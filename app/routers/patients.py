from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse
)
from app.services import patient_service
from app.services.audit_service import log_action

from app.middleware.auth_middleware import (
    get_current_user,
    doctor_only,
    receptionist_or_doctor,
    check_patient_limit
)

from app.models.user import User

router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)

@router.post("", response_model=PatientResponse)
def create_patient(
    request: Request,
    data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_patient_limit)
):
    patient = patient_service.create_patient(
        db, data, current_user.clinic_id
    )
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
    full = (
        f"{patient.title or ''} "
        f"{patient.first_name} "
        f"{patient.middle_name or ''} "
        f"{patient.last_name or ''}"
    ).strip()
    response = PatientResponse.model_validate(patient)
    response.full_name = full
    return response

@router.get("")
def list_patients(
    search: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patients = patient_service.get_patients(
        db, current_user.clinic_id, search, skip, limit
    )
    return {
        "total": len(patients),
        "patients": [
            {
                "id": p.id,
                "reg_no": p.reg_no,
                "full_name": f"{p.first_name} {p.last_name or ''}".strip(),
                "phone": p.phone_mobile,
                "city": p.res_city,
                "patient_type": p.patient_type.value if p.patient_type else None,
                "total_visits": p.total_visits,
                "last_visit": p.last_visit_date.strftime("%d-%m-%Y") if p.last_visit_date else None,
                "is_missed": p.is_missed
            }
            for p in patients
        ]
    }

@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patient = patient_service.get_patient_by_id(
        db, patient_id, current_user.clinic_id
    )
    full = (
        f"{patient.title or ''} "
        f"{patient.first_name} "
        f"{patient.middle_name or ''} "
        f"{patient.last_name or ''}"
    ).strip()
    response = PatientResponse.model_validate(patient)
    response.full_name = full
    return response

@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: str,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patient = patient_service.update_patient(
        db, patient_id, current_user.clinic_id, data
    )
    return PatientResponse.model_validate(patient)

@router.get("/{patient_id}/history")
def get_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return patient_service.get_patient_history(
        db, patient_id, current_user.clinic_id
    )