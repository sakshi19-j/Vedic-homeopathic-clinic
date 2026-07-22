import logging
import time
import threading
from datetime import datetime, timedelta

import pytz
import httpx

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer
)

from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.clinic import Clinic

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

security = HTTPBearer(auto_error=False)


# =====================================================
# CURRENT USER DATACLASS
# =====================================================

class CurrentUser:
    def __init__(
        self,
        id: str,
        clinic_id: str,
        role: str,
        email: str,
        full_name: str,
        is_active: bool = True
    ):
        self.id = id
        self.clinic_id = clinic_id
        self.role = role
        self.email = email
        self.full_name = full_name
        self.is_active = is_active

    def __repr__(self):
        return (
            f"<CurrentUser "
            f"id={self.id} "
            f"role={self.role} "
            f"clinic={self.clinic_id}>"
        )


# =====================================================
# JWKS CACHE
# -----------------------------------------------------
# FIX: decode_supabase_token used to call httpx.get() on
# Supabase's JWKS endpoint on EVERY single request. Since
# this runs inside get_current_user (a dependency on almost
# every route), and the DB session dependency is resolved
# alongside it, every request held a DB connection idle
# for up to `timeout` seconds while waiting on this network
# call. Under any real concurrency this exhausted the
# SQLAlchemy pool (see database.py: pool_size=5,
# max_overflow=5) and caused QueuePool timeout errors on
# every other request, including auth itself -- effectively
# taking the whole backend down.
#
# JWKS keys barely ever rotate, so we cache them in-process
# and only refetch once per hour (or immediately if nothing
# has been fetched yet). A lock guards against multiple
# threads refetching simultaneously the first time.
# =====================================================

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0
_jwks_lock = threading.Lock()
_JWKS_TTL_SECONDS = 3600  # refresh at most once per hour


def get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at

    now = time.time()
    if _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    with _jwks_lock:
        # Re-check inside the lock in case another thread already refreshed
        # it while we were waiting.
        now = time.time()
        if _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
            return _jwks_cache

        jwks_url = (
            f"{settings.SUPABASE_URL}"
            f"/auth/v1/.well-known/jwks.json"
        )

        response = httpx.get(jwks_url, timeout=10)
        response.raise_for_status()

        _jwks_cache = response.json()
        _jwks_fetched_at = now

        logger.info("Refreshed Supabase JWKS cache")

        return _jwks_cache


# =====================================================
# DECODE SUPABASE JWT
# FINAL FIXED VERSION
# =====================================================

def decode_supabase_token(token: str) -> dict | None:
    try:
        jwks = get_jwks()

        # Decode token
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["ES256"],
            options={
                "verify_aud": False
            }
        )

        logger.info(
            f"JWT decoded successfully "
            f"for user: {payload.get('sub')}"
        )

        return payload

    except Exception as e:
        logger.warning(
            f"JWT decode failed: {e}"
        )
        return None


# =====================================================
# GET CURRENT USER
# =====================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUser:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token"
        )

    token = credentials.credentials

    payload = decode_supabase_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid or expired token. "
                "Please log in again."
            )
        )

    # Supabase user UUID
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity."
        )

    from sqlalchemy import text

    profile_row = db.execute(
        text(
            """
            SELECT
                p.clinic_id,
                p.full_name,
                p.email,
                ur.role,
                ur.is_active
            FROM public.profiles p
            JOIN public.user_roles ur
                ON ur.user_id = p.id
                AND ur.clinic_id = p.clinic_id
            WHERE p.id = :uid
            LIMIT 1
            """
        ),
        {"uid": user_id}
    ).fetchone()

    if not profile_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "User profile not found. "
                "Contact clinic admin."
            )
        )

    if not profile_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been deactivated."
        )

    return CurrentUser(
        id=user_id,
        clinic_id=str(profile_row.clinic_id),
        role=profile_row.role,
        email=profile_row.email or "",
        full_name=profile_row.full_name or "",
        is_active=profile_row.is_active
    )


# =====================================================
# SUBSCRIPTION CHECK
# =====================================================

