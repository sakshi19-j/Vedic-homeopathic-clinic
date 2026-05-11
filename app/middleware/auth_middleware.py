from fastapi import (
    Depends,
    HTTPException,
    status
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import pytz

from app.database import get_db
from app.utils.security import decode_token
from app.models.user import User, UserRole
from app.models.clinic import Clinic
from app.enums import SubscriptionStatus


IST = pytz.timezone("Asia/Kolkata")
security = HTTPBearer()


# =====================================================
# GET CURRENT USER
# =====================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again."
        )

    user = db.query(User).filter(
        User.id == payload.get("user_id")
    ).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated"
        )

    return user


# =====================================================
# SUBSCRIPTION CHECK
# =====================================================

def check_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return current_user

    if (
        clinic.subscription_status == SubscriptionStatus.TRIAL
        and clinic.trial_end_date
    ):
        trial_end = (
            IST.localize(clinic.trial_end_date)
            if clinic.trial_end_date.tzinfo is None
            else clinic.trial_end_date
        )

        if datetime.now(IST) > trial_end:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "Trial expired. Please upgrade to continue.",
                    "code": "TRIAL_EXPIRED",
                    "upgrade_url": "/settings/subscription"
                }
            )

    return current_user


# =====================================================
# PERMISSION MATRIX
# =====================================================

# What each role CANNOT access
ROLE_RESTRICTIONS = {
    "RECEPTIONIST": [
        "revenue",
        "analytics",
        "billing_summary",
        "export",
        "audit",
        "subscription"
    ],

    "NURSE": [
        "revenue",
        "billing_summary",
        "export",
        "audit",
        "subscription"
    ],

    "DOCTOR": []
}


# =====================================================
# ROLE GUARDS
# =====================================================

def doctor_only(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "This action requires doctor access.",
                "code": "DOCTOR_ONLY"
            }
        )

    return current_user


def receptionist_or_doctor(
    current_user: User = Depends(get_current_user)
) -> User:

    allowed = [
        UserRole.DOCTOR,
        UserRole.RECEPTIONIST
    ]

    if current_user.role not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Access denied.",
                "code": "INSUFFICIENT_ROLE"
            }
        )

    return current_user


