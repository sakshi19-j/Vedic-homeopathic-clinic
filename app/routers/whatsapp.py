import os
import hmac
import hashlib
import logging
import json

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

import pytz

from app.database import get_db
from app.services.whatsapp_service import (
    send_text_message,
    send_followup_reminder,
    send_thankyou_message,
    send_birthday_message
)
from app.middleware.auth_middleware import receptionist_or_doctor
from app.models.user import User
from app.models.patient import Patient
from app.models.clinic import Clinic

logger = logging.getLogger(__name__)
IST    = pytz.timezone("Asia/Kolkata")

router      = APIRouter(prefix="/webhooks", tags=["WhatsApp Webhooks"])
send_router = APIRouter(prefix="/whatsapp",  tags=["WhatsApp Send"])

STOP_WORDS = {
    "STOP", "UNSUBSCRIBE", "CANCEL MESSAGES",
    "BAND KARO", "MAT BHEJO", "NAHI CHAHIYE"
}


# ─────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    patient_id: str
    message:    str


class SendReminderRequest(BaseModel):
    patient_id:    str
    followup_type: Optional[str] = "followup_7d"


# ─────────────────────────────────────────────────────────────
# WEBHOOK VERIFICATION  GET /webhooks/whatsapp
# ─────────────────────────────────────────────────────────────

@router.get("/whatsapp")
async def verify_webhook(request: Request):
    params    = request.query_params
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token = os.getenv(
        "WHATSAPP_VERIFY_TOKEN",
        "vennova_webhook_verify_2026"
    )

    if mode == "subscribe" and token == verify_token:
        logger.info("✅ WhatsApp webhook verified")
        return PlainTextResponse(content=str(challenge), status_code=200)

    logger.warning("❌ Webhook verification failed")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


# ─────────────────────────────────────────────────────────────
# RECEIVE WEBHOOK  POST /webhooks/whatsapp
# ─────────────────────────────────────────────────────────────

@router.post("/whatsapp")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    body_bytes = await request.body()

    _verify_webhook_signature(
        body_bytes,
        request.headers.get("X-Hub-Signature-256", "")
    )

    try:
        body    = json.loads(body_bytes)
        entry   = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})

        for status_event in value.get("statuses", []):
            _handle_delivery_status(db, status_event)

        for msg in value.get("messages", []):
            await _handle_inbound_message(db, msg, value)

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────
# SIGNATURE VERIFICATION
# ─────────────────────────────────────────────────────────────

def _verify_webhook_signature(body: bytes, signature_header: str):
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "")

    if not app_secret:
        return  # dev mode — skip

    if not signature_header.startswith("sha256="):
        raise HTTPException(403, "Missing webhook signature")

    mac = hmac.new(
        app_secret.encode("utf-8"),
        body,
        hashlib.sha256
    )
    expected = mac.hexdigest()
    received = signature_header[len("sha256="):]

    if not hmac.compare_digest(expected, received):
        logger.warning("Webhook signature mismatch")
        raise HTTPException(403, "Invalid webhook signature")


# ─────────────────────────────────────────────────────────────
# DELIVERY STATUS HANDLER
# ✅ ADDED — idempotency guard against duplicate Meta webhooks
# ─────────────────────────────────────────────────────────────

def _handle_delivery_status(db: Session, status_event: dict):
    try:
        from app.models.reminder import WhatsAppLog, DeliveryStatus

        message_id = status_event.get("id")
        status_val = status_event.get("status", "").upper()
        now        = datetime.now(IST)

        if not message_id:
            return

        log = db.query(WhatsAppLog).filter(
            WhatsAppLog.message_id == message_id
        ).first()

        if not log:
            logger.warning(
                f"WhatsAppLog not found for message_id: {message_id}: "
                f"event={status_event}"
            )
            return

        # ✅ IDEMPOTENCY — skip if this status was already recorded
        # Meta sends duplicate webhooks sometimes — this prevents double processing
        already_processed = (
            (status_val == "DELIVERED" and log.delivered_at is not None) or
            (status_val == "READ"      and log.read_at is not None)      or
            (status_val == "FAILED"    and log.failed_at is not None)
        )
        if already_processed:
            logger.info(f"Duplicate webhook ignored: {message_id} → {status_val}")
            return

        if status_val == "DELIVERED":
            log.delivery_status = DeliveryStatus.DELIVERED
            log.delivered_at    = now
        elif status_val == "READ":
            log.delivery_status = DeliveryStatus.READ
            log.read_at         = now
        elif status_val == "FAILED":
            log.delivery_status = DeliveryStatus.FAILED
            log.failed_at       = now
            log.error_text      = str(
                status_event.get("errors", [{}])[0].get("title", "")
            )

        db.commit()
        logger.info(f"Delivery update: {message_id} → {status_val}")

    except Exception as e:
        logger.error(f"Delivery status update failed: {e}")


