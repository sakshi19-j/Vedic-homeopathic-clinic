import requests
import os

from sqlalchemy.orm import Session


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

    response = requests.post(

        WHATSAPP_API_URL,

        headers=headers,

        json=payload
    )

    try:

        data = response.json()

    except Exception:

        data = {
            "raw": response.text
        }

    if response.status_code in [200, 201]:

        return {

            "status": "sent",

            "message_id": (
                data.get("messages", [{}])[0]
                .get("id")
            ),

            "phone": formatted_phone
        }

    return {

        "status": "failed",

        "phone": formatted_phone,

        "error": data
    }

# =====================================================
# PRESCRIPTION MESSAGE
# =====================================================

async def send_prescription_message(

    phone: str,

    patient_name: str,

    clinic_name: str,

    prescription_url: str,

    support_phone: str = ""
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
            "name": "prescription_ready",
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": patient_name
                        },
                        {
                            "type": "text",
                            "text": clinic_name
                        },
                        {
                            "type": "text",
                            "text": prescription_url
                        },
                        {
                            "type": "text",
                            "text": support_phone
                        }
                    ]
                }
            ]
        }
    }

    response = requests.post(
        WHATSAPP_API_URL,
        headers=headers,
        json=payload
    )

    data = response.json()

    return {
        "status": "sent" if response.status_code in [200, 201] else "failed",
        "response": data
    }


# =====================================================
# FOLLOWUP REMINDER
# =====================================================

async def send_followup_reminder(

    phone: str,

    patient_name: str,

    clinic_name: str,

    reminder_date: str = ""
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
            "name": "followup_reminder",
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": patient_name
                        },
                        {
                            "type": "text",
                            "text": clinic_name
                        },
                        {
                            "type": "text",
                            "text": reminder_date
                        }
                    ]
                }
            ]
        }
    }

    response = requests.post(
        WHATSAPP_API_URL,
        headers=headers,
        json=payload
    )

    data = response.json()

    return {
        "status": "sent" if response.status_code in [200, 201] else "failed",
        "response": data
    }


# =====================================================
# THANK YOU MESSAGE
# =====================================================

async def send_thankyou_message(
        phone: str,
        patient_name: str,
        clinic_name: str,
        doctor_name: str = ""
):

    message = f"""
Dear {patient_name},

Thank you for visiting {clinic_name}.

We appreciate your trust.

Get well soon.

- Team Vennova
"""

    return await send_text_message(

        phone=phone,

        message=message
    )


# =====================================================
# VISIT THANK YOU
# =====================================================

async def send_visit_thank_you(

    phone: str,

    patient_name: str,

    clinic_name: str
):

    message = f"""
Dear {patient_name},

Thank you for visiting {clinic_name}.

We wish you good health.

- Team Vennova
"""

    return await send_text_message(

        phone=phone,

        message=message
    )


# =====================================================
# BIRTHDAY MESSAGE
# =====================================================

async def send_birthday_message(
        phone: str,
        patient_name: str,
        clinic_name: str,
        doctor_name: str = ""
):

    message = f"""
Happy Birthday {patient_name} 🎉

Wishing you happiness,
health and prosperity.

- {clinic_name}
"""

    return await send_text_message(

        phone=phone,

        message=message
    )

# =====================================================
# BILLING RECEIPT MESSAGE
# =====================================================

async def send_billing_receipt(
        phone: str,
        patient_name: str,
        clinic_name: str,
        receipt_url: str,
        amount: str
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
            "name": "billing_receipt",
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": patient_name
                        },
                        {
                            "type": "text",
                            "text": clinic_name
                        },
                        {
                            "type": "text",
                            "text": receipt_url
                        },
                        {
                            "type": "text",
                            "text": amount
                        }
                    ]
                }
            ]
        }
    }

    response = requests.post(
        WHATSAPP_API_URL,
        headers=headers,
        json=payload
    )

    data = response.json()

    return {
        "status": "sent" if response.status_code in [200, 201] else "failed",
        "response": data
    }