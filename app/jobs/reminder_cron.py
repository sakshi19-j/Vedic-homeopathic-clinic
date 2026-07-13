import asyncio
import logging
import pytz
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.database import SessionLocal
from app.config import settings
from app.services.growth_service import flag_missed_patients
from app.services.reminder_service import send_due_reminders
from app.models.visit import VisitStatus

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

_scheduler = None


# =====================================================
# JOB RUNNERS — one per job type for clean isolation
# =====================================================

def run_daily_reminders():
    """9:30 AM — send followup reminders + flag missed"""
    _run_async_job(_job_daily_reminders, "daily_reminders")


def run_birthday_messages():
    """9:00 AM — send birthday greetings"""
    _run_async_job(_job_birthday_messages, "birthday_messages")


def run_appointment_reminders():
    """8:00 AM — send 24hr appointment reminders"""
    _run_async_job(_job_appointment_reminders, "appointment_reminders")


def run_missed_reengagement():
    """10:00 AM Monday — re-engage missed patients"""
    _run_async_job(_job_missed_reengagement, "missed_reengagement")


def run_cleanup_jobs():
    """2:00 AM — cleanup temp files"""
    _run_async_job(_job_cleanup, "cleanup")


def _run_async_job(coro_func, job_name: str):
    """
    Safe wrapper: creates fresh DB session + event loop per job.
    Each job gets its own session — no stale data from long-lived sessions.
    """
    db   = SessionLocal()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(coro_func(db))
    except Exception as e:
        logger.error(f"❌ Job {job_name} failed: {e}")
    finally:
        db.close()
        try:
            loop.close()
        except Exception:
            pass


# =====================================================
# ASYNC JOB IMPLEMENTATIONS
# =====================================================

async def _job_daily_reminders(db):
    """Flag missed patients + send due reminders for all clinics."""
    try:
        from app.models.clinic import Clinic
        clinics = db.query(Clinic).filter(Clinic.is_active == True).all()
        logger.info(f"🏥 Daily reminders: {len(clinics)} clinics")

        for clinic in clinics:
            try:
                missed = flag_missed_patients(db, clinic.id)
                logger.info(f"  {clinic.name}: {missed} flagged as missed")

                result = await send_due_reminders(db, clinic.id)
                from app.models.visit import Visit

                recent_visits = db.query(Visit).filter(
                    Visit.clinic_id == clinic.id,
                    Visit.visit_status == VisitStatus.COMPLETED
                ).all()

                logger.info(
                    f"📄 Prescription followups checked: {len(recent_visits)}"
                )
                logger.info(
                    f"  {clinic.name}: "
                    f"sent={result['sent']} "
                    f"failed={result['failed']} "
                    f"skipped={result.get('skipped', 0)}"
                )
            except Exception as e:
                logger.error(f"  ❌ {clinic.name}: {e}")

        logger.info("✅ Daily reminders complete")

    except Exception as e:
        logger.error(f"❌ _job_daily_reminders failed: {e}")


async def _job_birthday_messages(db):
    """Send birthday greetings to patients with birthday today."""
    try:
        from app.models.patient import Patient
        from app.models.clinic import Clinic
        from app.services.whatsapp_service import send_birthday_message

        import pytz
        IST = pytz.timezone("Asia/Kolkata")
        today = datetime.now(IST).date()
        logger.info(f"🎂 Birthday messages for {today}")

        # Find patients with birthday today (match month + day)
        patients = db.query(Patient).filter(
            Patient.is_active         == True,
            Patient.phone_mobile      != None,
            Patient.whatsapp_opted_out == False,
            Patient.dob               != None,
        ).all()

        sent = 0
        for patient in patients:
            if not patient.dob:
                continue
            if (patient.dob.month == today.month and
                    patient.dob.day == today.day):

                clinic = db.query(Clinic).filter(
                    Clinic.id == patient.clinic_id
                ).first()

                # Check notification settings
                if clinic:
                    ns = clinic.get_notification_settings()
                    if not ns.get("birthday_greetings", True):
                        continue

                await send_birthday_message(
                    phone        = patient.phone_mobile,
                    patient_name = f"{patient.first_name} {patient.last_name or ''}".strip(),
                    doctor_name  = clinic.doctor_name if clinic else "Doctor",
                    clinic_name  = clinic.name if clinic else "Clinic",
                    language     = patient.language_pref or "en",
                    db           = db,
                    clinic_id    = str(patient.clinic_id),
                    patient_id   = str(patient.id)
                )
                sent += 1

        logger.info(f"✅ Birthday messages sent: {sent}")

    except Exception as e:
        logger.error(f"❌ _job_birthday_messages failed: {e}")


