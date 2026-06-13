from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.reminder import (
    FollowupReminder
)

from app.models.patient import Patient

from app.services.whatsapp_service import (
    send_followup_reminder
)

import asyncio


# =====================================================
# CREATE FOLLOWUP
# =====================================================

def create_followup(

    db: Session,

    clinic_id: str,

    patient_id: str,

    visit_id: str,

    followup_date
):

    reminder = FollowupReminder(

        clinic_id=clinic_id,

        patient_id=patient_id,

        visit_id=visit_id,

        followup_date=followup_date
    )

    db.add(reminder)

    db.commit()

    db.refresh(reminder)

    return reminder


# =====================================================
# SEND DUE FOLLOWUPS
# =====================================================

def send_due_followups(
    db: Session
):

    now = datetime.utcnow()

    reminders = db.query(
        FollowupReminder
    ).filter(
        FollowupReminder.followup_date <= now,
        FollowupReminder.reminder_24h_sent == False
    ).all()

    for reminder in reminders:

        patient = db.query(Patient).filter(
            Patient.id == reminder.patient_id
        ).first()

        if not patient:
            continue

        if not patient.phone_mobile:
            continue

        try:

            asyncio.run(

                send_followup_reminder(

                    phone=patient.phone_mobile,

                    patient_name=(
                        f"{patient.first_name} "
                        f"{patient.last_name or ''}"
                    ).strip(),

                    clinic_name="Vennova Clinic",

                    reminder_date=str(
                        reminder.followup_date.date()
                    )
                )
            )

            reminder.reminder_24h_sent = True

            db.commit()

        except Exception as e:

            print(
                "Followup send failed:",
                str(e)
            )