import httpx
import os
import logging
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
import pytz

logger = logging.getLogger(__name__)
IST    = pytz.timezone("Asia/Kolkata")

# =====================================================
# RATE LIMIT — DB-backed so survives deploys
# =====================================================
# FIX: in-memory dict resets on every Railway restart
# Use DB-based count via WhatsAppLog instead
# =====================================================

DAILY_LIMIT = int(os.getenv("WHATSAPP_DAILY_LIMIT", "950"))


def _check_rate_limit_db(clinic_id: str, db: Session) -> bool:
    """
    DB-backed rate limit — survives server restarts.
    Counts today's outbound sends from whatsapp_logs.
    Falls back to allow if DB unavailable.
    """
    if not db or not clinic_id:
        return True

    try:
        from app.models.reminder import WhatsAppLog, DeliveryStatus
        today_start = datetime.now(IST).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).replace(tzinfo=None)

        count = db.query(WhatsAppLog).filter(
            WhatsAppLog.clinic_id  == str(clinic_id),
            WhatsAppLog.direction  == "outbound",
            WhatsAppLog.created_at >= today_start
        ).count()

        if count >= DAILY_LIMIT:
            logger.warning(
                f"Rate limit: clinic={clinic_id} "
                f"sent={count} limit={DAILY_LIMIT}"
            )
            return False
        return True

    except Exception as e:
        logger.error(f"Rate limit check failed: {e} — allowing send")
        return True


# =====================================================
# PHONE NORMALIZATION
# =====================================================

def normalize_phone(phone: str) -> str:
    """Returns 12-digit: 919876543210"""
    if not phone:
        return ""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0091"):
        phone = phone[4:]
    if len(phone) == 10 and not phone.startswith("91"):
        phone = f"91{phone}"
    return phone


# =====================================================
# HEADERS + URL
# =====================================================

def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN', '')}",
        "Content-Type":  "application/json"
    }


def get_api_url() -> str:
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    version  = os.getenv("WHATSAPP_API_VERSION", "v19.0")
    base     = os.getenv("WHATSAPP_API_URL", f"https://graph.facebook.com/{version}")
    return f"{base}/{phone_id}/messages"


# =====================================================
# LOG WRITER
# =====================================================

def _write_log(
    db: Session, clinic_id: str, patient_id: str,
    phone: str, body: str, result: dict,
    template_key: str = None,
    trigger: str = "manual",
    direction: str = "outbound"
):
    if db is None:
        return
    try:
        from app.models.reminder import WhatsAppLog, DeliveryStatus
        status_map = {
            "sent":   DeliveryStatus.SENT,
            "mocked": DeliveryStatus.MOCKED,
            "failed": DeliveryStatus.FAILED,
        }
        log = WhatsAppLog(
            clinic_id       = str(clinic_id) if clinic_id else "unknown",
            patient_id      = str(patient_id) if patient_id else None,
            direction       = direction,
            phone           = phone,
            message_type    = "template" if template_key else "text",
            template_key    = template_key,
            body            = (body or "")[:500],
            message_id      = result.get("message_id"),
            delivery_status = status_map.get(
                result.get("status", "failed"),
                DeliveryStatus.FAILED
            ),
            error_text = result.get("error"),
            trigger    = trigger,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"WhatsApp log write failed: {e}")


# =====================================================
# RETRY HELPER
# =====================================================

async def _send_with_retry(
    payload: dict,
    max_retries: int = 2,
    base_delay: float = 2.0
) -> tuple[int, dict]:
    """
    Exponential backoff retry for transient Meta API failures.
    Retries on: 429 (rate limited), 5xx (server errors).
    Does NOT retry on: 400 (bad request), 401 (auth), 403 (forbidden).
    Returns (status_code, response_data).
    """
    last_status = 500
    last_data   = {}

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    get_api_url(),
                    headers=get_headers(),
                    json=payload
                )
                last_status = response.status_code
                last_data   = response.json()

                # Success
                if last_status == 200:
                    return last_status, last_data

                # Don't retry client errors
                if last_status in (400, 401, 403, 404):
                    return last_status, last_data

                # Retry on 429 or 5xx
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # 2s, 4s
                    logger.warning(
                        f"WhatsApp API {last_status} — "
                        f"retry {attempt+1}/{max_retries} in {delay}s"
                    )
                    await asyncio.sleep(delay)

        except httpx.TimeoutException:
            logger.warning(f"WhatsApp timeout — attempt {attempt+1}")
            if attempt < max_retries:
                await asyncio.sleep(base_delay * (2 ** attempt))
        except Exception as e:
            logger.error(f"WhatsApp exception: {e}")
            return 500, {"error": {"message": str(e)}}

    return last_status, last_data


# =====================================================
# SEND TEXT MESSAGE
# =====================================================

