import json
import logging
import tempfile
import os
import asyncio
import secrets

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.visit import Visit
from app.models.patient import Patient
from app.models.clinic import Clinic

from app.services.pdf_service import generate_prescription_pdf
from app.services.whatsapp_service import (
    send_prescription_message
)
from app.utils.storage import upload_pdf

logger = logging.getLogger(__name__)


# =====================================================
# GENERATE PRESCRIPTION
# =====================================================

async def generate_prescription(
    db: Session,
    visit_id: str,
    clinic_id: str,
    send_whatsapp: bool = True
) -> dict:

    # =================================================
    # FETCH VISIT
    # =================================================

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == clinic_id
    ).first()

    if not visit:

        raise HTTPException(
            status_code=404,
            detail="Visit not found"
        )

    # =================================================
    # FETCH PATIENT
    # =================================================

    patient = db.query(Patient).filter(
        Patient.id == visit.patient_id,
        Patient.clinic_id == clinic_id
    ).first()

    if not patient:

        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    # =================================================
    # FETCH CLINIC
    # =================================================

    clinic = db.query(Clinic).filter(
        Clinic.id == clinic_id
    ).first()

    if not clinic:

        raise HTTPException(
            status_code=404,
            detail="Clinic not found"
        )

    # =================================================
    # GENERATE TOKEN
    # =================================================

    if not visit.prescription_token:

        visit.prescription_token = (
            secrets.token_urlsafe(16)
        )

        db.commit()

        db.refresh(visit)

    # =================================================
    # VISIT TYPE
    # =================================================

    visit_type = (

        visit.type.value.upper()

        if hasattr(visit.type, "value")

        else str(visit.type).upper()
    )

    rx_notes = ""

    medicines_list = []

    advice = ""

    next_visit = ""

    diagnosis = visit.diagnosis or ""

    # =================================================
    # ALLOPATHY
    # =================================================

    if visit.allopathy_rx:

        rx = visit.allopathy_rx

        if rx.medicines:

            try:

                medicines_list = json.loads(
                    rx.medicines
                )

            except Exception:

                medicines_list = []

        for med in medicines_list:

            rx_notes += (

                f"• {med.get('name', '')} | "
                f"{med.get('dosage', '')} | "
                f"{med.get('frequency', '')} | "
                f"{med.get('duration', '')}\n"
            )

        advice = rx.advice or ""

        next_visit = (

            rx.next_visit_date.strftime("%d %b %Y")

            if rx.next_visit_date
            else ""
        )

    # =================================================
    # HOMEOPATHY
    # =================================================

    elif visit.homeopathy_case:
        hc = visit.homeopathy_case
        patient_rx_raw = hc.patient_rx or ""
        if "\n\nAdvice: " in patient_rx_raw:
            rx_part, advice_part = patient_rx_raw.split("\n\nAdvice: ", 1)
        else:
            rx_part, advice_part = patient_rx_raw, ""
        rx_notes += rx_part or "Take medicines as prescribed by your doctor."
        advice = advice_part

