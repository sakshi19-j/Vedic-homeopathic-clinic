import os
from datetime import datetime
from app.models.reminder import Channel
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────
# MESSAGE TEMPLATES
# Multi-language templates for better patient engagement
# Supported languages:
# en = English
# hi = Hindi
# mr = Marathi
# ─────────────────────────────────────────────────────────────

TEMPLATES = {

    # ── 3 DAY FOLLOWUP ──────────────────────────────────────
    "followup_3d": {
        "en": (
            "Dear {name}, hope you are feeling better after your visit "
            "at {clinic}. Dr. {doctor} is checking on your progress. "
            "If you have any concerns please visit us or call {phone} 🙏"
        ),
        "hi": (
            "प्रिय {name}, {clinic} में आपकी visit के बाद आप कैसा "
            "महसूस कर रहे हैं? Dr. {doctor} आपकी care करते हैं। "
            "कोई भी समस्या हो तो call करें: {phone} 🙏"
        ),
        "mr": (
            "प्रिय {name}, {clinic} ला भेट दिल्यानंतर तुम्ही कसे "
            "आहात? Dr. {doctor} तुमची काळजी घेतात. "
            "काही त्रास असल्यास call करा: {phone} 🙏"
        ),
    },

    # ── 7 DAY FOLLOWUP ──────────────────────────────────────
    "followup_7d": {
        "en": (
            "Dear {name}, it has been a week since your visit at {clinic}. "
            "Dr. {doctor} recommends a follow-up checkup to monitor "
            "your progress. Please book your appointment: {phone} ✅"
        ),
        "hi": (
            "प्रिय {name}, {clinic} में आपकी visit को एक हफ्ता हो गया है। "
            "Dr. {doctor} आपका follow-up checkup recommend करते हैं। "
            "Appointment के लिए call करें: {phone} ✅"
        ),
        "mr": (
            "प्रिय {name}, {clinic} ला भेट देऊन एक आठवडा झाला. "
            "Dr. {doctor} follow-up तपासणी सुचवतात. "
            "Appointment साठी call करा: {phone} ✅"
        ),
    },

    # ── 15 DAY FOLLOWUP ─────────────────────────────────────
    "followup_15d": {
        "en": (
            "Dear {name}, Dr. {doctor} from {clinic} would like to "
            "review your treatment progress. A follow-up visit will "
            "ensure you are on the right path to recovery. Call: {phone}"
        ),
        "hi": (
            "प्रिय {name}, Dr. {doctor} आपके treatment की progress "
            "देखना चाहते हैं। Follow-up visit से आपकी recovery "
            "बेहतर होगी। Call करें: {phone}"
        ),
        "mr": (
            "प्रिय {name}, Dr. {doctor} तुमच्या उपचाराची प्रगती "
            "पाहू इच्छितात. Follow-up visit तुमच्या बरे होण्यास "
            "मदत करेल. Call करा: {phone}"
        ),
    },

    # ── MONTHLY FOLLOWUP ────────────────────────────────────
    "followup_monthly": {
        "en": (
            "Dear {name}, your monthly checkup is due at {clinic}. "
            "Regular follow-ups help Dr. {doctor} give you the best "
            "treatment. Book now: {phone} 📅"
        ),
        "hi": (
            "प्रिय {name}, {clinic} में आपका monthly checkup बाकी है। "
            "Regular follow-up से Dr. {doctor} आपको बेहतर treatment "
            "दे सकते हैं। अभी book करें: {phone} 📅"
        ),
        "mr": (
            "प्रिय {name}, {clinic} मध्ये तुमची monthly तपासणी बाकी आहे. "
            "नियमित follow-up मुळे Dr. {doctor} तुम्हाला उत्तम "
            "उपचार देऊ शकतात. आता book करा: {phone} 📅"
        ),
    },

    # ── THANK YOU MESSAGE ───────────────────────────────────
    "thankyou": {
        "en": (
            "Dear {name}, thank you for visiting {clinic} today. "
            "Dr. {doctor} wishes you a speedy recovery. "
            "Take care and follow the prescribed treatment. "
            "For any queries call: {phone} 🙏"
        ),
        "hi": (
            "प्रिय {name}, आज {clinic} में आने के लिए धन्यवाद। "
            "Dr. {doctor} आपके जल्द ठीक होने की कामना करते हैं। "
            "Prescribed treatment follow करें। "
            "Call: {phone} 🙏"
        ),
        "mr": (
            "प्रिय {name}, आज {clinic} ला भेट दिल्याबद्दल धन्यवाद. "
            "Dr. {doctor} तुमच्या लवकर बरे होण्याची इच्छा करतात. "
            "दिलेले उपचार follow करा. Call: {phone} 🙏"
        ),
    },

    # ── BIRTHDAY MESSAGE ────────────────────────────────────
    "birthday": {
        "en": (
            "🎂 Dear {name}, wishing you a very Happy Birthday! "
            "May this year bring you good health and happiness. "
            "From Dr. {doctor} and the entire team at {clinic}. "
            "Stay healthy! 💐"
        ),
        "hi": (
            "🎂 प्रिय {name}, जन्मदिन की हार्दिक शुभकामनाएं! "
            "यह साल आपके लिए स्वास्थ्य और खुशियां लेकर आए। "
            "Dr. {doctor} और {clinic} की पूरी team की ओर से। "
            "स्वस्थ रहें! 💐"
        ),
        "mr": (
            "🎂 प्रिय {name}, वाढदिवसाच्या हार्दिक शुभेच्छा! "
            "हे वर्ष तुम्हाला आरोग्य आणि आनंद देवो. "
            "Dr. {doctor} आणि {clinic} टीमकडून. "
            "निरोगी राहा! 💐"
        ),
    },

    # ── MISSED PATIENT ──────────────────────────────────────
    "missed_patient": {
        "en": (
            "Dear {name}, we have been missing you at {clinic}. "
            "Dr. {doctor} is concerned about your health. "
            "Please visit us for a checkup when you get time. "
            "Call: {phone} ❤️"
        ),
        "hi": (
            "प्रिय {name}, {clinic} में आपकी याद आ रही है। "
            "Dr. {doctor} आपकी health को लेकर concerned हैं। "
            "जब time मिले, checkup के लिए आएं। "
            "Call: {phone} ❤️"
        ),
        "mr": (
            "प्रिय {name}, {clinic} मध्ये तुमची आठवण येत आहे. "
            "Dr. {doctor} तुमच्या आरोग्याबद्दल काळजीत आहेत. "
            "वेळ मिळाल्यावर तपासणीसाठी या. "
            "Call: {phone} ❤️"
        ),
    }
}