async def send_text_message(
    phone: str,
    message: str,
    db: Session = None,
    clinic_id: str = None,
    patient_id: str = None,
    trigger: str = "manual"
) -> dict:

    normalized = normalize_phone(phone)
    if not normalized:
        return {"status": "failed", "error": "Invalid phone number"}

    # DB-backed rate limit
    if clinic_id and not _check_rate_limit_db(clinic_id, db):
        result = {
            "status": "failed",
            "error":  f"Daily WhatsApp limit reached ({DAILY_LIMIT}/day)",
            "phone":  normalized
        }
        _write_log(db, clinic_id, patient_id, normalized, message, result, trigger=trigger)
        return result

    # Mock mode
    if not os.getenv("WHATSAPP_ACCESS_TOKEN"):
        logger.info(f"📱 MOCK → +{normalized}: {message[:60]}...")
        result = {"status": "mocked", "message_id": "mock_id", "phone": normalized}
        _write_log(db, clinic_id, patient_id, normalized, message, result, trigger=trigger)
        return result

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type":    "individual",
        "to":                normalized,
        "type":              "text",
        "text":              {"body": message}
    }

    status_code, data = await _send_with_retry(payload)

    if status_code == 200:
        result = {
            "status":     "sent",
            "message_id": data.get("messages", [{}])[0].get("id", ""),
            "phone":      normalized
        }
    else:
        error_msg = data.get("error", {}).get("message", "Unknown error")
        logger.error(f"WhatsApp failed: {error_msg} | to={normalized} | status={status_code}")
        result = {"status": "failed", "error": error_msg, "phone": normalized}

    _write_log(db, clinic_id, patient_id, normalized, message, result, trigger=trigger)
    return result


# =====================================================
# SEND TEMPLATE MESSAGE
# =====================================================

async def send_template_message(
    phone: str, template_name: str,
    language: str, components: list,
    db: Session = None, clinic_id: str = None,
    patient_id: str = None, trigger: str = "manual"
) -> dict:

    normalized = normalize_phone(phone)

    if not os.getenv("WHATSAPP_ACCESS_TOKEN"):
        result = {"status": "mocked", "template": template_name, "message_id": "mock_id"}
        _write_log(db, clinic_id, patient_id, normalized, f"[template:{template_name}]",
                   result, template_key=template_name, trigger=trigger)
        return result

    payload = {
        "messaging_product": "whatsapp",
        "to":                normalized,
        "type":              "template",
        "template": {
            "name":       template_name,
            "language":   {"code": language},
            "components": components
        }
    }

    status_code, data = await _send_with_retry(payload)

    if status_code == 200:
        result = {
            "status":     "sent",
            "message_id": data.get("messages", [{}])[0].get("id", ""),
            "template":   template_name
        }
    else:
        result = {
            "status": "failed",
            "error":  data.get("error", {}).get("message", "Unknown"),
            "phone":  normalized
        }

    _write_log(db, clinic_id, patient_id, normalized, f"[template:{template_name}]",
               result, template_key=template_name, trigger=trigger)
    return result


# =====================================================
# HIGH-LEVEL SENDERS
# =====================================================

async def send_followup_reminder(
    phone: str, patient_name: str, doctor_name: str,
    clinic_name: str, clinic_phone: str,
    language: str = "en", followup_type: str = "followup_7d",
    db: Session = None, clinic_id: str = None, patient_id: str = None
) -> dict:
    from app.services.notification_service import get_template, fill_template
    msg = fill_template(
        get_template(followup_type, language),
        patient_name=patient_name, doctor_name=doctor_name,
        clinic_name=clinic_name, clinic_phone=clinic_phone
    )
    return await send_text_message(
        phone, msg, db=db, clinic_id=clinic_id,
        patient_id=patient_id, trigger="followup_cron"
    )


async def send_thankyou_message(
    phone: str, patient_name: str, doctor_name: str,
    clinic_name: str, clinic_phone: str,
    language: str = "en",
    db: Session = None, clinic_id: str = None, patient_id: str = None
) -> dict:
    from app.services.notification_service import get_template, fill_template
    msg = fill_template(
        get_template("thankyou", language),
        patient_name=patient_name, doctor_name=doctor_name,
        clinic_name=clinic_name, clinic_phone=clinic_phone
    )
    return await send_text_message(
        phone, msg, db=db, clinic_id=clinic_id,
        patient_id=patient_id, trigger="visit_close"
    )


async def send_birthday_message(
    phone: str, patient_name: str, doctor_name: str,
    clinic_name: str, language: str = "en",
    db: Session = None, clinic_id: str = None, patient_id: str = None
) -> dict:
    from app.services.notification_service import get_template, fill_template
    msg = fill_template(
        get_template("birthday", language),
        patient_name=patient_name, doctor_name=doctor_name,
        clinic_name=clinic_name, clinic_phone=""
    )
    return await send_text_message(
        phone, msg, db=db, clinic_id=clinic_id,
        patient_id=patient_id, trigger="birthday_cron"
    )