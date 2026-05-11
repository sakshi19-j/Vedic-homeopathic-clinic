from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

from app.services import analytics_service

from app.middleware.auth_middleware import (
    doctor_only,
    get_current_user,
    require_plan,
    block_receptionist_from_revenue
)

from app.models.user import User


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# ─────────────────────────────────────────────────────
# FULL DASHBOARD
# ─────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),

    # Revenue restriction
    current_user: User = Depends(
        block_receptionist_from_revenue
    ),

    # Growth+ only
    plan_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Full analytics dashboard.
    Growth plan and above only.
    """

    clinic_id = current_user.clinic_id

    return {

        "daily_revenue":
            analytics_service.daily_revenue(
                db,
                clinic_id
            ),

        "monthly_revenue":
            analytics_service.monthly_revenue(
                db,
                clinic_id
            ),

        "missed_patients":
            analytics_service.missed_patients(
                db,
                clinic_id
            ),

        "retention":
            analytics_service.retention_rate(
                db,
                clinic_id
            ),

        "followups_today":
            analytics_service.followups_due_today(
                db,
                clinic_id
            ),

        "top_patients":
            analytics_service.top_patients(
                db,
                clinic_id,
                limit=5
            )
    }


# ─────────────────────────────────────────────────────
# DAILY REVENUE
# ─────────────────────────────────────────────────────

@router.get("/revenue/daily")
def get_daily_revenue(
    db: Session = Depends(get_db),

    # Revenue restriction
    current_user: User = Depends(
        block_receptionist_from_revenue
    ),

    plan_user: User = Depends(
        require_plan("starter")
    )
):
    """
    Starter+ can access daily revenue.
    """

    return analytics_service.daily_revenue(
        db,
        current_user.clinic_id
    )


# ─────────────────────────────────────────────────────
# MONTHLY REVENUE
# ─────────────────────────────────────────────────────

@router.get("/revenue/monthly")
def get_monthly_revenue(
    db: Session = Depends(get_db),

    # Revenue restriction
    current_user: User = Depends(
        block_receptionist_from_revenue
    ),

    plan_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Growth+ only.
    """

    return analytics_service.monthly_revenue(
        db,
        current_user.clinic_id
    )


# ─────────────────────────────────────────────────────
# MISSED PATIENTS
# ─────────────────────────────────────────────────────

@router.get("/missed-patients")
def get_missed_patients(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Growth+ only.
    """

    return analytics_service.missed_patients(
        db,
        current_user.clinic_id
    )


# ─────────────────────────────────────────────────────
# RETENTION
# ─────────────────────────────────────────────────────

@router.get("/retention")
def get_retention(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Growth+ only.
    """

    return analytics_service.retention_rate(
        db,
        current_user.clinic_id
    )


# ─────────────────────────────────────────────────────
# TOP PATIENTS
# ─────────────────────────────────────────────────────

@router.get("/top-patients")
def get_top_patients(
    limit: int = 10,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Growth+ only.
    """

    return analytics_service.top_patients(
        db,
        current_user.clinic_id,
        limit
    )


# ─────────────────────────────────────────────────────
# FOLLOWUPS TODAY
# ─────────────────────────────────────────────────────

@router.get("/followups/today")
def get_followups_today(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_plan("starter")
    )
):
    """
    Starter+ can access followups.
    """

    return analytics_service.followups_due_today(
        db,
        current_user.clinic_id
    )


# ─────────────────────────────────────────────────────
# SUMMARY TODAY
# Alias for Lovable frontend compatibility
# ─────────────────────────────────────────────────────

@router.get("/summary/today")
def summary_today(
    db: Session = Depends(get_db),

    # Revenue restriction
    current_user: User = Depends(
        block_receptionist_from_revenue
    ),

    # Starter+ can access
    plan_user: User = Depends(
        require_plan("starter")
    )
):
    """
    Alias for dashboard —
    frontend calls this endpoint.

    Starter+ only.
    """

    return analytics_service.get_full_dashboard(
        db,
        current_user.clinic_id
    )


# ─────────────────────────────────────────────────────
# EXPORT ANALYTICS
# ─────────────────────────────────────────────────────

@router.get("/export")
def export_analytics(
    db: Session = Depends(get_db),

    # Revenue restriction
    current_user: User = Depends(
        block_receptionist_from_revenue
    ),

    # Growth+ only
    plan_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Export analytics data.

    Growth plan and above only.
    """

    clinic_id = current_user.clinic_id

    return {
        "daily_revenue":
            analytics_service.daily_revenue(
                db,
                clinic_id
            ),

        "monthly_revenue":
            analytics_service.monthly_revenue(
                db,
                clinic_id
            ),

        "missed_patients":
            analytics_service.missed_patients(
                db,
                clinic_id
            ),

        "retention":
            analytics_service.retention_rate(
                db,
                clinic_id
            ),

        "followups_today":
            analytics_service.followups_due_today(
                db,
                clinic_id
            ),

        "top_patients":
            analytics_service.top_patients(
                db,
                clinic_id,
                limit=100
            )
    }