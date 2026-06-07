from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from datetime import datetime, timedelta

from app.models.user import User
from app.models.clinic import Clinic

from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    CreateStaffRequest
)

from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token
)

from app.enums import (
    UserRole,
    SubscriptionPlan,
    SubscriptionStatus
)

import uuid
import pytz


IST = pytz.timezone("Asia/Kolkata")


# =========================================================
# Signup Clinic + Doctor
# =========================================================

def signup_clinic(
    db: Session,
    data: SignupRequest
) -> dict:
    """
    Create clinic + doctor account together.

    Only doctors can self-signup.
    Receptionists are created by doctor.
    """

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    existing = db.query(User).filter(
        or_(
            User.email == data.email,
            User.phone == data.phone
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email or phone already registered. Please login."
        )

    # -----------------------------------------------------
    # CREATE CLINIC
    # -----------------------------------------------------

    clinic_id = str(uuid.uuid4())

    trial_end = (
        datetime.now(IST)
        + timedelta(days=30)
    )

    clinic = Clinic(

        id=clinic_id,

        # Basic Info
        name=data.clinic_name,

        doctor_name=data.doctor_name,

        qualification=data.qualification,

        city=data.city,

        phone=data.phone,

        email=data.email,

        timings=data.timings,

        # -------------------------------------------------
        # CLINIC TYPE
        # -------------------------------------------------
        # HOMEOPATHY
        # ALLOPATHY
        # AYURVEDIC
        # MULTI
        # -------------------------------------------------

        clinic_type=(
            data.clinic_type
            or "HOMEOPATHY"
        ),

        # -------------------------------------------------
        # SUBSCRIPTION
        # -------------------------------------------------

        plan_id=SubscriptionPlan.STARTER.value,

        subscription_status=(
            SubscriptionStatus.TRIAL.value
        ),

        trial_end_date=trial_end,

        staff_limit=2,

        # Monthly patient usage limit
        max_patients_per_month=100,

        # -------------------------------------------------
        # BRANDING DEFAULTS
        # -------------------------------------------------

        branding_enabled=False,

        primary_color="#16a34a",

        secondary_color="#2563eb",

        # -------------------------------------------------
        # SETTINGS
        # -------------------------------------------------

        is_active=True
    )

    db.add(clinic)

    # -----------------------------------------------------
    # CREATE DOCTOR USER
    # -----------------------------------------------------

    user = User(

        clinic_id=clinic_id,

        name=data.doctor_name,

        phone=data.phone,

        email=data.email,

        # SECURE PASSWORD
        hashed_password=hash_password(
            data.password
        ),

        role=UserRole.DOCTOR
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    # -----------------------------------------------------
    # JWT TOKEN
    # -----------------------------------------------------

    token = create_access_token({

        "user_id": user.id,

        "clinic_id": clinic_id,

        "role": UserRole.DOCTOR.value,

        "name": data.doctor_name,

        "clinic_name": data.clinic_name
    })

    return {

        "access_token": token,

        "token_type": "bearer",

        "role": UserRole.DOCTOR.value,

        "name": data.doctor_name,

        "clinic_id": clinic_id,

        "clinic_name": data.clinic_name,

        "user_id": user.id,

        "plan": SubscriptionPlan.STARTER.value,

        "message":
            "Clinic account created successfully. "
            "30-day trial activated."
    }


# =========================================================
# LOGIN USER
# =========================================================

def login_user(
    db: Session,
    data: LoginRequest
) -> dict:
    """
    Login using email.
    """

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    # -----------------------------------------------------
    # VERIFY PASSWORD
    # -----------------------------------------------------

    if not user or not verify_password(
        data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    # -----------------------------------------------------
    # ACCOUNT STATUS
    # -----------------------------------------------------

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account deactivated. Contact clinic admin."
        )

    # -----------------------------------------------------
    # GET CLINIC
    # -----------------------------------------------------

    clinic = db.query(Clinic).filter(
        Clinic.id == user.clinic_id
    ).first()

    clinic_name = (
        clinic.name
        if clinic else "Clinic"
    )

    # -----------------------------------------------------
    # PLAN LOGIC
    # -----------------------------------------------------

    plan = (
        clinic.plan_id
        if clinic and clinic.plan_id
        else SubscriptionPlan.STARTER.value
    )

    # -----------------------------------------------------
    # BRANDING
    # -----------------------------------------------------

    branding = None

    if clinic and getattr(
        clinic,
        "branding_enabled",
        False
    ):
        branding = {

            "primary_color":
                clinic.primary_color,

            "secondary_color":
                clinic.secondary_color,

            "custom_logo":
                clinic.custom_logo
        }

    # -----------------------------------------------------
    # USAGE STATS
    # -----------------------------------------------------

    usage_stats = get_usage_stats(
        db,
        user.clinic_id
    )

    # -----------------------------------------------------
    # JWT TOKEN
    # -----------------------------------------------------

    token = create_access_token({

        "user_id": user.id,

        "clinic_id": user.clinic_id,

        "role": user.role.value,

        "name": user.name,

        "clinic_name": clinic_name
    })

    return {

        "access_token": token,

        "token_type": "bearer",

        "role": user.role.value,

        "name": user.name,

        "clinic_id": user.clinic_id,

        "clinic_name": clinic_name,

        "user_id": user.id,

        "plan": plan,

        "branding": branding,

        "usage": usage_stats
    }


# =========================================================
# CREATE STAFF ACCOUNT
# =========================================================

def create_staff_account(
    db: Session,
    data: CreateStaffRequest,
    clinic_id: str
) -> User:
    """
    Doctor creates receptionist/staff accounts.
    """

    # -----------------------------------------------------
    # GET CLINIC
    # -----------------------------------------------------

    clinic = db.query(Clinic).filter(
        Clinic.id == clinic_id
    ).first()

    # -----------------------------------------------------
    # CURRENT STAFF COUNT
    # -----------------------------------------------------

    current_staff = db.query(User).filter(
        User.clinic_id == clinic_id,
        User.role != UserRole.DOCTOR,
        User.is_active == True
    ).count()

    # -----------------------------------------------------
    # STAFF LIMIT CHECK
    # -----------------------------------------------------

    if (
        clinic
        and current_staff >= (
            clinic.staff_limit or 2
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Staff limit reached "
                f"({clinic.staff_limit}). "
                f"Upgrade your plan."
            )
        )

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    existing = db.query(User).filter(
        or_(
            User.phone == data.phone,
            User.email == data.email
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email or phone already registered."
        )

    # -----------------------------------------------------
    # CREATE STAFF USER
    # -----------------------------------------------------

    user = User(

        clinic_id=clinic_id,

        name=data.name,

        phone=data.phone,

        email=data.email,

        hashed_password=hash_password(
            data.password
        ),

        role=data.role
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return user


# =========================================================
# USAGE STATS
# =========================================================

def get_usage_stats(
    db: Session,
    clinic_id: str
) -> dict:
    """
    Patients added this month vs plan limit.
    Called from /auth/clinic and /analytics/dashboard.
    """

    from app.models.patient import Patient

    clinic = db.query(Clinic).filter(
        Clinic.id == clinic_id
    ).first()

    if not clinic:
        raise HTTPException(
            status_code=404,
            detail="Clinic not found"
        )

    # -----------------------------------------------------
    # CURRENT MONTH START
    # -----------------------------------------------------

    now = datetime.utcnow()

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    # -----------------------------------------------------
    # PATIENT COUNT
    # -----------------------------------------------------

    patients_this_month = db.query(Patient).filter(
        Patient.clinic_id == clinic_id,
        Patient.created_at >= month_start
    ).count()

    # -----------------------------------------------------
    # PLAN LIMIT
    # -----------------------------------------------------

    limit = clinic.max_patients_per_month or 100

    # -----------------------------------------------------
    # USAGE %
    # -----------------------------------------------------

    usage_percent = (
        round((patients_this_month / limit) * 100, 1)
        if limit > 0 else 0
    )

    return {
        "patients_this_month": patients_this_month,

        "limit": limit,

        "remaining": max(
            0,
            limit - patients_this_month
        ),

        "usage_percent": usage_percent,

        "limit_reached": (
            patients_this_month >= limit
        )
    }
