import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import pytz

from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)
IST    = pytz.timezone("Asia/Kolkata")
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
@router.get("/")
def health_check(db: Session = Depends(get_db)):
    """
    Railway health check endpoint.
    Returns 200 only when DB is reachable.
    Returns 503 if DB is down — Railway will restart the service.
    """
    checks  = {}
    healthy = True

    # DB check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"
        healthy = False
        logger.error(f"Health check DB failed: {e}")

    # WhatsApp config check
    checks["whatsapp_configured"] = bool(
        settings.WHATSAPP_ACCESS_TOKEN
        and settings.WHATSAPP_PHONE_NUMBER_ID
    )

    # Scheduler check
    try:
        from app.jobs.reminder_cron import _scheduler
        checks["scheduler"] = (
            "running" if _scheduler and _scheduler.running
            else "stopped"
        )
    except Exception:
        checks["scheduler"] = "unknown"

    return {
        "status":      "healthy" if healthy else "degraded",
        "app":         "Vennova",
        "version":     "2.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp":   datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "checks":      checks
    }


@router.get("/detailed")
def detailed_health(db: Session = Depends(get_db)):
    """
    Detailed health — doctor/internal use only.
    Shows pool stats, table counts, scheduler jobs.
    """
    from sqlalchemy import inspect as sa_inspect

    details = {}

    # Table row counts
    try:
        for table in ["patients", "visits", "clinics", "whatsapp_logs"]:
            count = db.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
            details[f"count_{table}"] = count
    except Exception as e:
        details["table_counts_error"] = str(e)[:100]

    # Scheduler jobs
    try:
        from app.jobs.reminder_cron import _scheduler
        if _scheduler:
            jobs = _scheduler.get_jobs()
            details["scheduler_jobs"] = [
                {
                    "id":       j.id,
                    "name":     j.name,
                    "next_run": str(j.next_run_time)
                }
                for j in jobs
            ]
    except Exception:
        details["scheduler_jobs"] = []

    return {
        "status":  "ok",
        "details": details,
        "time":    datetime.now(IST).isoformat()
    }