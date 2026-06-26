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

    from sqlalchemy.orm import joinedload

    followups = (
        db.query(FollowUp)
        .options(joinedload(FollowUp.patient))
        .filter(
            FollowUp.clinic_id == current_user.clinic_id,
            func.date(FollowUp.due_date) <= today
        )
        .all()
    )

    result = []

    for f in followups:

        patient = f.patient

        result.append({
            "id": str(f.id),
            "patient_id": str(f.patient_id),
            "patient_name": (
                f"{patient.first_name} {patient.last_name or ''}".strip()
                if patient else "Unknown"
            ),
            "patient_phone": (
                patient.phone_mobile
                if patient else None
            ),
            "status": (
                f.status.value
                if f.status else None
            ),
            "type": (
                f.type.value
                if f.type else None
            ),
            "channel": (
                f.channel.value
                if f.channel else None
            ),
            "due_date": (
                f.due_date.strftime("%Y-%m-%d")
                if f.due_date else None
            )
        })

    return result


@router.get("/upcoming")
def followups_upcoming(
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):

    today = date.today()

    from sqlalchemy.orm import joinedload

    followups = (
        db.query(FollowUp)
        .options(joinedload(FollowUp.patient))
        .filter(
            FollowUp.clinic_id == current_user.clinic_id,
            func.date(FollowUp.due_date) > today
        )
        .all()
    )

    result = []

    for f in followups:

        patient = f.patient

        result.append({
            "id": str(f.id),
            "patient_id": str(f.patient_id),
            "patient_name": (
                f"{patient.first_name} {patient.last_name or ''}".strip()
                if patient else "Unknown"
            ),
            "patient_phone": (
                patient.phone_mobile
                if patient else None
            ),
            "status": (
                f.status.value
                if f.status else None
            ),
            "type": (
                f.type.value
                if f.type else None
            ),
            "channel": (
                f.channel.value
                if f.channel else None
            ),
            "due_date": (
                f.due_date.strftime("%Y-%m-%d")
                if f.due_date else None
            )
        })

    return result