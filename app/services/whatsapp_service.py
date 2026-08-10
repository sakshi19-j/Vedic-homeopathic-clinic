import requests
import os
import logging

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# =====================================================
# ENV
# =====================================================

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")

PHONE_NUMBER_ID = os.getenv(
    "WHATSAPP_PHONE_NUMBER_ID"
)

WHATSAPP_API_URL = (
    f"https://graph.facebook.com/v23.0/"
    f"{PHONE_NUMBER_ID}/messages"
)


# =====================================================
# FORMAT PHONE
# =====================================================

def normalize_phone(phone: str) -> str:

    phone = str(phone).strip()

    phone = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("+", "")
    )

    if phone.startswith("91"):

        return phone

    if len(phone) == 10:

        return f"91{phone}"

    return phone


def _save_whatsapp_log(
    db: Session,
    clinic_id: str,
    patient_id: str,
    phone: str,
    message_type: str,
    template_key: str = None,
    body: str = None,
    message_id: str = None,
    status: str = None,
    trigger: str = None,
    error_text: str = None
):
    from app.models.reminder import WhatsAppLog

    if not db:
        return

    log = WhatsAppLog(
        clinic_id=clinic_id,
        patient_id=patient_id,
        direction="outbound",
        phone=phone,
        message_type=message_type,
        template_key=template_key,
        body=body,
        message_id=message_id,
        delivery_status=("SENT" if status == "sent" else "FAILED") if status else None,
        trigger=trigger,
        error_text=error_text,
    )

    db.add(log)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save WhatsAppLog: {e}")


# =====================================================
# SEND TEXT MESSAGE
# =====================================================

async def send_text_message(

    phone: str,

    message: str,

    db: Session = None,

    clinic_id: str = None,

    patient_id: str = None,

    trigger: str = None
):

    formatted_phone = normalize_phone(
        phone
    )

    headers = {

        "Authorization":
            f"Bearer {WHATSAPP_TOKEN}",

        "Content-Type":
            "application/json"
    }
    payload = {

    "messaging_product":
        "whatsapp",

    "to":
        formatted_phone,

    "type":
        "text",

    "text": {

        "body": message
    }

    }

    try:

        response = requests.post(
            WHATSAPP_API_URL,
            headers=headers,
            json=payload
        )

    except Exception as e:

        return {

            "status":"failed",

            "error":str(e)

        }

    try:

        data = response.json()

    except Exception:

        data = {
            "raw": response.text
        }

    status = "sent" if response.status_code in [200, 201] else "failed"
    message_id = (
        data.get("messages", [{}])[0]
        .get("id")
    ) if status == "sent" else None
    result = {
        "status": status,
        "message_id": message_id,
        "phone": formatted_phone
    }

    if status == "failed":
        result["error"] = data

    if db is not None:
        _save_whatsapp_log(
            db=db,
            clinic_id=clinic_id,
            patient_id=patient_id,
            phone=formatted_phone,
            message_type="text",
            template_key=None,
            body=message,
            message_id=message_id,
            status=status,
            trigger=trigger,
            error_text=(str(data) if status == "failed" else None)
        )

    return result


def _send_template_message(
    phone: str,
    template_name: str,
    parameters: list,
    template_key: str = None,
    db: Session = None,
    clinic_id: str = None,
    patient_id: str = None,
    trigger: str = None,
    body: str = None,
    language: str = "en"
):
    formatted_phone = normalize_phone(phone)
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": formatted_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [
                {
                    "type": "body",
                    "parameters": parameters
                }
            ]
        }
    }

    try:
        response = requests.post(
            WHATSAPP_API_URL,
            headers=headers,
            json=payload
        )
    except Exception as e:
        error = str(e)
        if db is not None:
            _save_whatsapp_log(
                db=db,
                clinic_id=clinic_id,
                patient_id=patient_id,
                phone=formatted_phone,
                message_type="template",
                template_key=template_key,
                body=body or template_name,
                message_id=None,
                status="failed",
                trigger=trigger,
                error_text=error
            )
        return {
            "status": "failed",
            "error": error
        }

    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    status = "sent" if response.status_code in [200, 201] else "failed"
    message_id = (
        data.get("messages", [{}])[0].get("id")
        if status == "sent" else None
    )
    result = {
        "status": status,
        "message_id": message_id,
        "response": data
    }

    if db is not None:
        _save_whatsapp_log(
            db=db,
            clinic_id=clinic_id,
            patient_id=patient_id,
            phone=formatted_phone,
            message_type="template",
            template_key=template_key,
            body=body or template_name,
            message_id=message_id,
            status=status,
            trigger=trigger,
            error_text=(str(data) if status == "failed" else None)
        )

    return result


# =====================================================
# PRESCRIPTION MESSAGE
# =====================================================