# ─────────────────────────────────────────────────────────────
# INBOUND MESSAGE HANDLER
# ─────────────────────────────────────────────────────────────

async def _handle_inbound_message(db: Session, msg: dict, value: dict):
    try:
        raw_phone = msg.get("from", "")
        text      = msg.get("text", {}).get("body", "").strip().upper()

        if not raw_phone or not text:
            return

        phone = raw_phone
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]

        logger.info(f"📩 Inbound: +91{phone} → {text[:50]}")

        patient = db.query(Patient).filter(
            Patient.phone_mobile == phone
        ).first()

        if not patient:
            await send_text_message(
                phone,
                "Thank you for contacting us. "
                "Please call us directly for assistance."
            )
            return

        clinic = db.query(Clinic).filter(
            Clinic.id == patient.clinic_id
        ).first()

        # STOP — highest priority
        if any(w in text for w in STOP_WORDS):
            _handle_opt_out(db, patient)
            await send_text_message(
                phone,
                "You have been unsubscribed from reminders. "
                "Reply START to resubscribe anytime."
            )
            return

        # START — re-subscribe
        if text in ("START", "SUBSCRIBE", "SHURU"):
            patient.whatsapp_opted_out    = False
            patient.whatsapp_opted_out_at = None
            db.commit()
            await send_text_message(
                phone,
                f"Welcome back {patient.first_name}! "
                f"You will receive reminders from "
                f"{clinic.name if clinic else 'our clinic'}."
            )
            return

        clinic_name    = clinic.name        if clinic else "our clinic"
        doctor_name    = clinic.doctor_name if clinic else "Doctor"
        clinic_phone   = clinic.phone       if clinic else ""
        clinic_timings = (
            clinic.timings
            if clinic and hasattr(clinic, "timings") and clinic.timings
            else "10am-2pm | 5pm-9pm"
        )

        reply = _build_auto_reply(
            text           = text,
            patient_name   = patient.first_name,
            clinic_name    = clinic_name,
            doctor_name    = doctor_name,
            clinic_phone   = clinic_phone,
            clinic_timings = clinic_timings,
            language       = patient.language_pref or "en"
        )

        await send_text_message(phone, reply)
        _update_followup_from_reply(db, patient.id, text)

    except Exception as e:
        logger.error(f"Inbound message handler error: {e}")


# ─────────────────────────────────────────────────────────────
# OPT-OUT
# ─────────────────────────────────────────────────────────────

def _handle_opt_out(db: Session, patient: Patient):
    patient.whatsapp_opted_out    = True
    patient.whatsapp_opted_out_at = datetime.now(IST)
    db.commit()
    logger.info(f"Patient {patient.id} opted out of WhatsApp")


# ─────────────────────────────────────────────────────────────
# AUTO REPLY BUILDER
# ─────────────────────────────────────────────────────────────

