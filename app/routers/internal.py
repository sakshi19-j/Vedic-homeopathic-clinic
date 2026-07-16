from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["Internal"])

@router.post("/run-reminders")
def run_reminders_endpoint(
    x_cron_secret: str = Header(None),
    db: Session = Depends(get_db)
):
    if x_cron_secret != settings.CRON_SECRET:
        raise HTTPException(403, "Forbidden")

    from app.jobs.reminder_cron import _job_daily_reminders
    import asyncio
    asyncio.run(_job_daily_reminders(db))
    logger.info("✅ /internal/run-reminders executed via Railway Cron")
    return {"status": "executed"}