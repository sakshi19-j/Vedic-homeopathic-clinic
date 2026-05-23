from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    CreateStaffRequest,
    LoginResponse,
    UserResponse
)

from app.services import auth_service

from app.middleware.auth_middleware import (
    get_current_user,
    doctor_only
)

from app.models.user import User
from app.models.clinic import Clinic


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


# =========================================================
# SIGNUP
# =========================================================

@router.post("/signup")
def signup(
    data: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    New clinic registration.
    Creates clinic + doctor account in one step.
    Starts 30-day free trial automatically.
    """

    return auth_service.signup_clinic(
        db,
        data
    )


# =========================================================
# LOGIN
# =========================================================

@router.post(
    "/login",
    response_model=LoginResponse
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email OR phone + password
    """

    return auth_service.login_user(
        db,
        data
    )


# =========================================================
# CREATE STAFF
# =========================================================

@router.post(
    "/staff",
    response_model=UserResponse
)
def create_staff(
    data: CreateStaffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(doctor_only)
):
    """
    Doctor creates receptionist account.
    Staff cannot self-signup — security requirement.
    """

    user = auth_service.create_staff_account(
        db,
        data,
        current_user.clinic_id
    )

    return user


# =========================================================
# CURRENT USER
# =========================================================

@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user info
    """

    return current_user


# =========================================================
# GET CLINIC
# =========================================================

@router.get("/clinic")
def get_clinic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current clinic details
    """

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return {
            "message": "Clinic not set up yet"
        }

    # -----------------------------------------------------
    # USAGE STATS
    # -----------------------------------------------------

    usage = auth_service.get_usage_stats(
        db,
        current_user.clinic_id
    )

    return {

        "id": clinic.id,

        "name": clinic.name,

        "doctor_name": clinic.doctor_name,

        "qualification": clinic.qualification,

        "address": clinic.address,

        "city": clinic.city,

        "phone": clinic.phone,

        "email": clinic.email,

        "timings": clinic.timings,

        "plan": clinic.plan_id,

        "subscription_status":
            clinic.subscription_status,

        "trial_end_date": (
            str(clinic.trial_end_date)
            if clinic.trial_end_date
            else None
        ),

        "branding_enabled":
            clinic.branding_enabled,

        "primary_color":
            clinic.primary_color,

        "secondary_color":
            clinic.secondary_color,

        # -------------------------------------------------
        # NEW BRANDING FIELDS
        # -------------------------------------------------

        "logo_url":
            clinic.logo_url,

        "signature_url":
            clinic.signature_url,

        "notification_settings":
            clinic.notification_settings,

        "clinic_type":
            clinic.clinic_type,

        # -------------------------------------------------
        # SUBSCRIPTION LIMITS
        # -------------------------------------------------

        "staff_limit":
            clinic.staff_limit,

        "max_patients_per_month":
            clinic.max_patients_per_month,

        # -------------------------------------------------
        # USAGE
        # -------------------------------------------------

        "usage": usage
    }


# =========================================================
# UPDATE CLINIC
# =========================================================

@router.put("/clinic")
def update_clinic(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(doctor_only)
):
    """
    Update clinic details — doctor only
    """

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        raise HTTPException(
            status_code=404,
            detail="Clinic not found"
        )

    allowed = [
        "name",
        "doctor_name",
        "qualification",
        "address",
        "city",
        "phone",
        "email",
        "timings",
        "primary_color",
        "secondary_color",
        "logo_url",
        "signature_url",
        "notification_settings",
        "clinic_type"
    ]

    for key, value in data.items():

        if key in allowed:
            setattr(clinic, key, value)

    db.commit()

    db.refresh(clinic)

    return {

        "message": "Clinic updated successfully",

        "clinic": {

            "id": clinic.id,

            "name": clinic.name,

            "doctor_name": clinic.doctor_name,

            "qualification": clinic.qualification,

            "address": clinic.address,

            "city": clinic.city,

            "phone": clinic.phone,

            "email": clinic.email,

            "timings": clinic.timings,

            "primary_color": clinic.primary_color,

            "secondary_color": clinic.secondary_color,

            "logo_url": clinic.logo_url,

            "signature_url": clinic.signature_url,

            "notification_settings": clinic.notification_settings,

            "clinic_type": clinic.clinic_type
        }
    }


# =========================================================
# USAGE STATS
# =========================================================

@router.get("/usage")
def get_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Patient usage this month vs plan limit
    """

    from app.services.auth_service import (
        get_usage_stats
    )

    return get_usage_stats(
        db,
        current_user.clinic_id
    )