from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import receptionist_or_doctor
from app.models.user import User
from app.models.reminder import FollowUp

from datetime import date
from sqlalchemy import func
router = APIRouter(
    prefix="/followups",
    tags=["Followups"]
)


@router.get("/today")
def followups_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):

    today = date.today()

    followups = db.query(FollowUp).filter(
        FollowUp.clinic_id == current_user.clinic_id,
        func.date(FollowUp.followup_date) == today
    ).all()

    return followups


@router.get("/upcoming")
def followups_upcoming(
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):

    today = date.today()

    followups = db.query(FollowUp).filter(
        FollowUp.clinic_id == current_user.clinic_id,
        func.date(FollowUp.followup_date) > today
    ).all()

    return followups