async def send_prescription_message(

    phone: str,

    patient_name: str,

    clinic_name: str,

    prescription_url: str,

    support_phone: str = "",

    db: Session = None,

    clinic_id: str = None,

    patient_id: str = None,

    trigger: str = None
):
    return _send_template_message(
        phone=phone,
        template_name="prescription_ready",
        parameters=[
            {"type": "text", "text": patient_name},
            {"type": "text", "text": clinic_name},
            {"type": "text", "text": prescription_url},
            {"type": "text", "text": support_phone}
        ],
        template_key="prescription_ready",
        db=db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        trigger=trigger,
        body=f"Prescription ready for {patient_name}",
        language="en"
    )


# =====================================================
# FOLLOWUP REMINDER
# =====================================================

async def send_followup_reminder(

    phone: str,

    patient_name: str,

    clinic_name: str,

    reminder_date: str = "",

    followup_type: str = "",

    doctor_name: str = "",

    clinic_phone: str = "",

    language: str = "en",

    db: Session = None,

    clinic_id: str = None,

    patient_id: str = None,

    trigger: str = None
):
    return _send_template_message(
        phone=phone,
        template_name="followup_reminder",
        parameters=[
            {"type": "text", "text": patient_name or "Patient"},
            {"type": "text", "text": clinic_name or "Clinic"},
            {"type": "text", "text": str(reminder_date or "Tomorrow")}
        ],
        template_key="followup_reminder",
        db=db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        trigger=trigger or followup_type,
        body=f"Follow-up reminder for {patient_name}",
        language=language
    )


# =====================================================
# THANK YOU MESSAGE
# =====================================================

async def send_thankyou_message(

    phone: str,

    patient_name: str,

    clinic_name: str,

    doctor_name: str = "",

    clinic_phone: str = "",

    language: str = "en",

    db: Session = None,

    clinic_id: str = None,

    patient_id: str = None,

    trigger: str = None
):
    return _send_template_message(
        phone=phone,
        template_name="visit_thankyou",
        parameters=[
            {"type": "text", "text": patient_name},
            {"type": "text", "text": clinic_name}
        ],
        template_key="visit_thankyou",
        db=db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        trigger=trigger,
        body=f"Thank you message for {patient_name}",
        language=language
    )

# =====================================================
# VISIT THANK YOU
# =====================================================

async def send_visit_thank_you(

    phone: str,

    patient_name: str,

    clinic_name: str,

    doctor_name: str = "",

    clinic_phone: str = "",

    language: str = "en"
):

    return await send_thankyou_message(

        phone=phone,

        patient_name=patient_name,

        clinic_name=clinic_name,

        doctor_name=doctor_name,

        clinic_phone=clinic_phone,

        language=language
    )

# =====================================================
# BIRTHDAY MESSAGE
# =====================================================

async def send_birthday_message(
    phone: str,
    patient_name: str,
    clinic_name: str,
    doctor_name: str = "",
    language: str = "en",
    db: Session = None,
    clinic_id: str = None,
    patient_id: str = None,
    trigger: str = None
):
    return _send_template_message(
        phone=phone,
        template_name="birthday_message",
        parameters=[
            {"type": "text", "text": patient_name},
            {"type": "text", "text": clinic_name}
        ],
        template_key="birthday_message",
        db=db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        trigger=trigger,
        body=f"Birthday message for {patient_name}",
        language=language
    )

# =====================================================
# BILLING RECEIPT MESSAGE
# =====================================================

async def send_billing_receipt(
        phone: str,
        patient_name: str,
        clinic_name: str,
        receipt_url: str,
        amount: str,
        db: Session = None,
        clinic_id: str = None,
        patient_id: str = None,
        trigger: str = None
):
    return _send_template_message(
        phone=phone,
        template_name="billing_receipt",
        parameters=[
            {"type": "text", "text": patient_name},
            {"type": "text", "text": clinic_name},
            {"type": "text", "text": receipt_url},
            {"type": "text", "text": amount}
        ],
        template_key="billing_receipt",
        db=db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        trigger=trigger,
        body=f"Billing receipt for {patient_name}",
        language="en"
    )
# =====================================================
# ANNIVERSARY MESSAGE
# =====================================================

async def send_anniversary_message(
    phone: str,
    patient_name: str,
    clinic_name: str,
    language: str = "en",
    db: Session = None,
    clinic_id: str = None,
    patient_id: str = None,
    trigger: str = None
):
    return _send_template_message(
        phone=phone,
        template_name="anniversary_message",
        parameters=[
            {"type": "text", "text": patient_name}
        ],
        template_key="anniversary_message",
        db=db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        trigger=trigger,
        body=f"Anniversary message for {patient_name}",
        language=language
    )