async def _job_appointment_reminders(db):
    """Send WhatsApp reminder 24 hours before appointment."""
    try:
        from app.models.clinic import Clinic
        from app.models.patient import Patient
        from app.services.whatsapp_service import send_text_message

        now             = datetime.now(IST)
        window_start    = now + timedelta(hours=23)
        window_end      = now + timedelta(hours=25)
        window_start_n  = window_start.replace(tzinfo=None)
        window_end_n    = window_end.replace(tzinfo=None)

        logger.info(f"📅 Appointment reminders: window {window_start_n} → {window_end_n}")

        try:
            from app.models.appointment import Appointment
            appointments = db.query(Appointment).filter(
                Appointment.scheduled_at >= window_start_n,
                Appointment.scheduled_at <= window_end_n,
                Appointment.status       == "SCHEDULED"
            ).all()
        except Exception:
            logger.warning("Appointment model not available — skipping")
            return

        sent = 0
        for appt in appointments:
            patient = db.query(Patient).filter(
                Patient.id == appt.patient_id
            ).first()
            clinic = db.query(Clinic).filter(
                Clinic.id == appt.clinic_id
            ).first()

            if not patient or not patient.phone_mobile:
                continue
            if getattr(patient, "whatsapp_opted_out", False):
                continue

            # Check notification settings
            if clinic:
                ns = clinic.get_notification_settings()
                if not ns.get("appointment_reminder", True):
                    continue

            appt_time = appt.scheduled_at.strftime("%d %b at %I:%M %p")
            lang      = patient.language_pref or "en"

            messages = {
                "en": (
                    f"Hi {patient.first_name}! Reminder: your appointment "
                    f"at {clinic.name if clinic else 'clinic'} is tomorrow — "
                    f"{appt_time}. Reply YES to confirm or call "
                    f"{clinic.phone if clinic else ''} to reschedule."
                ),
                "hi": (
                    f"नमस्ते {patient.first_name}! Reminder: आपकी appointment "
                    f"{clinic.name if clinic else 'clinic'} में कल है — "
                    f"{appt_time}. Confirm करने के लिए YES reply करें।"
                ),
                "mr": (
                    f"नमस्ते {patient.first_name}! Reminder: तुमची appointment "
                    f"{clinic.name if clinic else 'clinic'} मध्ये उद्या आहे — "
                    f"{appt_time}. Confirm करण्यासाठी YES reply करा."
                ),
            }

            await send_text_message(
                phone      = patient.phone_mobile,
                message    = messages.get(lang, messages["en"]),
                db         = db,
                clinic_id  = str(appt.clinic_id),
                patient_id = str(patient.id),
                trigger    = "appointment_reminder"
            )
            sent += 1

        logger.info(f"✅ Appointment reminders sent: {sent}")

    except Exception as e:
        logger.error(f"❌ _job_appointment_reminders failed: {e}")


