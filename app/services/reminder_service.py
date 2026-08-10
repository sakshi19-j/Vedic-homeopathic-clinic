import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.models.reminder import (
    FollowUp,
    FollowUpStatus,
    FollowUpType,
    Channel as ReminderChannel
)

from app.models.patient import Patient
from app.models.clinic import Clinic

import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

OVERDUE_CUTOFF_DAYS = 0


# =====================================================
# TEMPLATE KEY
# =====================================================

def get_template_key(followup_type: FollowUpType) -> str:

    mapping = {
        FollowUpType.THREE_DAY:   "followup_reminder",
        FollowUpType.SEVEN_DAY:   "followup_reminder",
        FollowUpType.FIFTEEN_DAY: "followup_reminder",
        FollowUpType.MONTHLY:     "followup_reminder",
        FollowUpType.CUSTOM:      "followup_reminder",
    }

    return mapping.get(
        followup_type,
        "followup_reminder"
    )


# =====================================================
# AUTO SCHEDULE FOLLOWUPS
# =====================================================

def schedule_followups_after_visit(
    db,
    visit_id,
    patient_id,
    clinic_id,
    followup_date,
    followup_type
):
    if not followup_date:
        return {
            "scheduled": 0
        }
    
    reminder_dates = [

        (
            followup_date - timedelta(days=3),
            followup_type
        ),

        (
            followup_date,
            followup_type
        )

    ]
    reminder_dates = [
        (followup_date - timedelta(days=3), followup_type),
        (followup_date - timedelta(days=1), followup_type),   # 24hr reminder
    ]

    for due_date, reminder_type in reminder_dates:
        existing = db.query(FollowUp).filter(
            FollowUp.visit_id == visit_id,
            FollowUp.type == reminder_type,
            FollowUp.due_date == due_date
        ).first()

        if existing:
            continue
        followup = FollowUp(
            clinic_id=clinic_id,
            patient_id=patient_id,
            visit_id=visit_id,
            due_date=due_date,
            type=reminder_type,
            status=FollowUpStatus.PENDING,
            channel=ReminderChannel.WHATSAPP
        )

        db.add(followup)

    db.commit()

    return {
        "scheduled": len(reminder_dates)
    }
# =====================================================
# GET DUE REMINDERS
# =====================================================

def get_due_reminders(
    db: Session,
    clinic_id: str,
    target_date: date = None
) -> list:

    if not target_date:
        target_date = datetime.now(IST).date()

    cutoff_date = target_date - timedelta(
        days=OVERDUE_CUTOFF_DAYS
    )

    followups = (
        db.query(FollowUp)
        .options(
            joinedload(FollowUp.patient),
            joinedload(FollowUp.visit)
        )
        .filter(
            and_(
                FollowUp.clinic_id == clinic_id,
                FollowUp.status == FollowUpStatus.PENDING,
                FollowUp.due_date >= datetime(
                    cutoff_date.year,
                    cutoff_date.month,
                    cutoff_date.day
                ),
                FollowUp.due_date <= datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    23,
                    59,
                    59
                )
            )
        )
        .all()
    )

    clinic = db.query(Clinic).filter(
        Clinic.id == clinic_id
    ).first()

    result = []

    for f in followups:

        patient = f.patient

        if not patient:
            continue

        if getattr(patient, "whatsapp_opted_out", False):
            continue

        result.append({
            "followup_id": str(f.id),
            "patient_id": str(patient.id),
            "clinic_id": str(f.clinic_id),
            "patient_name":
                f"{patient.first_name} "
                f"{patient.last_name or ''}".strip(),
            "phone": patient.phone_mobile,
            "language": patient.language_pref or "en",
            "channel":
                f.channel.value if f.channel else "WHATSAPP",
            "type":
                f.type.value if f.type else None,
            "due_date":
                f.due_date.strftime("%d-%m-%Y")
                if f.due_date else None,
            "template_key": get_template_key(f.type),
            "template_vars": [
                patient.first_name,
                clinic.name if clinic else "Vedic Homeopathic Clinic",
                f.due_date.strftime("%d-%m-%Y")
                if f.due_date else ""
            ]
        })

    return result


