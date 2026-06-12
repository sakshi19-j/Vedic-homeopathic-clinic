import httpx
import os
import logging
import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

import pytz


logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


# =====================================================
# ENV
# =====================================================

WHATSAPP_ACCESS_TOKEN = os.getenv(
    "WHATSAPP_ACCESS_TOKEN"
)

WHATSAPP_PHONE_NUMBER_ID = os.getenv(
    "WHATSAPP_PHONE_NUMBER_ID"
)

WHATSAPP_API_VERSION = os.getenv(
    "WHATSAPP_API_VERSION",
    "v19.0"
)

WHATSAPP_API_URL = (
    f"https://graph.facebook.com/"
    f"{WHATSAPP_API_VERSION}"
)

DAILY_LIMIT = int(
    os.getenv(
        "WHATSAPP_DAILY_LIMIT",
        "950"
    )
)


# =====================================================
# NORMALIZE PHONE
# =====================================================

def normalize_phone(phone: str) -> str:

    if not phone:
        return ""

    phone = ''.join(
        filter(str.isdigit, str(phone))
    )

    # India fallback
    if len(phone) == 10:
        phone = f"91{phone}"

    return phone


# =====================================================
# HEADERS
# =====================================================

def get_headers():

    return {

        "Authorization":
            f"Bearer {WHATSAPP_ACCESS_TOKEN}",

        "Content-Type":
            "application/json"
    }


# =====================================================
# API URL
# =====================================================

def get_api_url():

    return (
        f"{WHATSAPP_API_URL}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


# =====================================================
# RETRY REQUEST
# =====================================================

async def _send_with_retry(
    payload: dict,
    max_retries: int = 2
):

    last_status = 500
    last_data = {}

    for attempt in range(max_retries + 1):

        try:

            async with httpx.AsyncClient(
                timeout=15.0
            ) as client:

                response = await client.post(

                    get_api_url(),

                    headers=get_headers(),

                    json=payload
                )

                last_status = response.status_code

                last_data = response.json()

                # =====================================
                # DEBUG LOG
                # =====================================

                print("\n")
                print("WHATSAPP STATUS:")
                print(last_status)

                print("\nWHATSAPP RESPONSE:")
                print(last_data)
                print("\n")

                # =====================================
                # SUCCESS
                # =====================================

                if last_status in [200, 201]:

                    return (
                        last_status,
                        last_data
                    )

                # =====================================
                # DON'T RETRY CLIENT ERRORS
                # =====================================

                if last_status in [
                    400,
                    401,
                    403,
                    404
                ]:

                    return (
                        last_status,
                        last_data
                    )

                # =====================================
                # RETRY DELAY
                # =====================================

                if attempt < max_retries:

                    delay = (
                        2 ** attempt
                    )

                    await asyncio.sleep(delay)

        except Exception as e:

            print("\nWHATSAPP EXCEPTION:")
            print(str(e))

            last_data = {
                "error": str(e)
            }

    return (
        last_status,
        last_data
    )


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
):

    # ================================================
    # NORMALIZE PHONE
    # ================================================

    normalized = normalize_phone(phone)

    if not normalized:

        return {

            "status": "failed",

            "error": "Invalid phone number"
        }

    # ================================================
    # MOCK MODE
    # ================================================

    if not WHATSAPP_ACCESS_TOKEN:

        print("\nMOCK WHATSAPP SEND")
        print(normalized)
        print(message)

        return {

            "status": "mocked",

            "message_id": "mocked_message",

            "phone": normalized
        }

    # ================================================
    # PAYLOAD
    # ================================================

    payload = {

        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            normalized,

        "type":
            "text",

        "text": {

            "preview_url": True,

            "body": message
        }
    }

    # ================================================
    # SEND
    # ================================================

    status_code, data = await _send_with_retry(
        payload
    )

    # ================================================
    # SUCCESS
    # ================================================

    if status_code in [200, 201]:

        return {

            "status": "sent",

            "message_id": (

                data.get(
                    "messages",
                    [{}]
                )[0].get("id")
            ),

            "phone": normalized
        }

    # ================================================
    # FAILED
    # ================================================

    return {

        "status": "failed",

        "error": data,

        "phone": normalized
    }


# =====================================================
# SEND TEMPLATE MESSAGE
# =====================================================

async def send_template_message(

    phone: str,

    template_name: str,

    language: str,

    components: list = None,

    db: Session = None,

    clinic_id: str = None,

    patient_id: str = None,

    trigger: str = "manual"
):

    normalized = normalize_phone(phone)

    if not normalized:

        return {

            "status": "failed",

            "error": "Invalid phone number"
        }

    payload = {

        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            normalized,

        "type":
            "template",

        "template": {

            "name":
                template_name,

            "language": {

                "code":
                    language
            },

            "components":
                components or []
        }
    }

    status_code, data = await _send_with_retry(
        payload
    )

    if status_code in [200, 201]:

        return {

            "status": "sent",

            "message_id": (

                data.get(
                    "messages",
                    [{}]
                )[0].get("id")
            ),

            "template":
                template_name,

            "phone":
                normalized
        }

    return {

        "status": "failed",

        "error": data,

        "template":
            template_name,

        "phone":
            normalized
    }