def block_receptionist_from_revenue(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Blocks receptionist from seeing revenue/billing data.
    Use on analytics and billing summary endpoints.
    """

    if current_user.role == UserRole.RECEPTIONIST:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Revenue data is only visible to doctors.",
                "code": "REVENUE_RESTRICTED"
            }
        )

    return current_user


# =====================================================
# PLAN ORDER — FOR TIER COMPARISON
# =====================================================

PLAN_ORDER = {
    "trial": 0,
    "starter": 1,
    "growth": 2,
    "clinicpro": 3
}


# =====================================================
# REQUIRE PLAN — FEATURE GATE DECORATOR
# =====================================================

def require_plan(minimum_plan: str):
    """
    Usage:
        Depends(require_plan("growth"))

    Blocks if clinic is below minimum tier.
    """

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:

        clinic = db.query(Clinic).filter(
            Clinic.id == current_user.clinic_id
        ).first()

        if not clinic:
            raise HTTPException(
                status_code=403,
                detail="Clinic not found"
            )

        current_plan = (
            clinic.subscription_plan or "trial"
        ).lower()

        required_plan = minimum_plan.lower()

        current_level = PLAN_ORDER.get(current_plan, 0)
        required_level = PLAN_ORDER.get(required_plan, 1)

        if current_level < required_level:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": (
                        f"This feature requires "
                        f"{minimum_plan.title()} plan or above."
                    ),
                    "code": "PLAN_UPGRADE_REQUIRED",
                    "current_plan": current_plan,
                    "required_plan": required_plan,
                    "upgrade_url": "/settings/subscription"
                }
            )

        return current_user

    return checker


# =====================================================
# PATIENT LIMIT ENFORCER
# =====================================================

def check_patient_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Blocks patient registration if starter plan
    has exceeded monthly patient limit.
    """

    from app.models.patient import Patient

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return current_user

    # Unlimited patients
    if (clinic.max_patients_per_month or -1) == -1:
        return current_user

    now = datetime.now(IST)

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    count = db.query(Patient).filter(
        Patient.clinic_id == current_user.clinic_id,
        Patient.created_at >= month_start,
        Patient.is_active == True
    ).count()

    if count >= clinic.max_patients_per_month:
        raise HTTPException(
            status_code=403,
            detail={
                "message": (
                    f"Monthly patient limit reached "
                    f"({clinic.max_patients_per_month}/month on Starter plan). "
                    f"Upgrade to Growth for unlimited patients."
                ),
                "code": "PATIENT_LIMIT_REACHED",
                "used": count,
                "limit": clinic.max_patients_per_month,
                "upgrade_url": "/settings/subscription"
            }
        )

    return current_user


# =====================================================
# STAFF LIMIT ENFORCER
# =====================================================

def check_staff_limit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Blocks staff creation if plan limit reached.

    Starter   = 0 staff
    Growth    = 3 staff
    ClinicPro = unlimited
    """

    from app.models.staff import Staff

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return current_user

    max_staff = (
        clinic.max_staff
        if clinic.max_staff is not None
        else 0
    )

    # Unlimited
    if max_staff == -1:
        return current_user

    # No staff allowed
    if max_staff == 0:
        raise HTTPException(
            status_code=403,
            detail={
                "message": (
                    "Staff accounts are not available "
                    "on the Starter plan. Upgrade to "
                    "Growth to add up to 3 staff members."
                ),
                "code": "STAFF_NOT_ALLOWED",
                "upgrade_url": "/settings/subscription"
            }
        )

    count = db.query(Staff).filter(
        Staff.clinic_id == current_user.clinic_id,
        Staff.is_active == True
    ).count()

    if count >= max_staff:
        raise HTTPException(
            status_code=403,
            detail={
                "message": (
                    f"Staff limit reached ({max_staff} on your plan). "
                    f"Upgrade to Clinic Pro for unlimited staff."
                ),
                "code": "STAFF_LIMIT_REACHED",
                "used": count,
                "limit": max_staff,
                "upgrade_url": "/settings/subscription"
            }
        )

    return current_user


# =====================================================
# GRACE PERIOD CHECK — 3 DAYS AFTER EXPIRY
# =====================================================

def check_subscription_with_grace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Allows 3-day grace period after
    trial/subscription expires.

    After grace period → hard block with 402.
    """

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return current_user

    subscription_status = clinic.subscription_status

    # ACTIVE
    if (
        subscription_status == SubscriptionStatus.ACTIVE
        or str(subscription_status).upper() == "ACTIVE"
    ):
        return current_user

    # =====================================================
    # TRIAL CHECK
    # =====================================================

    if (
        subscription_status == SubscriptionStatus.TRIAL
        or str(subscription_status).upper() == "TRIAL"
    ) and clinic.trial_end_date:

        trial_end = (
            IST.localize(clinic.trial_end_date)
            if clinic.trial_end_date.tzinfo is None
            else clinic.trial_end_date
        )

        grace_end = trial_end + timedelta(days=3)

        if datetime.now(IST) <= grace_end:
            return current_user

        raise HTTPException(
            status_code=402,
            detail={
                "message": (
                    "Your trial has ended. "
                    "Please upgrade to continue."
                ),
                "code": "TRIAL_EXPIRED",
                "upgrade_url": "/settings/subscription"
            }
        )

    # =====================================================
    # EXPIRED SUBSCRIPTION CHECK
    # =====================================================

    if (
        subscription_status == SubscriptionStatus.EXPIRED
        or str(subscription_status).upper() == "EXPIRED"
    ) and clinic.subscription_start_date:

        grace_end = (
            clinic.subscription_start_date +
            timedelta(days=3)
        )

        if datetime.now(IST) <= grace_end:
            return current_user

        raise HTTPException(
            status_code=402,
            detail={
                "message": (
                    "Your subscription has expired. "
                    "Please renew to continue."
                ),
                "code": "SUBSCRIPTION_EXPIRED",
                "upgrade_url": "/settings/subscription"
            }
        )

    return current_user