# Pull BOX-style medicines saved via the Medicine table (homeopathy flow)
    from app.models.medicine import Medicine
    box_medicines = db.query(Medicine).filter(Medicine.visit_id == visit.id).all()
    if box_medicines:
        medicines_list = [
            {
                "name": m.name,
                "dosage": m.potency or "",
                "timing": m.timing or "",
                "duration": m.days or "",
                "food_relation": m.food_relation or "",
            }
            for m in box_medicines
        ]
    # =================================================
    # HOMEOPATHY CASE
    # =================================================

    homeopathy_case = {}

    rubrics = []

    if visit.homeopathy_case:

        hc = visit.homeopathy_case

        homeopathy_case = {

            "remedy":
                hc.remedy or "",

            "potency":
                hc.potency or "",

            "repetition":
                hc.repetition or "",

            "miasm":
                hc.miasm or "",
        }

        if hc.rubrics:

            try:

                rubrics = json.loads(
                    hc.rubrics
                )

            except Exception:

                rubrics = []

    # =================================================
    # VISIT DICT
    # =================================================

    visit_dict = {

        "id":
            visit.id,

        "token":
            visit.prescription_token,

        "backend_url":
            "https://natural-success-production.up.railway.app",

        "rx":
            rx_notes,

        "notes":
            visit.notes or "",

        "chief_complaint":
            visit.chief_complaint or "",

        "visit_type":
            visit_type,

        "diagnosis":
            diagnosis,

        "advice":
            advice,

        "next_visit_date":
            next_visit,

        "medicines":
            medicines_list,

        "homeopathy_case":
            homeopathy_case,

        "rubrics":
            rubrics,
        
        "patient_rx": (hc.patient_rx or "") if visit.homeopathy_case else "",
        "remedy": (hc.remedy or "") if visit.homeopathy_case else "",
        "potency": (hc.potency or "") if visit.homeopathy_case else "",
        "repetition": (hc.repetition or "") if visit.homeopathy_case else "",
        "miasm": (hc.miasm or "") if visit.homeopathy_case else "",
    }

    # =================================================
    # CLINIC DICT
    # =================================================

    clinic_dict = {
        "name": clinic.name or "Clinic",
        "logo_url": clinic.logo_url,
        "doctor_name": clinic.doctor_name or "Doctor",
        "qualification": clinic.qualification or "",
        "phone": clinic.phone or "",
        "email": clinic.email or "",
        "website": clinic.website or "",
        "address": clinic.address or "",
        "timings": clinic.timings or "",
        "footer_text": clinic.footer_text or "",
        "signature_url": clinic.signature_url,
        "primary_color": clinic.primary_color or "#5B21B6",
        "secondary_color": clinic.secondary_color or "#EDE9FE",
        "prescription_theme": clinic.prescription_theme or "CLASSIC_BLUE",
    }
    # =================================================
    # PATIENT DICT
    # =================================================

    patient_dict = {

        "name":
            f"{patient.first_name} "
            f"{patient.last_name or ''}".strip(),

        "age":
            patient.age or "",

        "gender":
            (
                patient.gender.value

                if patient.gender
                else ""
            ),
    }

    # =================================================
    # DOCTOR DICT
    # =================================================

    doctor_dict = {

        "name":
            clinic.doctor_name or "Doctor",

        "qualification":
            clinic.qualification or "B.H.M.S.",
    }

    # =================================================
    # GENERATE PDF
    # =================================================

    pdf_bytes = generate_prescription_pdf(

        visit=visit_dict,

        clinic=clinic_dict,

        doctor=doctor_dict,

        patient=patient_dict
    )

    # =================================================
    # TEMP FILE
    # =================================================

    pdf_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as tmp:

            tmp.write(pdf_bytes)

            pdf_path = tmp.name

        pdf_url = upload_pdf(
            pdf_path,
            folder="prescriptions"
        )

    finally:

        if pdf_path and os.path.exists(pdf_path):

            try:

                os.unlink(pdf_path)

            except Exception:
                pass

    # =================================================
    # SAVE URL
    # =================================================

    # =================================================
    # SAVE URL
    # =================================================

    visit.prescription_url = pdf_url

    db.add(visit)
    db.commit()
    db.refresh(visit)

    # =================================================
    # SECURE URL
    # =================================================

    # =================================================
    # SECURE URL
    # =================================================

    secure_url = (

        f"https://natural-success-production.up.railway.app"
        f"/prescriptions/rx/"
        f"{visit.prescription_token}"
    )
    
    # =================================================
    # WHATSAPP
    # =================================================

    if send_whatsapp and patient.phone_mobile:

        try:

            wa_result = await send_prescription_message(
                phone=patient.phone_mobile,
                patient_name=patient.first_name or "Patient",
                clinic_name=clinic.name or "Your Clinic",
                prescription_url=secure_url,
                support_phone=clinic.phone or "N/A"
            )
            
            logger.info(
                f"Prescription WhatsApp result: {wa_result}"
            )

        except Exception as e:

            logger.error(
                f"Prescription WhatsApp failed: {e}"
            )
    # =================================================
    # RESPONSE
    # =================================================

    return {

        "message":
            "Prescription generated successfully",

        "pdf_url":
            pdf_url,

        "secure_url":
            secure_url,

        "token":
            visit.prescription_token,

        "visit_id":
            visit.id
    }