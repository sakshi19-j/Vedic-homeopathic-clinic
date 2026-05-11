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


# =====================================================
# CREATE PATIENT
# =====================================================

@router.post("/", response_model=PatientResponse)
def create_patient(
    request: Request,

    data: PatientCreate,

    db: Session = Depends(get_db),

    # BOTH ROLES + PLAN LIMIT CHECK
    current_user: User = Depends(check_patient_limit)
):
    """
    Register new patient.

    Receptionist does this at front desk when patient arrives.

    Auto-assigns next Reg.No. just like Hompath Classic.
    """

    patient = patient_service.create_patient(
        db,
        data,
        current_user.clinic_id
    )

    # =====================================================
    # AUDIT LOG
    # =====================================================

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

    # Build full_name for response
    full = (
        f"{patient.title or ''} "
        f"{patient.first_name} "
        f"{patient.middle_name or ''} "
        f"{patient.last_name or ''}"
    ).strip()

    response = PatientResponse.model_validate(patient)
    response.full_name = full

    return response


# =====================================================
# LIST PATIENTS
# =====================================================

@router.get("/")
def list_patients(
    search: Optional[str] = Query(
        None,
        description="Search by name or phone"
    ),

    skip: int = Query(
        0,
        description="Pagination offset"
    ),

    limit: int = Query(
        50,
        description="Max results"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        receptionist_or_doctor
    )
):
    """
    List all patients with search.

    Receptionist types patient name or phone
    → instant results.
    """

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

                "full_name":
                    f"{p.first_name} "
                    f"{p.last_name or ''}".strip(),

                "phone": p.phone_mobile,
                "city": p.res_city,

                "patient_type":
                    p.patient_type.value
                    if p.patient_type else None,

                "total_visits": p.total_visits,

                "last_visit":
                    p.last_visit_date.strftime("%d-%m-%Y")
                    if p.last_visit_date else None,

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

    current_user: User = Depends(
        receptionist_or_doctor
    )
):
    """
    Get full patient profile.
    """

    patient = patient_service.get_patient_by_id(
        db,
        patient_id,
        current_user.clinic_id
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


# =====================================================
# UPDATE PATIENT
# =====================================================

@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: str,

    data: PatientUpdate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        receptionist_or_doctor
    )
):
    """
    Update patient details.
    """

    patient = patient_service.update_patient(
        db,
        patient_id,
        current_user.clinic_id,
        data
    )

    return PatientResponse.model_validate(patient)


# =====================================================
# PATIENT HISTORY
# =====================================================

@router.get("/{patient_id}/history")
def get_history(
    patient_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):
    """
    Full visit timeline for a patient.

    Doctor sees this before consultation —
    all past visits, remedies,
    potencies in one view.
    """

    return patient_service.get_patient_history(
        db,
        patient_id,
        current_user.clinic_id
    )