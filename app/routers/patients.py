from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.database import get_db

from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse
)

from app.services import patient_service
from app.services.audit_service import log_action

from app.middleware.auth_middleware import (
    CurrentUser,
    get_current_user,
    receptionist_or_doctor,
    check_patient_limit
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)


# =====================================================
# CREATE PATIENT
# =====================================================

@router.post("", response_model=PatientResponse)
def create_patient(
    request: Request,
    data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(check_patient_limit)
):
    patient = patient_service.create_patient(
        db,
        data,
        current_user.clinic_id
    )

    # ─────────────────────────────────────────────
    # REFRESH OBJECT SAFELY
    # ─────────────────────────────────────────────
    try:
        db.refresh(patient)
    except Exception:
        pass

    # ─────────────────────────────────────────────
    # AUDIT LOG (NON-CRITICAL)
    # ─────────────────────────────────────────────
    try:
        log_action(
            db=db,
            user=current_user,
            action="PATIENT_CREATED",
            resource="patient",
            resource_id=patient.id,
            detail=(
                f"Registered "
                f"{patient.first_name} "
                f"{patient.last_name or ''} "
                f"({patient.reg_no})"
            ),
            ip_address=request.client.host if request else None,
        )

    except Exception as e:
        logger.warning(
            f"Audit log failed (non-critical): {e}"
        )

        # Reset failed transaction state
        db.rollback()

    # ─────────────────────────────────────────────
    # SAFE RESPONSE BUILD
    # ─────────────────────────────────────────────
    return {
        "id": str(patient.id),
        "reg_no": patient.reg_no,
        "title": patient.title,
        "first_name": patient.first_name,
        "middle_name": patient.middle_name,
        "last_name": patient.last_name,
        "full_name": (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip(),
        "dob": (
            str(patient.dob)
            if patient.dob
            else None
        ),
        "age": patient.age,
        "gender": patient.gender,
        "marital_status": patient.marital_status,
        "res_address": patient.res_address,
        "res_city": patient.res_city,
        "res_state": patient.res_state,
        "res_postal": patient.res_postal,
        "res_country": patient.res_country,
        "phone_mobile": patient.phone_mobile,
        "phone_res": patient.phone_res,
        "email": patient.email,
        "referred_by_name": patient.referred_by_name,
        "referred_by_contact": patient.referred_by_contact,
        "language_pref": (
            patient.language_pref or "en"
        ),
        "patient_type": patient.patient_type,
        "total_visits": (
            patient.total_visits or 0
        ),
        "total_spent": float(
            patient.total_spent or 0
        ),
        "patient_value_score": float(
            patient.patient_value_score or 0
        ),
        "is_missed": (
            patient.is_missed or False
        ),
        "last_visit_date": (
            str(patient.last_visit_date)
            if patient.last_visit_date
            else None
        ),
    }


# =====================================================
# LIST PATIENTS
# =====================================================

@router.get("")
def list_patients(
    search: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        receptionist_or_doctor
    )
):
    patients = patient_service.get_patients(
        db,
        current_user.clinic_id,
        search,
        skip,
        limit
    )

    return {
        "total": len(patients),
        "patients": [
            {
                "id": p.id,
                "reg_no": p.reg_no,
                "full_name": (
                    f"{p.first_name} "
                    f"{p.last_name or ''}"
                ).strip(),
                "phone": p.phone_mobile,
                "city": p.res_city,
                "patient_type": (
                    p.patient_type.value
                    if p.patient_type
                    else None
                ),
                "total_visits": p.total_visits,
                "last_visit": (
                    p.last_visit_date.strftime("%d-%m-%Y")
                    if p.last_visit_date
                    else None
                ),
                "is_missed": p.is_missed
            }
            for p in patients
        ]
    }


# =====================================================
# GET SINGLE PATIENT
# =====================================================

@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        receptionist_or_doctor
    )
):
    patient = patient_service.get_patient_by_id(
        db,
        patient_id,
        current_user.clinic_id
    )

    return {
        "id": str(patient.id),
        "reg_no": patient.reg_no,
        "title": patient.title,
        "first_name": patient.first_name,
        "middle_name": patient.middle_name,
        "last_name": patient.last_name,
        "full_name": (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip(),
        "dob": (
            str(patient.dob)
            if patient.dob
            else None
        ),
        "age": patient.age,
        "gender": patient.gender,
        "marital_status": patient.marital_status,
        "res_address": patient.res_address,
        "res_city": patient.res_city,
        "res_state": patient.res_state,
        "res_postal": patient.res_postal,
        "res_country": patient.res_country,
        "phone_mobile": patient.phone_mobile,
        "phone_res": patient.phone_res,
        "email": patient.email,
        "referred_by_name": patient.referred_by_name,
        "referred_by_contact": patient.referred_by_contact,
        "language_pref": (
            patient.language_pref or "en"
        ),
        "patient_type": patient.patient_type,
        "total_visits": (
            patient.total_visits or 0
        ),
        "total_spent": float(
            patient.total_spent or 0
        ),
        "patient_value_score": float(
            patient.patient_value_score or 0
        ),
        "is_missed": (
            patient.is_missed or False
        ),
        "last_visit_date": (
            str(patient.last_visit_date)
            if patient.last_visit_date
            else None
        ),
    }


# =====================================================
# UPDATE PATIENT
# =====================================================

@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: str,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        receptionist_or_doctor
    )
):
    patient = patient_service.update_patient(
        db,
        patient_id,
        current_user.clinic_id,
        data
    )

    return {
        "id": str(patient.id),
        "reg_no": patient.reg_no,
        "title": patient.title,
        "first_name": patient.first_name,
        "middle_name": patient.middle_name,
        "last_name": patient.last_name,
        "full_name": (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip(),
        "dob": (
            str(patient.dob)
            if patient.dob
            else None
        ),
        "age": patient.age,
        "gender": patient.gender,
        "marital_status": patient.marital_status,
        "res_address": patient.res_address,
        "res_city": patient.res_city,
        "res_state": patient.res_state,
        "res_postal": patient.res_postal,
        "res_country": patient.res_country,
        "phone_mobile": patient.phone_mobile,
        "phone_res": patient.phone_res,
        "email": patient.email,
        "referred_by_name": patient.referred_by_name,
        "referred_by_contact": patient.referred_by_contact,
        "language_pref": (
            patient.language_pref or "en"
        ),
        "patient_type": patient.patient_type,
        "total_visits": (
            patient.total_visits or 0
        ),
        "total_spent": float(
            patient.total_spent or 0
        ),
        "patient_value_score": float(
            patient.patient_value_score or 0
        ),
        "is_missed": (
            patient.is_missed or False
        ),
        "last_visit_date": (
            str(patient.last_visit_date)
            if patient.last_visit_date
            else None
        ),
    }


# =====================================================
# PATIENT HISTORY
# =====================================================

@router.get("/{patient_id}/history")
def get_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(
        get_current_user
    )
):
    return patient_service.get_patient_history(
        db,
        patient_id,
        current_user.clinic_id
    )
