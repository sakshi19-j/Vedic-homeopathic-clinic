from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.middleware.auth_middleware import (
    doctor_only
)

from app.models.user import User

from app.models.doctor_profile import (
    DoctorProfile
)

router = APIRouter(
    prefix="/doctor-profile",
    tags=["Doctor Profile"]
)


# =====================================================
# CREATE / UPDATE
# =====================================================

@router.post("/")
def create_or_update_profile(

    data: dict,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        doctor_only
    )
):

    profile = db.query(DoctorProfile).filter(

        DoctorProfile.clinic_id
        == current_user.clinic_id

    ).first()

    if not profile:

        profile = DoctorProfile(

            clinic_id=current_user.clinic_id
        )

        db.add(profile)

    profile.doctor_name = data.get(
        "doctor_name"
    )

    profile.clinic_name = data.get(
        "clinic_name"
    )

    profile.qualification = data.get(
        "qualification"
    )

    profile.registration_number = data.get(
        "registration_number"
    )

    profile.specialty = data.get(
        "specialty"
    )

    profile.whatsapp_number = data.get(
        "whatsapp_number"
    )

    profile.clinic_address = data.get(
        "clinic_address"
    )

    db.commit()

    return {
        "message": "Doctor profile saved"
    }


# =====================================================
# GET PROFILE
# =====================================================

@router.get("/")
def get_profile(

    db: Session = Depends(get_db),

    current_user: User = Depends(
        doctor_only
    )
):

    profile = db.query(DoctorProfile).filter(

        DoctorProfile.clinic_id
        == current_user.clinic_id

    ).first()

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    return profile