# ─────────────────────────────────────────────────────────────
# TEMPLATE FUNCTIONS
# ─────────────────────────────────────────────────────────────

def get_template(template_key: str, language: str = "en") -> str:
    """
    Fetch template by key and language.
    Falls back to English if language not found.
    """

    templates = TEMPLATES.get(template_key)

    if not templates:
        templates = TEMPLATES["followup_7d"]

    return templates.get(language, templates["en"])


def fill_template(
    template: str,
    patient_name: str,
    doctor_name: str,
    clinic_name: str,
    clinic_phone: str
) -> str:
    """
    Replace placeholders with actual values.
    """

    return template.format(
        name=patient_name,
        doctor=doctor_name,
        clinic=clinic_name,
        phone=clinic_phone
    )


# ─────────────────────────────────────────────────────────────
# WHATSAPP SENDER
# ─────────────────────────────────────────────────────────────

def send_whatsapp(phone: str, message: str) -> dict:
    """
    Send WhatsApp message using Twilio.
    Falls back to MOCK mode if credentials are missing.
    """

    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from = os.getenv("TWILIO_WHATSAPP_FROM", "")

    # REAL SEND
    if twilio_sid and twilio_token and twilio_from:

        try:
            from twilio.rest import Client

            client = Client(twilio_sid, twilio_token)

            msg = client.messages.create(
                from_=f"whatsapp:{twilio_from}",
                to=f"whatsapp:+91{phone}",
                body=message
            )

            return {
                "status": "sent",
                "channel": "whatsapp",
                "sid": msg.sid,
                "phone": phone
            }

        except Exception as e:

            return {
                "status": "failed",
                "channel": "whatsapp",
                "error": str(e),
                "phone": phone
            }

    # MOCK MODE
    print("\n📱 WHATSAPP MOCK")
    print(f"To: +91{phone}")
    print(f"Message: {message}")
    print(
        f"Time: {datetime.now(IST).strftime('%d-%m-%Y %H:%M')}\n"
    )

    return {
        "status": "mocked",
        "channel": "whatsapp",
        "phone": phone,
        "message": message,
        "note": "Add Twilio credentials to enable real sending"
    }


# ─────────────────────────────────────────────────────────────
# SMS SENDER
# ─────────────────────────────────────────────────────────────

def send_sms(phone: str, message: str) -> dict:
    """
    Send SMS using Twilio.
    """

    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")

    if twilio_sid and twilio_token:

        try:
            from twilio.rest import Client

            client = Client(twilio_sid, twilio_token)

            msg = client.messages.create(
                from_=os.getenv("TWILIO_SMS_FROM", ""),
                to=f"+91{phone}",
                body=message
            )

            return {
                "status": "sent",
                "channel": "sms",
                "sid": msg.sid
            }

        except Exception as e:

            return {
                "status": "failed",
                "channel": "sms",
                "error": str(e)
            }

    # MOCK MODE
    print("\n📨 SMS MOCK")
    print(f"To: +91{phone}")
    print(f"Message: {message}\n")

    return {
        "status": "mocked",
        "channel": "sms",
        "phone": phone,
        "message": message
    }


# ─────────────────────────────────────────────────────────────
# MAIN NOTIFICATION ROUTER
# ─────────────────────────────────────────────────────────────

def send_notification(
    channel: str,
    phone: str,
    message: str
) -> dict:
    """
    Main notification router.
    """

    if channel == "WHATSAPP":
        return send_whatsapp(phone, message)

    elif channel == "SMS":
        return send_sms(phone, message)

    # DEFAULT = WHATSAPP
    return send_whatsapp(phone, message)

# ─────────────────────────────────────────────────────────────
# META CLOUD API SENDER (primary — replaces Twilio)
# ─────────────────────────────────────────────────────────────

async def send_whatsapp_meta(phone: str, message: str) -> dict:
    """
    Send WhatsApp via Meta Cloud API.
    Used by cron jobs — async.
    """
    import httpx, os
    token           = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

    if not token or not phone_number_id:
        print(f"📱 MOCK → +91{phone}: {message[:60]}...")
        return {"status": "mocked", "phone": phone}

    # Normalize phone
    clean = phone.strip().lstrip("+").lstrip("91").replace(" ", "").replace("-", "")

    url     = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type":    "individual",
        "to":                f"91{clean}",
        "type":              "text",
        "text":              {"body": message}
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            data = resp.json()
            if resp.status_code == 200:
                return {
                    "status":     "sent",
                    "message_id": data.get("messages", [{}])[0].get("id", ""),
                    "phone":      clean
                }
            return {"status": "failed", "error": data.get("error", {}).get("message"), "phone": clean}
        except Exception as e:
            return {"status": "failed", "error": str(e), "phone": clean}