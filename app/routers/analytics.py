from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics_service
from app.middleware.auth_middleware import (
    require_plan,
    block_receptionist_from_revenue,
    check_subscription_with_grace
)
from app.models.user import User


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)
from app.middleware.auth_middleware import (
    receptionist_or_doctor
)

# ─────────────────────────────────────────────
# FULL DASHBOARD
# ─────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(check_subscription_with_grace)
):
    clinic_id = current_user.clinic_id

    return {
        "revenue": {
            "today":        analytics_service.daily_revenue(db, clinic_id),
            "this_week":    analytics_service.weekly_revenue(db, clinic_id),
            "this_month":   analytics_service.monthly_revenue(db, clinic_id),
        },
        "patients": {
            "missed":       analytics_service.missed_patients(db, clinic_id),
            "retention":    analytics_service.retention_rate(db, clinic_id),
            "top":          analytics_service.top_patients(db, clinic_id, limit=5),
        },
        "clinical": {
            "top_diseases":         analytics_service.top_diseases(db, clinic_id),
            "followups_due_today":  analytics_service.followups_due_today(db, clinic_id),
        },
        "whatsapp":     analytics_service.whatsapp_delivery_rate(db, clinic_id),
        "intelligence": analytics_service.revenue_lost_estimate(db, clinic_id)
    }


# ─────────────────────────────────────────────
# SUMMARY TODAY
# Alias for Lovable frontend — /analytics/summary/today
# ─────────────────────────────────────────────

@router.get("/summary/today")
def summary_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(check_subscription_with_grace)
):
    """
    Lightweight summary for frontend dashboard widgets.
    Starter+ access.
    """
    clinic_id = current_user.clinic_id

    return {
        "daily_revenue":    analytics_service.daily_revenue(db, clinic_id),
        "missed_patients":  analytics_service.missed_patients(db, clinic_id),
        "retention":        analytics_service.retention_rate(db, clinic_id),
        "followups_today":  analytics_service.followups_due_today(db, clinic_id),
        "top_patients":     analytics_service.top_patients(db, clinic_id, limit=5)
    }


# ─────────────────────────────────────────────
# REVENUE — DAILY
# ─────────────────────────────────────────────

@router.get("/revenue/daily")
def get_daily_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(require_plan("starter"))
):
    return analytics_service.daily_revenue(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# REVENUE — WEEKLY (last 7 days breakdown)
# ─────────────────────────────────────────────

@router.get("/revenue/weekly")
def get_weekly_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(require_plan("growth"))
):
    return analytics_service.weekly_revenue(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# REVENUE — MONTHLY
# ─────────────────────────────────────────────

@router.get("/revenue/monthly")
def get_monthly_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(require_plan("growth"))
):
    return analytics_service.monthly_revenue(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# REVENUE LOST ESTIMATE
# ─────────────────────────────────────────────

@router.get("/revenue/lost-estimate")
def get_revenue_lost(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(require_plan("growth"))
):
    return analytics_service.revenue_lost_estimate(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# MISSED PATIENTS
# ─────────────────────────────────────────────

@router.get("/patients/missed")
def get_missed_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("growth"))
):
    return analytics_service.missed_patients(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# RETENTION RATE
# ─────────────────────────────────────────────

@router.get("/patients/retention")
def get_retention(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("growth"))
):
    return analytics_service.retention_rate(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# TOP PATIENTS
# ─────────────────────────────────────────────

@router.get("/patients/top")
def get_top_patients(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("growth"))
):
    return analytics_service.top_patients(db, current_user.clinic_id, limit)


# ─────────────────────────────────────────────
# TOP DISEASES
# ─────────────────────────────────────────────

@router.get("/diseases/top")
def get_top_diseases(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("growth"))
):
    return analytics_service.top_diseases(db, current_user.clinic_id, limit)


# ─────────────────────────────────────────────
# FOLLOWUPS DUE TODAY
# ─────────────────────────────────────────────

@router.get("/followups/today")
def get_followups_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("starter"))
):
    return analytics_service.followups_due_today(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# WHATSAPP DELIVERY RATE
# ─────────────────────────────────────────────

@router.get("/whatsapp/delivery")
def get_whatsapp_delivery(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("growth"))
):
    return analytics_service.whatsapp_delivery_rate(db, current_user.clinic_id)


# ─────────────────────────────────────────────
# EXPORT — full data dump
# ─────────────────────────────────────────────

@router.get("/export")
def export_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue),
    _: User = Depends(require_plan("growth"))
):
    clinic_id = current_user.clinic_id

    return {
        "revenue": {
            "today":        analytics_service.daily_revenue(db, clinic_id),
            "this_week":    analytics_service.weekly_revenue(db, clinic_id),
            "this_month":   analytics_service.monthly_revenue(db, clinic_id),
        },
        "patients": {
            "missed":       analytics_service.missed_patients(db, clinic_id),
            "retention":    analytics_service.retention_rate(db, clinic_id),
            "top":          analytics_service.top_patients(db, clinic_id, limit=100),
        },
        "clinical": {
            "top_diseases":         analytics_service.top_diseases(db, clinic_id),
            "followups_due_today":  analytics_service.followups_due_today(db, clinic_id),
        },
        "whatsapp":     analytics_service.whatsapp_delivery_rate(db, clinic_id),
        "intelligence": analytics_service.revenue_lost_estimate(db, clinic_id)
    }

# ─────────────────────────────────────────────
# REVENUE — combined endpoint for frontend
# ─────────────────────────────────────────────
@router.get("/revenue")
def get_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(block_receptionist_from_revenue)
):
    clinic_id = current_user.clinic_id
    return {
        "today":   analytics_service.daily_revenue(db, clinic_id),
        "weekly":  analytics_service.weekly_revenue(db, clinic_id),
        "monthly": analytics_service.monthly_revenue(db, clinic_id),
    }

@router.get("/dashboard-lite")
def dashboard_lite(
    db: Session = Depends(get_db),
    current_user = Depends(receptionist_or_doctor)
):
    return {
        "message": "dashboard lite"
    }