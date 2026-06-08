import asyncio

from app.services.whatsapp_service import send_text_message


async def send_medicine_reminder(
    patient,
    clinic,
    message
):

    if not patient.phone_mobile:
        return False

    await send_text_message(
        phone=patient.phone_mobile,
        message=message,
        clinic_id=str(clinic.id),
        patient_id=str(patient.id),
        trigger="medicine_reminder"
    )

    return True