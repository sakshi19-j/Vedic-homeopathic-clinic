from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime

from app.database import get_db
from app.services import reminder_service
from app.middleware.auth_middleware import (
    get_current_user,
    receptionist_or_doctor
)
from app.middleware.auth_middleware import CurrentUser
from app.models.patient import Patient
from app.schemas.reminder import FollowUpCreate

router = APIRouter(prefix="/reminders", tags=["Reminders"])


# =====================================================
# TODAY'S REMINDERS — frontend reminders tab
# =====================================================

@router.get("/today")
def get_todays_reminders(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    """
    All follow-ups due today — for reception reminders tab.
    Returns PENDING + SENT (sent today).
    """
    reminders = reminder_service.get_todays_reminders(
        db,
        current_user.clinic_id
    )

    return {
        "date": str(date.today()),
        "total": len(reminders),
        "reminders": reminders
    }


# =====================================================
# SEND SINGLE REMINDER MANUALLY
# Reception "Send" button on reminders tab
# =====================================================

@router.post("/{followup_id}/send")
async def send_reminder(
    followup_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    """
    Manually send a WhatsApp follow-up for a specific follow-up.
    Uses approved Meta template: followup_reminde
    """
    return await reminder_service.send_single_reminder(
        db=db,
        followup_id=followup_id,
        clinic_id=current_user.clinic_id
    )


# =====================================================
# GET DUE REMINDERS (for external/cron use)
# =====================================================

@router.get("/due")
def get_due_reminders(
    target_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    return {
        "clinic_id": current_user.clinic_id,
        "date": str(target_date or date.today()),
        "reminders": reminder_service.get_due_reminders(
            db,
            current_user.clinic_id,
            target_date
        )
    }


# =====================================================
# SEND TODAY'S REMINDERS (manual trigger)
# =====================================================

@router.post("/send-today")
def send_todays_reminders(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    """
    Manually trigger today's reminders.
    Cron job calls this automatically at 9:30 AM.
    """
    return reminder_service.send_due_reminders(
        db,
        current_user.clinic_id
    )


# =====================================================
# MARK REMINDER SENT
# =====================================================

@router.put("/{followup_id}/mark-sent")
def mark_sent(
    followup_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    return reminder_service.mark_reminder_sent(
        db,
        followup_id,
        current_user.clinic_id
    )


# =====================================================
# MARK REMINDER DONE
# =====================================================

@router.put("/{followup_id}/mark-done")
def mark_done(
    followup_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    return reminder_service.mark_reminder_done(
        db,
        followup_id,
        current_user.clinic_id
    )


# =====================================================
# SCHEDULE MANUAL FOLLOWUP
# =====================================================

@router.post("/schedule")
def schedule_followup(
    data: FollowUpCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    from app.models.reminder import (
        FollowUp,
        FollowUpStatus,
        FollowUpType,
        Channel as ReminderChannel
    )

    patient_id = data.patient_id
    due_date = data.due_date
    ftype = data.type

    if not patient_id or not due_date:
        raise HTTPException(
            status_code=400,
            detail="patient_id and due_date required"
        )

    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    followup = FollowUp(
        clinic_id=current_user.clinic_id,
        patient_id=patient_id,
        due_date=due_date,
        type=(
            FollowUpType[ftype.upper()]
            if ftype.upper() in FollowUpType.__members__
            else FollowUpType.CUSTOM
        ),
        status=FollowUpStatus.PENDING,
        channel=ReminderChannel.WHATSAPP
    )

    db.add(followup)
    db.commit()
    db.refresh(followup)

    return {
        "message": "Followup scheduled",
        "followup_id": str(followup.id),
        "patient": f"{patient.first_name} {patient.last_name or ''}".strip(),
        "due_date": due_date
    }


# =====================================================
# FOLLOWUP STATS
# =====================================================

@router.get("/stats")
def get_followup_stats(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    from app.models.reminder import FollowUp, FollowUpStatus
    from sqlalchemy import func

    def count(status):
        return db.query(FollowUp).filter(
            FollowUp.clinic_id == current_user.clinic_id,
            FollowUp.status == status
        ).count()

    today = datetime.utcnow().date()

    due_today = db.query(FollowUp).filter(
        FollowUp.clinic_id == current_user.clinic_id,
        FollowUp.status == FollowUpStatus.PENDING,
        func.date(FollowUp.due_date) <= today
    ).count()

    return {
        "pending": count(FollowUpStatus.PENDING),
        "sent": count(FollowUpStatus.SENT),
        "done": count(FollowUpStatus.DONE),
        "skipped": count(FollowUpStatus.SKIPPED),
        "failed": count(FollowUpStatus.FAILED),
        "due_today": due_today
    }


# =====================================================
# GET PATIENT REMINDERS
# =====================================================

@router.get("/patient/{patient_id}")
def get_patient_reminders(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(receptionist_or_doctor)
):
    from app.models.reminder import FollowUp

    followups = db.query(FollowUp).filter(
        FollowUp.patient_id == patient_id,
        FollowUp.clinic_id == current_user.clinic_id
    ).order_by(FollowUp.due_date).all()

    return {
        "patient_id": patient_id,
        "total": len(followups),
        "reminders": [
            {
                "id": str(f.id),
                "type": f.type.value if f.type else None,
                "due_date": (
                    f.due_date.strftime("%d-%m-%Y")
                    if f.due_date else None
                ),
                "status": f.status.value if f.status else None,
                "channel": f.channel.value if f.channel else None,
                "sent_at": (
                    f.sent_at.strftime("%d-%m-%Y %H:%M")
                    if f.sent_at else None
                ),
            }
            for f in followups
        ]
    }