def _build_auto_reply(
    text: str, patient_name: str, clinic_name: str,
    doctor_name: str, clinic_phone: str,
    clinic_timings: str, language: str
) -> str:

    CONFIRM_WORDS = {
        "YES", "COMING", "OK", "OKAY", "WILL COME", "HA", "HAN",
        "HAAN", "ZAROOR", "AAUNGA", "AAUNGI", "CONFIRM", "CONFIRMED", "YEP", "YA"
    }
    CANCEL_WORDS = {
        "NO", "CANCEL", "NAHI", "NAHIN", "CANNOT", "CANT",
        "NOT COMING", "BUSY", "NOPE"
    }
    HELP_WORDS = {
        "HELP", "TIMING", "TIME", "TIMINGS", "WHEN", "ADDRESS",
        "WHERE", "LOCATION", "FEES", "FEE", "COST", "CHARGE", "DOCTOR"
    }
    THANKS_WORDS = {
        "THANK", "THANKS", "THANKYOU", "SHUKRIYA", "DHANYAWAD", "DHANYABAD"
    }

    words = set(text.split())

    if words & CONFIRM_WORDS:
        msgs = {
            "hi": f"धन्यवाद {patient_name}! आपकी visit confirm हो गई है। {clinic_name} में स्वागत है। 📞 {clinic_phone}",
            "mr": f"धन्यवाद {patient_name}! तुमची visit confirm झाली आहे. {clinic_name} मध्ये स्वागत आहे. 📞 {clinic_phone}",
            "en": f"Thank you {patient_name}! Your visit is confirmed. See you at {clinic_name}. 📞 {clinic_phone}"
        }
    elif words & CANCEL_WORDS:
        msgs = {
            "hi": f"कोई बात नहीं {patient_name}। जब भी ready हों: 📞 {clinic_phone}",
            "mr": f"ठीक आहे {patient_name}. तयार असाल तेव्हा: 📞 {clinic_phone}",
            "en": f"No problem {patient_name}. Call us to reschedule: 📞 {clinic_phone}"
        }
    elif words & HELP_WORDS:
        msgs = {
            "hi": f"नमस्ते {patient_name}!\n🏥 {clinic_name}\n👨‍⚕️ {doctor_name}\n⏰ {clinic_timings}\n📞 {clinic_phone}",
            "mr": f"नमस्ते {patient_name}!\n🏥 {clinic_name}\n👨‍⚕️ {doctor_name}\n⏰ {clinic_timings}\n📞 {clinic_phone}",
            "en": f"Hello {patient_name}!\n🏥 {clinic_name}\n👨‍⚕️ {doctor_name}\n⏰ {clinic_timings}\n📞 {clinic_phone}"
        }
    elif words & THANKS_WORDS:
        msgs = {
            "hi": f"आपका स्वागत है {patient_name}! {clinic_name} हमेशा आपकी सेवा में है 🙏",
            "mr": f"स्वागत आहे {patient_name}! {clinic_name} नेहमी तुमच्या सेवेत आहे 🙏",
            "en": f"You're welcome {patient_name}! {clinic_name} is always here for you 🙏"
        }
    else:
        msgs = {
            "hi": f"नमस्ते {patient_name}! message मिल गया। जल्द संपर्क करेंगे। 📞 {clinic_phone}",
            "mr": f"नमस्ते {patient_name}! message मिळाला. लवकरच संपर्क करू. 📞 {clinic_phone}",
            "en": f"Hello {patient_name}! Message received. We'll contact you shortly. 📞 {clinic_phone}"
        }

    return msgs.get(language, msgs["en"])


# ─────────────────────────────────────────────────────────────
# FOLLOWUP STATUS FROM REPLY
# ─────────────────────────────────────────────────────────────

def _update_followup_from_reply(db: Session, patient_id: str, text: str):
    from app.models.reminder import FollowUp, FollowUpStatus

    CONFIRM = {
        "YES", "COMING", "OK", "OKAY", "WILL COME",
        "HA", "HAN", "HAAN", "CONFIRM", "CONFIRMED"
    }
    CANCEL = {"NO", "CANCEL", "NAHI", "NOT COMING", "BUSY"}

    words    = set(text.split())
    followup = db.query(FollowUp).filter(
        FollowUp.patient_id == patient_id,
        FollowUp.status.in_([FollowUpStatus.SENT, FollowUpStatus.PENDING])
    ).order_by(FollowUp.due_date.desc()).first()

    if not followup:
        return

    if words & CONFIRM:
        followup.status   = FollowUpStatus.DONE
        followup.response = text
        db.commit()
    elif words & CANCEL:
        followup.status   = FollowUpStatus.SKIPPED
        followup.response = text
        db.commit()


# ─────────────────────────────────────────────────────────────
# SEND ROUTES
# ─────────────────────────────────────────────────────────────

