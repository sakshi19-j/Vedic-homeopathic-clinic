import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.models.reminder import FollowUp, FollowUpStatus, FollowUpType, Channel as ReminderChannel
from app.models.patient import Patient
from app.models.clinic import Clinic
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

OVERDUE_CUTOFF_DAYS = 1


def get_template_key(followup_type: FollowUpType) -> str:
    mapping = {
        FollowUpType.THREE_DAY:   "followup_3d",
        FollowUpType.SEVEN_DAY:   "followup_7d",
        FollowUpType.FIFTEEN_DAY: "followup_15d",
        FollowUpType.MONTHLY:     "followup_monthly",
        FollowUpType.CUSTOM:      "followup_7d",
    }
    return mapping.get(followup_type, "followup_7d")


# =====================================================
# AUTO-SCHEDULE FOLLOW-UPS AFTER VISIT CLOSE
# Called from visit_service.close_visit()
# Creates 3-day, 7-day, 15-day follow-up rows
# APScheduler picks them up at 9:30 AM on due date
# =====================================================

def schedule_followups_after_visit(
    db:         Session,
    visit_id:   str,
    patient_id: str,
    clinic_id:  str
) -> dict:
    """
    Auto-creates 3 follow-up reminders after visit is closed.
    Schedules: 3-day, 7-day, 15-day from today.
    APScheduler sends WhatsApp automatically on due date at 9:30 AM.
    """
    try:
        today = datetime.now(IST).date()

        followup_schedule = [
            (FollowUpType.THREE_DAY,   3),
            (FollowUpType.SEVEN_DAY,   7),
            (FollowUpType.FIFTEEN_DAY, 15),
        ]

        created = []
        for ftype, days in followup_schedule:
            due_date = today + timedelta(days=days)

            # Avoid duplicate — check if same type already exists for this visit
            existing = db.query(FollowUp).filter(
                FollowUp.visit_id   == visit_id,
                FollowUp.type       == ftype,
                FollowUp.clinic_id  == clinic_id,
                FollowUp.status     == FollowUpStatus.PENDING
            ).first()

            if existing:
                logger.info(f"Follow-up {ftype.value} already exists for visit {visit_id} — skipping")
                continue

            followup = FollowUp(
                clinic_id  = clinic_id,
                patient_id = patient_id,
                visit_id   = visit_id,
                type       = ftype,
                due_date   = datetime(due_date.year, due_date.month, due_date.day, 9, 30),
                status     = FollowUpStatus.PENDING,
                channel    = ReminderChannel.WHATSAPP,
            )
            db.add(followup)
            created.append({
                "type":     ftype.value,
                "due_date": str(due_date)
            })

        db.commit()

        logger.info(
            f"Scheduled {len(created)} follow-ups for "
            f"patient={patient_id} visit={visit_id}"
        )

        return {
            "scheduled": len(created),
            "followups": created
        }

    except Exception as e:
        logger.error(f"schedule_followups_after_visit failed: {e}")
        db.rollback()
        return {"scheduled": 0, "followups": [], "error": str(e)}


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

    cutoff_date = target_date - timedelta(days=OVERDUE_CUTOFF_DAYS)

    followups = (
        db.query(FollowUp)
        .options(
            joinedload(FollowUp.patient),
            joinedload(FollowUp.visit)
        )
        .filter(
            and_(
                FollowUp.clinic_id == clinic_id,
                FollowUp.status    == FollowUpStatus.PENDING,
                FollowUp.due_date  >= datetime(
                    cutoff_date.year, cutoff_date.month, cutoff_date.day
                ),
                FollowUp.due_date  <= datetime(
                    target_date.year, target_date.month, target_date.day, 23, 59, 59
                )
            )
        )
        .all()
    )

    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()

    result = []
    for f in followups:
        patient = f.patient
        if not patient:
            continue

        if getattr(patient, "whatsapp_opted_out", False):
            continue

        result.append({
            "followup_id":  str(f.id),
            "patient_id":   str(patient.id),
            "patient_name": f"{patient.first_name} {patient.last_name or ''}".strip(),
            "phone":        patient.phone_mobile,
            "language":     patient.language_pref or "en",
            "channel":      f.channel.value if f.channel else "WHATSAPP",
            "type":         f.type.value if f.type else None,
            "due_date":     f.due_date.strftime("%d-%m-%Y") if f.due_date else None,
            "template_key": get_template_key(f.type),
            # For WhatsApp template: {{1}}=patient_name, {{2}}=clinic_phone
            "template_vars": [
                patient.first_name,
                clinic.phone if clinic else "9765402949"
            ]
        })

    return result


# =====================================================
# GET TODAY'S REMINDERS (for frontend dashboard)
# Returns pending + sent today — for reminders tab
# =====================================================

def get_todays_reminders(db: Session, clinic_id: str) -> list:
    """
    All reminders due today — for reception dashboard reminders tab.
    Includes PENDING and SENT (sent today).
    """
    today = datetime.now(IST).date()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end   = datetime(today.year, today.month, today.day, 23, 59, 59)

    followups = (
        db.query(FollowUp)
        .options(joinedload(FollowUp.patient))
        .filter(
            FollowUp.clinic_id == clinic_id,
            FollowUp.due_date  >= today_start,
            FollowUp.due_date  <= today_end,
        )
        .order_by(FollowUp.due_date.asc())
        .all()
    )

    result = []
    for f in followups:
        patient = f.patient
        result.append({
            "followup_id":   str(f.id),
            "patient_id":    str(patient.id) if patient else None,
            "patient_name":  f"{patient.first_name} {patient.last_name or ''}".strip() if patient else "Unknown",
            "patient_phone": patient.phone_mobile if patient else None,
            "followup_type": f.type.value if f.type else None,
            "due_date":      f.due_date.strftime("%Y-%m-%d") if f.due_date else None,
            "status":        f.status.value if f.status else "PENDING",
            "channel":       f.channel.value if f.channel else "WHATSAPP",
            "sent_at":       f.sent_at.isoformat() if f.sent_at else None,
        })

    return result


