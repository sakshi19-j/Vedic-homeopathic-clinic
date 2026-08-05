import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text, cast, String
from fastapi import HTTPException, status

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate

logger = logging.getLogger(__name__)


# =====================================================
# HELPERS
# =====================================================

def get_next_reg_no(db: Session, clinic_id: str) -> int:
    result = db.execute(
        text("""
            SELECT COALESCE(MAX(reg_no), 1000) + 1
            FROM patients
            WHERE clinic_id = :clinic_id
        """),
        {"clinic_id": clinic_id}
    ).scalar()
    return result


# =====================================================
# HELPERS
# =====================================================

def _attach_added_by_staff_name(db: Session, patient: Patient) -> Patient:
    if not patient.added_by_staff_id:
        patient.added_by_staff_name = None
        return patient

    staff_name = db.execute(
        text("""
            SELECT full_name
            FROM public.profiles
            WHERE id = :staff_id
        """),
        {"staff_id": str(patient.added_by_staff_id)}
    ).scalar()

    patient.added_by_staff_name = staff_name
    return patient


# =====================================================
# CREATE PATIENT
# =====================================================

def create_patient(
    db: Session,
    data: PatientCreate,
    clinic_id: str,
    added_by_staff_id: Optional[str] = None
) -> Patient:

    gender = data.gender.upper() if data.gender else None
    marital_status = data.marital_status.upper() if data.marital_status else None
    patient_type = data.patient_type.upper() if data.patient_type else "HOMEOPATHY"
    language_pref = data.language_pref.lower() if data.language_pref else "en"

    phone = _normalize_phone(data.phone_mobile) if data.phone_mobile else None

    patient = Patient(
        clinic_id=clinic_id,
        added_by_staff_id=added_by_staff_id,
        reg_no=get_next_reg_no(db, clinic_id),
        is_active=True,

        title=data.title,
        first_name=data.first_name,
        middle_name=data.middle_name,
        last_name=data.last_name,

        dob=data.dob,
        age=data.age,
        gender=gender,
        marital_status=marital_status,

        res_address=data.res_address,
        res_city=data.res_city,
        res_state=data.res_state,
        res_postal=data.res_postal,
        res_country=data.res_country or "India",

        off_address=data.off_address,
        off_city=data.off_city,
        off_state=data.off_state,
        off_postal=data.off_postal,

        phone_mobile=phone,
        phone_res=data.phone_res,
        phone_office=data.phone_office,

        fax=data.fax,
        email=data.email,

        referred_by_name=data.referred_by_name,
        referred_by_contact=data.referred_by_contact,

        language_pref=language_pref,
        patient_type=patient_type,
        anniversary=data.anniversary
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    logger.info(
        f"Patient created: {patient.id} | "
        f"Clinic: {clinic_id} | Reg: {patient.reg_no}"
    )

    return _attach_added_by_staff_name(db, patient)


# =====================================================
# GET PATIENTS
# =====================================================

def get_patients(
    db: Session,
    clinic_id: str,
    search: str = None,
    skip: int = 0,
    limit: int = 50
) -> list:
    """
    List/search patients — clinic-scoped, no debug queries.
    Limit capped at 200 to prevent accidental full-table dumps.
    """
    limit = min(limit, 200)

    query = db.query(Patient).filter(
        Patient.clinic_id == clinic_id,
        Patient.is_active == True
    )

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(search_term),
                Patient.last_name.ilike(search_term),
                Patient.middle_name.ilike(search_term),
                Patient.phone_mobile.ilike(search_term),
                cast(Patient.reg_no, String).ilike(search_term)
            )
        )

    patients = query.order_by(
        Patient.created_at.desc()
    ).offset(skip).limit(limit).all()

    for patient in patients:
        _attach_added_by_staff_name(db, patient)

    logger.debug(
        f"Patient list: clinic={clinic_id} "
        f"search={search!r} count={len(patients)}"
    )

    return patients


# =====================================================
# GET SINGLE PATIENT
# =====================================================

def get_patient_by_id(
    db: Session,
    patient_id: str,
    clinic_id: str
) -> Patient:
    """Always clinic-scoped. Never fetch by ID alone."""

    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    return _attach_added_by_staff_name(db, patient)


