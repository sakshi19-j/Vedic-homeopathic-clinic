import httpx
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# =====================================================
# DAILY RATE LIMIT
# Meta free tier: 1000 messages/day per phone number
# We guard at 950 to leave headroom
# =====================================================
_daily_counts: dict = {}   # { "clinic_id:YYYY-MM-DD": count }
DAILY_LIMIT = 950


def _check_rate_limit(clinic_id: str) -> bool:
    """Returns True if send is allowed, False if limit reached."""
    today = datetime.now(IST).strftime("%Y-%m-%d")
    key   = f"{clinic_id}:{today}"
    count = _daily_counts.get(key, 0)
    if count >= DAILY_LIMIT:
        logger.warning(
            f"Rate limit reached for clinic {clinic_id} on {today}"
        )
        return False
    _daily_counts[key] = count + 1
    return True


# =====================================================
# PHONE NORMALIZATION
# =====================================================

def normalize_phone(phone: str) -> str:
    """
    Always returns 12-digit format: 919876543210
    Handles: 9876543210 / +919876543210 / 91 9876... / 0091...
    """
    if not phone:
        return ""

    phone = phone.strip().replace(" ", "").replace("-", "")

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("0091"):
        phone = phone[4:]

    # Only add 91 if it's a bare 10-digit number
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
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    # Version as env var — upgrade without code change
    version  = os.getenv("WHATSAPP_API_VERSION", "v19.0")
    base_url = os.getenv(
        "WHATSAPP_API_URL",
        f"https://graph.facebook.com/{version}"
    )
    return f"{base_url}/{phone_number_id}/messages"


# =====================================================
# LOG WRITER
# =====================================================

def _write_log(
    db: Session,
    clinic_id: str,
    patient_id: str,
    phone: str,
    body: str,
    result: dict,
    template_key: str = None,
    trigger: str = "manual",
    direction: str = "outbound"
):
    """
    Persist every WhatsApp send attempt to whatsapp_logs.
    Called after every send — success or failure.
    """
    if db is None:
        return

    try:
        from app.models.reminder import WhatsAppLog, DeliveryStatus

        status_map = {
            "sent":    DeliveryStatus.SENT,
            "mocked":  DeliveryStatus.MOCKED,
            "failed":  DeliveryStatus.FAILED,
        }

        log = WhatsAppLog(
            clinic_id       = clinic_id,
            patient_id      = patient_id,
            direction       = direction,
            phone           = phone,
            message_type    = "template" if template_key else "text",
            template_key    = template_key,
            body            = body,
            message_id      = result.get("message_id"),
            delivery_status = status_map.get(
                result.get("status", "failed"),
                DeliveryStatus.FAILED
            ),
            error_text      = result.get("error"),
            trigger         = trigger,
        )
        db.add(log)
        db.commit()

    except Exception as e:
        # Never let logging crash the main flow
        logger.error(f"WhatsApp log write failed: {e}")


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

    # Rate limit check
    if clinic_id and not _check_rate_limit(clinic_id):
        result = {
            "status": "failed",
            "error":  "Daily WhatsApp limit reached (950/day)",
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

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                get_api_url(),
                headers=get_headers(),
                json=payload
            )
            data = response.json()

            if response.status_code == 200:
                result = {
                    "status":     "sent",
                    "message_id": data.get("messages", [{}])[0].get("id", ""),
                    "phone":      normalized
                }
            else:
                error_msg = data.get("error", {}).get("message", "Unknown error")
                logger.error(f"WhatsApp send failed: {error_msg} | to={normalized}")
                result = {"status": "failed", "error": error_msg, "phone": normalized}

        except Exception as e:
            logger.error(f"WhatsApp exception: {e} | to={normalized}")
            result = {"status": "failed", "error": str(e), "phone": normalized}

    _write_log(db, clinic_id, patient_id, normalized, message, result, trigger=trigger)
    return result


# =====================================================
# SEND TEMPLATE MESSAGE
# =====================================================

async def send_template_message(
    phone: str,
    template_name: str,
    language: str,
    components: list,
    db: Session = None,
    clinic_id: str = None,
    patient_id: str = None,
    trigger: str = "manual"
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

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                get_api_url(), headers=get_headers(), json=payload
            )
            data = response.json()

            if response.status_code == 200:
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
        except Exception as e:
            result = {"status": "failed", "error": str(e)}

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
    db: Session = None, clinic_id: str = None,
    patient_id: str = None
) -> dict:

    from app.services.notification_service import get_template, fill_template

    template = get_template(followup_type, language)
    message  = fill_template(
        template=template, patient_name=patient_name,
        doctor_name=doctor_name, clinic_name=clinic_name,
        clinic_phone=clinic_phone
    )
    return await send_text_message(
        phone, message, db=db,
        clinic_id=clinic_id, patient_id=patient_id,
        trigger="followup_cron"
    )


async def send_thankyou_message(
    phone: str, patient_name: str, doctor_name: str,
    clinic_name: str, clinic_phone: str,
    language: str = "en",
    db: Session = None, clinic_id: str = None,
    patient_id: str = None
) -> dict:

    from app.services.notification_service import get_template, fill_template

    template = get_template("thankyou", language)
    message  = fill_template(
        template=template, patient_name=patient_name,
        doctor_name=doctor_name, clinic_name=clinic_name,
        clinic_phone=clinic_phone
    )
    return await send_text_message(
        phone, message, db=db,
        clinic_id=clinic_id, patient_id=patient_id,
        trigger="visit_close"
    )


async def send_birthday_message(
    phone: str, patient_name: str, doctor_name: str,
    clinic_name: str, language: str = "en",
    db: Session = None, clinic_id: str = None,
    patient_id: str = None
) -> dict:

    from app.services.notification_service import get_template, fill_template

    template = get_template("birthday", language)
    message  = fill_template(
        template=template, patient_name=patient_name,
        doctor_name=doctor_name, clinic_name=clinic_name,
        clinic_phone=""
    )
    return await send_text_message(
        phone, message, db=db,
        clinic_id=clinic_id, patient_id=patient_id,
        trigger="birthday_cron"
    )