# =====================================================
# GET TODAY REMINDERS
# =====================================================

def get_todays_reminders(
    db: Session,
    clinic_id: str
) -> list:

    today = datetime.now(IST).date()

    today_start = datetime(
        today.year,
        today.month,
        today.day,
        0,
        0,
        0
    )

    today_end = datetime(
        today.year,
        today.month,
        today.day,
        23,
        59,
        59
    )

    followups = (
        db.query(FollowUp)
        .options(joinedload(FollowUp.patient))
        .filter(
            FollowUp.clinic_id == clinic_id,
            FollowUp.status.in_([
                FollowUpStatus.PENDING,
                FollowUpStatus.SENT,
            ]),
            FollowUp.due_date >= today_start,
            FollowUp.due_date <= today_end,
        )
        .order_by(FollowUp.due_date.asc())
        .all()
    )

    result = []

    for f in followups:

        patient = f.patient

        result.append({
            "followup_id": str(f.id),
            "patient_id":
                str(patient.id) if patient else None,
            "patient_name":
                f"{patient.first_name} "
                f"{patient.last_name or ''}".strip()
                if patient else "Unknown",
            "patient_phone":
                patient.phone_mobile if patient else None,
            "followup_type":
                f.type.value if f.type else None,
            "due_date":
                f.due_date.strftime("%Y-%m-%d")
                if f.due_date else None,
            "status":
                f.status.value if f.status else "PENDING",
            "channel":
                f.channel.value if f.channel else "WHATSAPP",
            "sent_at":
                f.sent_at.isoformat() if f.sent_at else None,
        })

    return result


# =====================================================
# SEND DUE REMINDERS
# =====================================================

async def send_due_reminders_async(
    db: Session,
    clinic_id: str
) -> dict:

    from app.services.whatsapp_service import (
         send_followup_reminder
    )

    due     = get_due_reminders(db, clinic_id)
    sent    = 0
    failed  = 0
    skipped = 0

    for reminder in due:

        phone = reminder.get("phone", "")

        if not phone:
            skipped += 1
            continue

        try:

            result = await send_followup_reminder(
                phone          = phone,
                patient_name   = reminder["template_vars"][0],
                clinic_name    = reminder["template_vars"][1],
                reminder_date  = reminder["template_vars"][2],
                followup_type  = reminder.get("type", ""),
                language       = reminder.get("language", "en"),
                db             = db,
                clinic_id      = reminder.get("clinic_id") or str(reminder.get("clinic_id") or ""),
                patient_id     = reminder.get("patient_id"),
                trigger        = reminder.get("type", "followup_reminder")
            )

            followup = db.query(FollowUp).filter(
                FollowUp.id == reminder["followup_id"]
            ).first()

            if followup:

                if result.get("status") in (
                    "sent",
                    "mocked"
                ):

                    followup.status    = FollowUpStatus.SENT
                    followup.sent_at   = datetime.now(IST)
                    followup.message_id = result.get("message_id")
                    followup.response   = str(result.get(
                        "response",
                        result.get("message_id", "")
                    ))

                    sent += 1

                else:

                    followup.status    = FollowUpStatus.FAILED
                    followup.message_id = None
                    followup.response   = str(result.get(
                        "error",
                        "unknown"
                    ))

                    failed += 1

                db.add(followup)
                visit = followup.visit

                if visit and result.get("status") in ("sent", "mocked"):
                    visit.followup_reminder_sent = True
                    db.add(visit)

                db.commit()

        except Exception as e:

            logger.error(
                f"Send failed for "
                f"{reminder['followup_id']}: {e}"
            )

            failed += 1

    return {
        "date": datetime.now(IST).strftime("%d-%m-%Y"),
        "total_due": len(due),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
    }


# =====================================================
# SYNC WRAPPER
# =====================================================

def send_due_reminders(
    db: Session,
    clinic_id: str
) -> dict:

    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(
            send_due_reminders_async(
                db,
                clinic_id
            )
        )

    finally:
        loop.close()


