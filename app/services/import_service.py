import pandas as pd

from fastapi import UploadFile

from sqlalchemy.orm import Session

from app.models.patient import Patient

from datetime import datetime

import uuid


async def import_patients_excel(

    db: Session,

    clinic_id: str,

    file: UploadFile
):

    contents = await file.read()

    temp_path = f"temp_{uuid.uuid4()}.xlsx"

    with open(temp_path, "wb") as f:

        f.write(contents)

    df = pd.read_excel(temp_path)

    created = 0

    skipped = 0

    errors = []

    for index, row in df.iterrows():

        try:

            phone = str(
                row.get("phone", "")
            ).strip()

            existing = db.query(Patient).filter(

                Patient.phone_mobile == phone,

                Patient.clinic_id == clinic_id

            ).first()

            if existing:

                skipped += 1
                continue

            patient = Patient(

                clinic_id=clinic_id,

                first_name=str(
                    row.get("first_name", "")
                ),

                last_name=str(
                    row.get("last_name", "")
                ),

                phone_mobile=phone,

                age=int(
                    row.get("age", 0)
                ),

                gender=row.get(
                    "gender",
                    "MALE"
                ),

                created_at=datetime.utcnow()
            )

            db.add(patient)

            created += 1

        except Exception as e:

            errors.append({

                "row": index + 1,

                "error": str(e)
            })

    db.commit()

    return {

        "success": True,

        "created": created,

        "skipped": skipped,

        "errors": errors
    }