# =====================================================
# SEND DUE REMINDERS (called by APScheduler)
# Uses WhatsApp template: followup_reminde
# =====================================================

async def send_due_reminders_async(db: Session, clinic_id: str) -> dict:
    """
    Async version — sends WhatsApp template messages for all due reminders.
    Uses approved Meta template: followup_reminde
    """
    from app.services.whatsapp_service import send_template_message

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
            # Use approved WhatsApp template: followup_reminde
            # {{1}} = patient first name, {{2}} = clinic phone
            result = await send_template_message(
                phone         = phone,
                template_name = "followup_reminde",
                language      = "en",
                components    = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": reminder["template_vars"][0]},
                            {"type": "text", "text": reminder["template_vars"][1]},
                        ]
                    }
                ],
                db         = db,
                clinic_id  = clinic_id,
                patient_id = reminder["patient_id"],
                trigger    = "followup_cron"
            )

            followup = db.query(FollowUp).filter(
                FollowUp.id == reminder["followup_id"]
            ).first()

            if followup:
                if result.get("status") in ("sent", "mocked"):
                    followup.status  = FollowUpStatus.SENT
                    followup.sent_at = datetime.now(IST)
                    followup.response = result.get("message_id", "")
                    sent += 1
                else:
                    followup.status   = FollowUpStatus.FAILED
                    followup.response = result.get("error", "unknown")
                    failed += 1
                db.commit()

        except Exception as e:
            logger.error(f"Send failed for {reminder['followup_id']}: {e}")
            failed += 1

    return {
        "date":      datetime.now(IST).strftime("%d-%m-%Y"),
        "total_due": len(due),
        "sent":      sent,
        "failed":    failed,
        "skipped":   skipped,
    }


def send_due_reminders(db: Session, clinic_id: str) -> dict:
    """
    Sync wrapper for APScheduler (runs in background thread).
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(send_due_reminders_async(db, clinic_id))
    finally:
        loop.close()


# =====================================================
# SEND SINGLE REMINDER MANUALLY
# Called from reception dashboard "Send" button
# =====================================================

async def send_single_reminder(
    db:         Session,
    followup_id: str,
    clinic_id:  str
) -> dict:
    """
    Manually send a single WhatsApp follow-up.
    Reception clicks "Send" on reminders tab.
    Uses approved Meta template: followup_reminde
    """
    from app.services.whatsapp_service import send_template_message

    followup = db.query(FollowUp).filter(
        FollowUp.id        == followup_id,
        FollowUp.clinic_id == clinic_id
    ).first()

    if not followup:
        from fastapi import HTTPException
        raise HTTPException(404, "Follow-up not found")

    patient = db.query(Patient).filter(Patient.id == followup.patient_id).first()
    clinic  = db.query(Clinic).filter(Clinic.id == clinic_id).first()

    if not patient or not patient.phone_mobile:
        from fastapi import HTTPException
        raise HTTPException(400, "Patient has no phone number")

    if getattr(patient, "whatsapp_opted_out", False):
        from fastapi import HTTPException
        raise HTTPException(400, "Patient has opted out of WhatsApp")

    result = await send_template_message(
        phone         = patient.phone_mobile,
        template_name = "followup_reminde",
        language      = "en",
        components    = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": patient.first_name},
                    {"type": "text", "text": clinic.phone if clinic else "9765402949"},
                ]
            }
        ],
        db         = db,
        clinic_id  = clinic_id,
        patient_id = str(patient.id),
        trigger    = "manual_send"
    )

    if result.get("status") in ("sent", "mocked"):
        followup.status  = FollowUpStatus.SENT
        followup.sent_at = datetime.now(IST)
        db.commit()

    return {
        "status":       result.get("status"),
        "patient_name": f"{patient.first_name} {patient.last_name or ''}".strip(),
        "phone":        patient.phone_mobile,
        "followup_id":  followup_id
    }


# =====================================================
# MARK REMINDER SENT (manual)
# =====================================================

def mark_reminder_sent(db: Session, followup_id: str, clinic_id: str) -> dict:
    followup = db.query(FollowUp).filter(
        FollowUp.id        == followup_id,
        FollowUp.clinic_id == clinic_id
    ).first()

    if not followup:
        from fastapi import HTTPException
        raise HTTPException(404, "Reminder not found")

    followup.status  = FollowUpStatus.SENT
    followup.sent_at = datetime.now(IST)
    db.commit()

    return {"message": "Marked as sent", "followup_id": followup_id}


# =====================================================
# MARK REMINDER DONE
# =====================================================

def mark_reminder_done(db: Session, followup_id: str, clinic_id: str) -> dict:
    followup = db.query(FollowUp).filter(
        FollowUp.id        == followup_id,
        FollowUp.clinic_id == clinic_id
    ).first()

    if not followup:
        from fastapi import HTTPException
        raise HTTPException(404, "Reminder not found")

    followup.status = FollowUpStatus.DONE
    db.commit()

    return {"message": "Marked as done", "followup_id": followup_id}