# =====================================================
# UPDATE PATIENT
# =====================================================

def update_patient(
    db: Session,
    patient_id: str,
    clinic_id: str,
    data: PatientUpdate
) -> Patient:

    patient = get_patient_by_id(db, patient_id, clinic_id)

    update_data = data.model_dump(exclude_unset=True)

    for enum_field in ("gender", "marital_status", "patient_type"):
        if update_data.get(enum_field):
            update_data[enum_field] = update_data[enum_field].upper()

    if "phone_mobile" in update_data and update_data["phone_mobile"]:
        update_data["phone_mobile"] = _normalize_phone(
            update_data["phone_mobile"]
        )

    for field, value in update_data.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)

    logger.info(f"Patient updated: {patient_id} | Clinic: {clinic_id}")

    return patient


# =====================================================
# PATIENT HISTORY
# =====================================================

def get_patient_history(
    db: Session,
    patient_id: str,
    clinic_id: str
) -> dict:
    """
    Complete visit timeline — fully clinic-scoped.
    """
    patient = get_patient_by_id(db, patient_id, clinic_id)

    from app.models.visit import Visit

    visits = db.query(Visit).filter(
        Visit.patient_id == patient_id,
        Visit.clinic_id == clinic_id
    ).order_by(
        Visit.visit_date.desc()
    ).all()

    history = []

    for v in visits:
        entry = {
            "visit_id":        v.id,
            "date":            v.visit_date.strftime("%d-%m-%Y") if v.visit_date else "",
            "type":            v.type.value if v.type else None,
            "chief_complaint": v.chief_complaint,
            "fee":             float(v.fee or 0),
            "payment_status":  v.payment_status.value if v.payment_status else None
        }

        if v.vitals:
            bp = ""
            if v.vitals.bp_systolic and v.vitals.bp_diastolic:
                bp = f"{v.vitals.bp_systolic}/{v.vitals.bp_diastolic}"
            entry["vitals"] = {
                "weight":      float(v.vitals.weight_kg or 0),
                "height":      float(v.vitals.height_cm or 0),
                "bp":          bp,
                "temperature": float(v.vitals.temperature or 0)
            }

        if v.homeopathy_case:
            entry["patient_rx"] = v.homeopathy_case.patient_rx
            entry["remedy"] = v.homeopathy_case.remedy
            entry["potency"] = v.homeopathy_case.potency
            entry["repetition"] = v.homeopathy_case.repetition
            entry["miasm"] = v.homeopathy_case.miasm

        entry["medicines"] = []

        if getattr(v, "medicines", None):
            for m in v.medicines:
                entry["medicines"].append({
                    "name": m.name,
                    "potency": m.potency,
                    "timing": m.timing,
                    "duration": m.days,
                    "instruction": m.notes,
                    "food_relation": m.food_relation
                })

        history.append(entry)
    return {
    "patient": {
        "id": patient.id,
        "reg_no": patient.reg_no,
        "name": f"{patient.first_name} {patient.last_name or ''}".strip(),
        "phone": patient.phone_mobile,
        "age": patient.age,
        "gender": patient.gender.value if patient.gender else None,
        "total_visits": patient.total_visits,
        "last_visit": (
            patient.last_visit_date.strftime("%d-%m-%Y")
            if patient.last_visit_date
            else None
        )
    },
    "visits": history,
    "total_visits": len(history)
}
# =====================================================
# SOFT DELETE
# =====================================================

def deactivate_patient(
    db: Session,
    patient_id: str,
    clinic_id: str
) -> dict:
    """
    Soft delete — never hard delete patient records.
    Medical records must be retained per Indian health regulations.
    """
    patient = get_patient_by_id(db, patient_id, clinic_id)
    patient.is_active = False
    db.commit()
    logger.info(f"Patient deactivated: {patient_id} | Clinic: {clinic_id}")
    return {"message": "Patient deactivated", "patient_id": patient_id}


# =====================================================
# PRIVATE HELPERS
# =====================================================

def _normalize_phone(phone: str) -> str:
    """
    Strips spaces, dashes, country code.
    Stores bare 10-digit number.
    WhatsApp service adds 91 prefix on send.
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+91"):
        phone = phone[4:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    return phone