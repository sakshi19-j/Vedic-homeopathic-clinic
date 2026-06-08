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
from app.services.whatsapp_service import send_text_message
from app.utils.storage import upload_pdf

logger = logging.getLogger(__name__)


# =====================================================
# GENERATE PRESCRIPTION
# =====================================================

def generate_prescription(
    db: Session,
    visit_id: str,
    clinic_id: str
) -> dict:

    # ──────────────────────────────────────────────────
    # FETCH RECORDS
    # ──────────────────────────────────────────────────

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == clinic_id
    ).first()

    if not visit:
        raise HTTPException(404, "Visit not found")

    patient = db.query(Patient).filter(
        Patient.id == visit.patient_id,
        Patient.clinic_id == clinic_id
    ).first()

    if not patient:
        raise HTTPException(404, "Patient not found")

    clinic = db.query(Clinic).filter(
        Clinic.id == clinic_id
    ).first()

    if not clinic:
        raise HTTPException(404, "Clinic not found")

    # ──────────────────────────────────────────────────
    # VISIT TYPE
    # ──────────────────────────────────────────────────

    visit_type = (
        visit.type.value.upper()
        if hasattr(visit.type, "value")
        else str(visit.type).upper()
    )

    if "." in visit_type:
        visit_type = visit_type.split(".")[-1]

    rx_notes = ""

    # ──────────────────────────────────────────────────
    # ALLOPATHY
    # ──────────────────────────────────────────────────

    if visit.allopathy_rx:

        rx = visit.allopathy_rx

        medicines = []

        if rx.medicines:

            try:
                medicines = json.loads(rx.medicines)

            except Exception:
                medicines = []

        for med in medicines:

            rx_notes += (
                f"• {med.get('name', '')} | "
                f"{med.get('dosage', '')} | "
                f"{med.get('frequency', '')} | "
                f"{med.get('duration', '')}\n"
            )

        if rx.advice:

            rx_notes += (
                f"\nAdvice: {rx.advice}\n"
            )

    # ──────────────────────────────────────────────────
    # HOMEOPATHY
    # ──────────────────────────────────────────────────

    elif visit.homeopathy_case:

        hc = visit.homeopathy_case

        # SAFE PATIENT PRESCRIPTION
        # DO NOT expose remedy names

        if hc.patient_rx:

            rx_notes += hc.patient_rx

        else:

            rx_notes += (
                "Take medicines as prescribed "
                "by your doctor."
            )

    # ──────────────────────────────────────────────────
    # HOMEOPATHY CASE DATA
    # ──────────────────────────────────────────────────

    homeopathy_case = {}

    rubrics = []

    if visit.homeopathy_case:

        hc = visit.homeopathy_case

        # INTERNAL ONLY
        # NOT SHOWN TO PATIENT PDF

        homeopathy_case = {

            "remedy": hc.remedy or "",

            "potency": hc.potency or "",

            "repetition": hc.repetition or "",

            "miasm": hc.miasm or "",
        }

        if hc.rubrics:

            try:
                rubrics = json.loads(hc.rubrics)

            except Exception:
                rubrics = []

    # ──────────────────────────────────────────────────
    # ALLOPATHY TABLE DATA
    # ──────────────────────────────────────────────────

    medicines_list = []

    advice = ""

    next_visit = ""

    diagnosis = ""

    if visit.allopathy_rx:

        rx = visit.allopathy_rx

        if rx.medicines:

            try:
                medicines_list = json.loads(
                    rx.medicines
                )

            except Exception:
                medicines_list = []

        advice = rx.advice or ""

        next_visit = (
            rx.next_visit_date.strftime("%d %b %Y")
            if rx.next_visit_date else ""
        )

    # ──────────────────────────────────────────────────
    # VISIT DICT
    # ──────────────────────────────────────────────────

    visit_dict = {

        "id": visit.id,

        "rx": rx_notes,

        "notes": visit.notes or "",

        "chief_complaint":
            visit.chief_complaint or "",

        "visit_type": visit_type,

        "diagnosis": diagnosis,

        "advice": advice,

        "next_visit_date": next_visit,

        "medicines": medicines_list,

        "homeopathy_case": homeopathy_case,

        "rubrics": rubrics,
    }

    # ──────────────────────────────────────────────────
    # CLINIC DATA
    # ──────────────────────────────────────────────────

    clinic_dict = {

        "name": clinic.name,

        "doctor_name":
            clinic.doctor_name,

        "qualification":
            clinic.qualification or "",

        "address":
            clinic.address or "",

        "phone":
            clinic.phone or "",

        "timings":
            clinic.timings or "",

        "logo_url":
            getattr(clinic, "logo_url", None),

        "signature_url":
            getattr(clinic, "signature_url", None),

        "reg_number":
            getattr(clinic, "registration_number", ""),
    }

    # ──────────────────────────────────────────────────
    # PATIENT DATA
    # ──────────────────────────────────────────────────

    gender_val = ""

    if patient.gender:

        gender_val = (
            patient.gender.value
            if hasattr(patient.gender, "value")
            else str(patient.gender)
        )

        if "." in gender_val:
            gender_val = gender_val.split(".")[-1]

    patient_dict = {

        "name":
            f"{patient.first_name} "
            f"{patient.last_name or ''}".strip(),

        "age":
            patient.age or "",

        "gender":
            gender_val,

        "reg_no":
            patient.reg_no
            if hasattr(patient, "reg_no")
            else "",
    }

    # ──────────────────────────────────────────────────
    # DOCTOR DATA
    # ──────────────────────────────────────────────────

    doctor_dict = {

        "name":
            clinic.doctor_name or "Doctor",

        "qualification":
            clinic.qualification or "B.H.M.S.",
    }

    # ──────────────────────────────────────────────────
    # GENERATE PDF
    # ──────────────────────────────────────────────────

    pdf_bytes = generate_prescription_pdf(

        visit=visit_dict,

        clinic=clinic_dict,

        doctor=doctor_dict,

        patient=patient_dict
    )

    # ──────────────────────────────────────────────────
    # TEMP FILE + UPLOAD
    # ──────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────
    # SAVE URL + TOKEN
    # ──────────────────────────────────────────────────

    try:

        if hasattr(visit, "prescription_url"):

            visit.prescription_url = pdf_url

            # SECURE PRESCRIPTION TOKEN
            visit.prescription_token = (
                secrets.token_urlsafe(16)
            )

            db.commit()

    except Exception as e:

        logger.warning(
            f"Could not save prescription_url/token: {e}"
        )

    # ──────────────────────────────────────────────────
    # WHATSAPP
    # ──────────────────────────────────────────────────

    try:

        opted_out = getattr(
            patient,
            "whatsapp_opted_out",
            False
        )

        if patient.phone_mobile and not opted_out:

            msg = (
                f"Hi {patient_dict['name']}, your prescription from "
                f"Dr. {clinic_dict['doctor_name']} is ready:\n\n"
                f"{pdf_url}\n\n"
                f"Save this for your records. "
                f"For queries call {clinic_dict['phone']}"
            )

            try:

                loop = asyncio.get_running_loop()

                loop.create_task(

                    send_text_message(
                        patient.phone_mobile,
                        msg,
                        clinic_id=str(clinic_id),
                        patient_id=str(patient.id),
                        trigger="prescription_generated"
                    )
                )

            except RuntimeError:

                asyncio.run(

                    send_text_message(
                        patient.phone_mobile,
                        msg,
                        clinic_id=str(clinic_id),
                        patient_id=str(patient.id),
                        trigger="prescription_generated"
                    )
                )

    except Exception as e:

        logger.error(
            f"WhatsApp prescription send failed: {e}"
        )

    # ──────────────────────────────────────────────────
    # RESPONSE
    # ──────────────────────────────────────────────────

    return {

        "message":
            "Prescription generated successfully",

        "pdf_url":
            pdf_url,

        "visit_id":
            visit_id,

        "patient":
            patient_dict["name"],

        "visit_type":
            visit_type,

        "prescription_token":
            visit.prescription_token,

        "whatsapp_sent": (
            bool(patient.phone_mobile)
            and not getattr(
                patient,
                "whatsapp_opted_out",
                False
            )
        )
    }