def check_subscription_with_grace(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CurrentUser:

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return current_user

    now = datetime.now(IST)

    # TRIAL
    if clinic.subscription_status == "TRIAL":

        if clinic.trial_end_date:

            trial_end = (
                IST.localize(clinic.trial_end_date)
                if clinic.trial_end_date.tzinfo is None
                else clinic.trial_end_date
            )

            grace_end = (
                trial_end + timedelta(days=3)
            )

            if now <= grace_end:
                return current_user

        raise HTTPException(
            status_code=402,
            detail={
                "message": (
                    "Trial ended. "
                    "Please upgrade to continue."
                ),
                "code": "TRIAL_EXPIRED",
                "upgrade_url":
                    "/settings/subscription"
            }
        )

    # ACTIVE
    if clinic.subscription_status == "ACTIVE":
        return current_user

    # EXPIRED
    if clinic.subscription_status == "EXPIRED":

        if clinic.grace_period_end:

            grace_end = (
                IST.localize(
                    clinic.grace_period_end
                )
                if clinic.grace_period_end.tzinfo is None
                else clinic.grace_period_end
            )

            if now <= grace_end:
                return current_user

        raise HTTPException(
            status_code=402,
            detail={
                "message": (
                    "Subscription expired. "
                    "Please renew."
                ),
                "code": "SUBSCRIPTION_EXPIRED",
                "upgrade_url":
                    "/settings/subscription"
            }
        )

    return current_user


# =====================================================
# ROLE GUARDS
# =====================================================

def admin_only(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:

    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "message":
                    "Admin access required.",
                "code": "ADMIN_ONLY"
            }
        )

    return current_user


def doctor_only(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:

    allowed = (
        "allopathy",
        "homeopathy",
        "admin"
    )

    if current_user.role not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "message":
                    "Doctor access required.",
                "code": "DOCTOR_ONLY"
            }
        )

    return current_user


def receptionist_or_doctor(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:

    allowed = (
        "admin",
        "reception",
        "allopathy",
        "homeopathy"
    )

    if current_user.role not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Access denied.",
                "code":
                    "INSUFFICIENT_ROLE"
            }
        )

    return current_user


def block_receptionist_from_revenue(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:

    if current_user.role == "reception":
        raise HTTPException(
            status_code=403,
            detail={
                "message":
                    "Revenue data is only visible "
                    "to doctors.",
                "code":
                    "REVENUE_RESTRICTED"
            }
        )

    return current_user


# =====================================================
# BACKWARDS COMPATIBILITY
# =====================================================

check_subscription = (
    check_subscription_with_grace
)

# =====================================================
# PLAN GATING
# =====================================================

PLAN_ORDER = {
    "trial": 0,
    "starter": 1,
    "growth": 2,
    "clinicpro": 3
}


def require_plan(minimum_plan: str):

    def checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> CurrentUser:

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

        required_plan = (
            minimum_plan.lower()
        )

        if (
            PLAN_ORDER.get(current_plan, 0)
            < PLAN_ORDER.get(required_plan, 1)
        ):
            raise HTTPException(
                status_code=402,
                detail={
                    "message":
                        f"Requires "
                        f"{minimum_plan.title()} "
                        f"plan or above.",
                    "code":
                        "PLAN_UPGRADE_REQUIRED",
                    "current_plan":
                        current_plan,
                    "required_plan":
                        required_plan,
                    "upgrade_url":
                        "/settings/subscription"
                }
            )

        return current_user

    return checker


# =====================================================
# PATIENT LIMIT ENFORCER
# =====================================================

def check_patient_limit(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CurrentUser:

    from app.models.patient import Patient

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        return current_user

    limit = (
        clinic.max_patients_per_month or -1
    )

    if limit == -1:
        return current_user

    now = datetime.now(IST)

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    month_start_naive = (
        month_start.replace(tzinfo=None)
    )

    count = db.query(Patient).filter(
        Patient.clinic_id ==
            current_user.clinic_id,
        Patient.created_at >=
            month_start_naive,
        Patient.is_active == True
    ).count()

    if count >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "message":
                    f"Monthly patient limit "
                    f"reached ({limit}/month).",
                "code":
                    "PATIENT_LIMIT_REACHED",
                "used":
                    count,
                "limit":
                    limit,
                "upgrade_url":
                    "/settings/subscription"
            }
        )

    return current_user


# =====================================================
# STAFF LIMIT ENFORCER
# =====================================================

def check_staff_limit(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CurrentUser:

    from sqlalchemy import text

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

    if max_staff == -1:
        return current_user

    if max_staff == 0:
        raise HTTPException(
            status_code=402,
            detail={
                "message":
                    "Staff accounts require "
                    "Growth plan or above.",
                "code":
                    "STAFF_NOT_ALLOWED",
                "upgrade_url":
                    "/settings/subscription"
            }
        )

    count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM public.user_roles
            WHERE clinic_id = :cid
            AND role = 'reception'
            AND is_active = true
            """
        ),
        {
            "cid":
                current_user.clinic_id
        }
    ).scalar()

    if count >= max_staff:
        raise HTTPException(
            status_code=402,
            detail={
                "message":
                    f"Staff limit reached "
                    f"({max_staff}).",
                "code":
                    "STAFF_LIMIT_REACHED",
                "used":
                    count,
                "limit":
                    max_staff,
                "upgrade_url":
                    "/settings/subscription"
            }
        )

    return current_user