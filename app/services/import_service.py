import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.models.patient import Patient
from datetime import datetime
import uuid
import re

# Map of target field -> list of header aliases we'll match against (case-insensitive, punctuation-stripped)
FIELD_ALIASES = {
    "first_name": ["first name", "firstname", "name", "patient name", "full name"],
    "last_name": ["last name", "lastname", "surname"],
    "phone_mobile": ["phone", "mobile", "mobile no", "contact", "phone number", "cell"],
    "age": ["age"],
    "gender": ["gender", "sex"],
}

def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def _build_column_map(columns) -> dict:
    """Match each spreadsheet column to our internal field name."""
    norm_cols = {c: _normalize(c) for c in columns}
    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        norm_aliases = [_normalize(a) for a in aliases]
        for orig_col, norm_col in norm_cols.items():
            if norm_col in norm_aliases:
                mapping[field] = orig_col
                break
    return mapping


async def import_patients_excel(db: Session, clinic_id: str, file: UploadFile):
    contents = await file.read()
    temp_path = f"temp_{uuid.uuid4()}.xlsx"
    with open(temp_path, "wb") as f:
        f.write(contents)

    # Support both .xlsx and .csv automatically
    if file.filename and file.filename.lower().endswith(".csv"):
        df = pd.read_csv(temp_path)
    else:
        df = pd.read_excel(temp_path)

    col_map = _build_column_map(df.columns)

    if "first_name" not in col_map or "phone_mobile" not in col_map:
        return {
            "success": False,
            "created": 0,
            "skipped": 0,
            "errors": [{
                "row": 0,
                "error": (
                    f"Could not detect required columns. Found headers: {list(df.columns)}. "
                    f"We need at least a name column and a phone column."
                )
            }],
            "detected_columns": col_map,
        }

    created = 0
    skipped = 0
    errors = []

    for index, row in df.iterrows():
        try:
            def get(field, default=""):
                col = col_map.get(field)
                if col is None:
                    return default
                val = row.get(col, default)
                return "" if pd.isna(val) else val

            phone = str(get("phone_mobile", "")).strip()
            if not phone:
                skipped += 1
                continue

            existing = db.query(Patient).filter(
                Patient.phone_mobile == phone,
                Patient.clinic_id == clinic_id
            ).first()

            if existing:
                skipped += 1
                continue

            age_raw = get("age", 0)
            try:
                age_val = int(age_raw) if age_raw not in ("", None) else None
            except (ValueError, TypeError):
                age_val = None

            gender_raw = str(get("gender", "")).strip().upper()
            gender_val = gender_raw if gender_raw in ("MALE", "FEMALE", "OTHER") else None

            patient = Patient(
                clinic_id=clinic_id,
                first_name=str(get("first_name", "")).strip(),
                last_name=str(get("last_name", "")).strip() or None,
                phone_mobile=phone,
                age=age_val,
                gender=gender_val,
                created_at=datetime.utcnow()
            )
            db.add(patient)
            created += 1

        except Exception as e:
            errors.append({"row": index + 1, "error": str(e)})

    db.commit()

    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "detected_columns": col_map,
    }