# =====================================================
# SEND SINGLE REMINDER
# =====================================================

async def send_single_reminder(
    db: Session,
    followup_id: str,
    clinic_id: str
) -> dict:

    from app.services.whatsapp_service import (
        send_followup_reminder
    )

    followup = db.query(FollowUp).filter(
        FollowUp.id == followup_id,
        FollowUp.clinic_id == clinic_id
    ).first()

    if not followup:

        from fastapi import HTTPException

        raise HTTPException(
            404,
            "Follow-up not found"
        )

    patient = db.query(Patient).filter(
        Patient.id == followup.patient_id
    ).first()

    clinic = db.query(Clinic).filter(
        Clinic.id == clinic_id
    ).first()

    if not patient or not patient.phone_mobile:

        from fastapi import HTTPException

        raise HTTPException(
            400,
            "Patient has no phone number"
        )

    if getattr(patient, "whatsapp_opted_out", False):

        from fastapi import HTTPException

        raise HTTPException(
            400,
            "Patient opted out"
        )
    try:

        result = await send_followup_reminder(
            phone         = patient.phone_mobile,
            patient_name  = patient.first_name,
            clinic_name   = clinic.name if clinic else "Vedic Homeopathic Clinic",
            reminder_date = (
                followup.due_date.strftime("%d-%m-%Y")
                if followup.due_date else ""
            ),
            followup_type = followup.type.value if followup.type else "",
            language      = patient.language_pref or "en",
            db            = db,
            clinic_id     = str(clinic_id),
            patient_id    = str(patient.id),
            trigger       = followup.type.value if followup.type else "followup_reminder"
        )

        print(f"REMINDER SEND RESULT: {result}")

    except Exception as e:

        import traceback

        print(f"REMINDER SEND EXCEPTION: {traceback.format_exc()}")

        print(traceback.format_exc())

        return {
            "status": "failed",
            "error": str(e)
        }
    if result.get("status") in ("sent", "mocked"):

        followup.status     = FollowUpStatus.SENT
        followup.sent_at    = datetime.now(IST)
        followup.message_id = result.get("message_id")
        followup.response   = str(result.get(
            "response",
            result.get("message_id", "")
        ))

        if followup.visit:
            followup.visit.followup_reminder_sent = True
            db.add(followup.visit)

        db.add(followup)
        db.commit()

    else:

        followup.status     = FollowUpStatus.FAILED
        followup.message_id = None
        followup.response   = str(result.get(
            "error",
            "unknown"
        ))

        db.add(followup)
        db.commit()

    return {
        "status": result.get("status"),
        "patient_name":
            f"{patient.first_name} "
            f"{patient.last_name or ''}".strip(),
        "phone": patient.phone_mobile,
        "followup_id": followup_id,
        "meta_response": result
    }


# =====================================================
# MARK REMINDER SENT
# =====================================================

def mark_reminder_sent(
    db: Session,
    followup_id: str,
    clinic_id: str
) -> dict:

    followup = db.query(FollowUp).filter(
        FollowUp.id == followup_id,
        FollowUp.clinic_id == clinic_id
    ).first()

    if not followup:

        from fastapi import HTTPException

        raise HTTPException(
            404,
            "Reminder not found"
        )

    followup.status  = FollowUpStatus.SENT
    followup.sent_at = datetime.now(IST)

    db.commit()

    return {
        "message": "Marked as sent",
        "followup_id": followup_id
    }


# =====================================================
# MARK REMINDER DONE
# =====================================================

def mark_reminder_done(
    db: Session,
    followup_id: str,
    clinic_id: str
) -> dict:

    followup = db.query(FollowUp).filter(
        FollowUp.id == followup_id,
        FollowUp.clinic_id == clinic_id
    ).first()

    if not followup:

        from fastapi import HTTPException

        raise HTTPException(
            404,
            "Reminder not found"
        )

    followup.status = FollowUpStatus.DONE

    db.commit()

    return {
        "message": "Marked as done",
        "followup_id": followup_id
    }