@send_router.post("/send/message")
async def send_message(
    data: SendMessageRequest,
    db:   Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patient = db.query(Patient).filter(
        Patient.id        == data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient or not patient.phone_mobile:
        raise HTTPException(404, "Patient not found or no phone")

    if getattr(patient, "whatsapp_opted_out", False):
        raise HTTPException(400, "Patient has opted out of WhatsApp messages")

    return await send_text_message(
        phone=patient.phone_mobile,
        message=data.message,
        db=db,
        clinic_id=str(current_user.clinic_id),
        patient_id=str(patient.id),
        trigger="manual_message"
    )


@send_router.post("/send/reminder")
async def send_reminder(
    data: SendReminderRequest,
    db:   Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patient = db.query(Patient).filter(
        Patient.id        == data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient or not patient.phone_mobile:
        raise HTTPException(404, "Patient not found")

    if getattr(patient, "whatsapp_opted_out", False):
        raise HTTPException(400, "Patient has opted out of WhatsApp messages")

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    return await send_followup_reminder(
        phone         = patient.phone_mobile,
        patient_name  = f"{patient.first_name} {patient.last_name or ''}".strip(),
        doctor_name   = clinic.doctor_name if clinic else "Doctor",
        clinic_name   = clinic.name        if clinic else "Clinic",
        clinic_phone  = clinic.phone       if clinic else "",
        language      = patient.language_pref or "en",
        followup_type = data.followup_type,
        db            = db,
        clinic_id     = str(current_user.clinic_id),
        patient_id    = str(patient.id),
        trigger       = data.followup_type or "manual_reminder"
    )


@send_router.post("/send/thankyou/{patient_id}")
async def send_thankyou(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patient = db.query(Patient).filter(
        Patient.id        == patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient or not patient.phone_mobile:
        raise HTTPException(404, "Patient not found")

    if getattr(patient, "whatsapp_opted_out", False):
        return {"status": "skipped", "reason": "Patient opted out"}

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    return await send_thankyou_message(
        phone        = patient.phone_mobile,
        patient_name = f"{patient.first_name} {patient.last_name or ''}".strip(),
        doctor_name  = clinic.doctor_name if clinic else "Doctor",
        clinic_name  = clinic.name        if clinic else "Clinic",
        clinic_phone = clinic.phone       if clinic else "",
        language     = patient.language_pref or "en",
        db           = db,
        clinic_id    = str(current_user.clinic_id),
        patient_id   = str(patient.id),
        trigger      = "thankyou"
    )


@send_router.post("/send/birthday/{patient_id}")
async def send_birthday(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    patient = db.query(Patient).filter(
        Patient.id        == patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient or not patient.phone_mobile:
        raise HTTPException(404, "Patient not found")

    if getattr(patient, "whatsapp_opted_out", False):
        return {"status": "skipped", "reason": "Patient opted out"}

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    return await send_birthday_message(
        phone        = patient.phone_mobile,
        patient_name = f"{patient.first_name} {patient.last_name or ''}".strip(),
        clinic_name  = clinic.name        if clinic else "Clinic",
        language     = patient.language_pref or "en",
        db           = db,
        clinic_id    = str(current_user.clinic_id),
        patient_id   = str(patient.id),
        trigger      = "birthday"
    )


# ─────────────────────────────────────────────────────────────
# DELIVERY LOGS
# ─────────────────────────────────────────────────────────────

@send_router.get("/logs")
def get_whatsapp_logs(
    limit: int = 50,
    db:    Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    from app.models.reminder import WhatsAppLog

    logs = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == str(current_user.clinic_id)
    ).order_by(
        WhatsAppLog.created_at.desc()
    ).limit(limit).all()

    return {
        "total": len(logs),
        "logs": [
            {
                "id":           log.id,
                "patient_id":   log.patient_id,
                "phone":        log.phone,
                "body":         (log.body or "")[:80],
                "status":       log.delivery_status.value if log.delivery_status else None,
                "sent_at":      log.created_at.strftime("%d-%m-%Y %H:%M") if log.created_at else None,
                "delivered_at": log.delivered_at.strftime("%d-%m-%Y %H:%M") if log.delivered_at else None,
                "read_at":      log.read_at.strftime("%d-%m-%Y %H:%M") if log.read_at else None,
                "trigger":      log.trigger,
            }
            for log in logs
        ]
    }