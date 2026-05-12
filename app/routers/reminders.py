from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date, datetime

from app.database import get_db
from app.services import reminder_service

from app.middleware.auth_middleware import (
    get_current_user,
    receptionist_or_doctor
)

from app.models.user import User
from app.models.patient import Patient

router = APIRouter(
    prefix="/reminders",
    tags=["Reminders"]
)


# =========================================================
# Get Due Reminders
# =========================================================

@router.get("/due")
def get_due_reminders(
    target_date: Optional[date] = Query(
        None,
        description="Date to fetch reminders for. Defaults to today."
    ),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Get all pending reminders due on a date.
    YOUR EXTERNAL REMINDER APP calls this endpoint daily.
    Returns patient name, phone, language, message — ready to send.
    """

    return {
        "clinic_id": current_user.clinic_id,
        "date": str(target_date or date.today()),
        "reminders": reminder_service.get_due_reminders(
            db,
            current_user.clinic_id,
            target_date
        )
    }


# =========================================================
# Send Today's Reminders
# =========================================================

@router.post("/send-today")
def send_todays_reminders(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Manually trigger today's reminders.
    Cron job calls this automatically at 9:30 AM.
    Receptionist can also trigger manually from dashboard.
    """

    return reminder_service.send_due_reminders(
        db,
        current_user.clinic_id
    )


# =========================================================
# Mark Reminder Sent
# =========================================================

@router.put("/{followup_id}/mark-sent")
def mark_sent(
    followup_id: str,
    db:          Session = Depends(get_db),
    current_user: User   = Depends(receptionist_or_doctor)
):
    """
    Mark reminder as sent.
    External reminder app calls this after sending WhatsApp.
    """

    return reminder_service.mark_reminder_sent(
        db,
        followup_id
    )


# =========================================================
# Mark Reminder Done
# =========================================================

@router.put("/{followup_id}/mark-done")
def mark_done(
    followup_id: str,
    db:          Session = Depends(get_db),
    current_user: User   = Depends(receptionist_or_doctor)
):
    """
    Patient confirmed or returned — mark as done
    """

    return reminder_service.mark_reminder_done(
        db,
        followup_id
    )


# =========================================================
# Get Patient Reminders
# =========================================================

@router.get("/patient/{patient_id}")
def get_patient_reminders(
    patient_id:   str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """All reminders for a specific patient"""

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
                "id": f.id,
                "type": (
                    f.type.value if f.type else None
                ),
                "due_date": (
                    f.due_date.strftime("%d-%m-%Y")
                    if f.due_date else None
                ),
                "status": (
                    f.status.value if f.status else None
                ),
                "channel": (
                    f.channel.value if f.channel else None
                ),
                "sent_at": (
                    f.sent_at.strftime("%d-%m-%Y %H:%M")
                    if f.sent_at else None
                )
            }
            for f in followups
        ]
    }


# =========================================================
# Get All Followups
# =========================================================

@router.get("/followups")
def get_all_followups(
    status:      Optional[str] = None,
    limit:       int           = 50,
    page:        int           = 1,
    db:          Session       = Depends(get_db),
    current_user: User         = Depends(receptionist_or_doctor)
):
    """
    All followups for clinic with optional status filter.

    Status:
    PENDING / SENT / DONE / SKIPPED / FAILED
    """

    from app.models.reminder import (
        FollowUp,
        FollowUpStatus
    )

    query = db.query(FollowUp).filter(
        FollowUp.clinic_id == current_user.clinic_id
    )

    if status:
        query = query.filter(
            FollowUp.status == status.upper()
        )

    total = query.count()

    offset = (page - 1) * limit

    followups = query.order_by(
        FollowUp.due_date.asc()
    ).offset(offset).limit(limit).all()

    result = []

    for f in followups:

        patient = db.query(Patient).filter(
            Patient.id == f.patient_id
        ).first()

        result.append({
            "id": f.id,
            "patient_id": f.patient_id,
            "patient_name": (
                f"{patient.first_name} {patient.last_name or ''}".strip()
                if patient else "Unknown"
            ),
            "patient_phone": (
                patient.phone_mobile if patient else None
            ),
            "type": (
                f.type.value if f.type else None
            ),
            "due_date": (
                f.due_date.strftime("%d-%m-%Y")
                if f.due_date else None
            ),
            "status": (
                f.status.value if f.status else None
            ),
            "channel": (
                f.channel.value if f.channel else None
            ),
            "sent_at": (
                f.sent_at.strftime("%d-%m-%Y %H:%M")
                if f.sent_at else None
            ),
            "response": f.response,
            "days_overdue": (
                (
                    datetime.utcnow().date()
                    - f.due_date.date()
                ).days
                if (
                    f.due_date
                    and f.due_date.date() < datetime.utcnow().date()
                )
                else 0
            )
        })

    return {
        "total": total,
        "page": page,
        "followups": result
    }


# =========================================================
# Followup Stats
# =========================================================

@router.get("/stats")
def get_followup_stats(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Followup counts by status — for dashboard widget.
    """

    from app.models.reminder import (
        FollowUp,
        FollowUpStatus
    )

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


# =========================================================
# Schedule Manual Followup
# =========================================================

@router.post("/schedule")
def schedule_followup(
    data:         dict,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Manually schedule a followup for a patient.

    Body:
    {
        patient_id,
        due_date (YYYY-MM-DD),
        type,
        notes
    }
    """

    from app.models.reminder import (
        FollowUp,
        FollowUpStatus,
        FollowUpType,
        ReminderChannel
    )

    patient_id = data.get("patient_id")
    due_date = data.get("due_date")
    ftype = data.get("type", "MANUAL")

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
        clinic_id  = current_user.clinic_id,
        patient_id = patient_id,
        due_date   = datetime.strptime(
            due_date,
            "%Y-%m-%d"
        ),
        type       = (
            FollowUpType[ftype.upper()]
            if ftype.upper() in FollowUpType.__members__
            else FollowUpType.MANUAL
        ),
        status     = FollowUpStatus.PENDING,
        channel    = ReminderChannel.WHATSAPP,
        notes      = data.get("notes", "")
    )

    db.add(followup)

    db.commit()
    db.refresh(followup)

    return {
        "message": "Followup scheduled",
        "followup_id": followup.id,
        "patient": (
            f"{patient.first_name} {patient.last_name or ''}".strip()
        ),
        "due_date": due_date
    }