async def _job_missed_reengagement(db):
    """
    Send re-engagement WhatsApp to patients who haven't visited
    in 30, 60, or 90 days. Runs once a week (Monday).
    """
    try:
        from app.models.patient import Patient
        from app.models.clinic import Clinic
        from app.services.whatsapp_service import send_text_message
        from app.services.notification_service import get_template, fill_template

        now = datetime.now(IST)
        logger.info("💔 Missed patient re-engagement")

        missed_patients = db.query(Patient).filter(
            Patient.is_active          == True,
            Patient.is_missed          == True,
            Patient.phone_mobile       != None,
            Patient.whatsapp_opted_out == False,
        ).all()

        sent = 0
        for patient in missed_patients:
            clinic = db.query(Clinic).filter(
                Clinic.id == patient.clinic_id
            ).first()

            if not clinic:
                continue

            # Check notification settings
            ns = clinic.get_notification_settings()
            if not ns.get("missed_reengagement", True):
                continue

            # Don't spam — only send if not sent in last 30 days
            # Check last outbound message to this patient
            from app.models.reminder import WhatsAppLog
            thirty_days_ago = now - timedelta(days=30)
            recent = db.query(WhatsAppLog).filter(
                WhatsAppLog.patient_id  == str(patient.id),
                WhatsAppLog.direction   == "outbound",
                WhatsAppLog.trigger     == "missed_reengagement",
                WhatsAppLog.created_at  >= thirty_days_ago.replace(tzinfo=None)
            ).first()

            if recent:
                continue  # already re-engaged recently

            lang    = patient.language_pref or "en"
            message = fill_template(
                get_template("missed_patient", lang),
                patient_name = f"{patient.first_name} {patient.last_name or ''}".strip(),
                doctor_name  = clinic.doctor_name,
                clinic_name  = clinic.name,
                clinic_phone = clinic.phone or ""
            )

            await send_text_message(
                phone      = patient.phone_mobile,
                message    = message,
                db         = db,
                clinic_id  = str(patient.clinic_id),
                patient_id = str(patient.id),
                trigger    = "missed_reengagement"
            )
            sent += 1

        logger.info(f"✅ Missed re-engagement sent: {sent}")

    except Exception as e:
        logger.error(f"❌ _job_missed_reengagement failed: {e}")


async def _job_cleanup(db):
    """Clean up temp PDF files older than 1 hour."""
    import os, glob

    try:
        now     = datetime.now(IST)
        cleaned = 0
        cutoff  = 3600  # 1 hour in seconds

        for pattern in ["/tmp/receipt_*.pdf", "/tmp/prescription_*.pdf"]:
            for filepath in glob.glob(pattern):
                try:
                    age = now.timestamp() - os.path.getmtime(filepath)
                    if age > cutoff:
                        os.unlink(filepath)
                        cleaned += 1
                except Exception as e:

                    logger.warning(str(e))

        logger.info(f"✅ Cleanup: {cleaned} temp files removed")

    except Exception as e:
        logger.error(f"❌ _job_cleanup failed: {e}")


# =====================================================
# START SCHEDULER
# =====================================================

def start_scheduler():
    global _scheduler

    if _scheduler is not None:
        logger.info("⚠️ Scheduler already running — skipping")
        return _scheduler

    try:
        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.DATABASE_URL)
        }

        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone=IST
        )

        # 9:30 AM — followup reminders + flag missed
        _scheduler.add_job(
            func=run_daily_reminders,
            trigger="cron", hour=9, minute=30,
            id="daily_reminders",
            name="Daily Followup Reminders",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # 9:00 AM — birthday greetings
        _scheduler.add_job(
            func=run_birthday_messages,
            trigger="cron", hour=9, minute=0,
            id="birthday_messages",
            name="Birthday Greetings",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # 8:00 AM — 24hr appointment reminders
        _scheduler.add_job(
            func=run_appointment_reminders,
            trigger="cron", hour=8, minute=0,
            id="appointment_reminders",
            name="Appointment Reminders",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # Monday 10:00 AM — missed patient re-engagement
        _scheduler.add_job(
            func=run_missed_reengagement,
            trigger="cron", day_of_week="mon", hour=10, minute=0,
            id="missed_reengagement",
            name="Missed Patient Re-engagement",
            replace_existing=True,
            misfire_grace_time=7200
        )

        # 2:00 AM — temp file cleanup
        _scheduler.add_job(
            func=run_cleanup_jobs,
            trigger="cron", hour=2, minute=0,
            id="cleanup_jobs",
            name="Temp File Cleanup",
            replace_existing=True,
            misfire_grace_time=3600
        )

        _scheduler.start()
        logger.info("✅ Scheduler started — 5 jobs registered")
        return _scheduler

    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        raise