from fastapi import APIRouter, Depends, HTTPException

from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db

from app.services.prescription_service import (
    generate_prescription
)

from app.services.whatsapp_service import (
    send_text_message
)

from app.middleware.auth_middleware import (
    doctor_only
)

from app.models.user import User

from app.models.patient import Patient

from app.models.clinic import Clinic

from app.models.visit import Visit


# =====================================================
# ROUTER
# =====================================================

router = APIRouter(

    prefix="/prescriptions",

    tags=["Prescriptions"]
)


# =====================================================
# GENERATE PRESCRIPTION
# =====================================================

@router.post("/generate/{visit_id}")
def create_prescription(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        doctor_only
    )
):

    return generate_prescription(

        db,

        visit_id,

        current_user.clinic_id
    )


# =====================================================
# DOWNLOAD PRESCRIPTION
# =====================================================

@router.get("/download/{visit_id}")
def download_prescription(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        doctor_only
    )
):

    result = generate_prescription(

        db,

        visit_id,

        current_user.clinic_id
    )

    pdf_url = result.get("pdf_url")

    if not pdf_url:

        raise HTTPException(

            status_code=404,

            detail="Prescription file not found"
        )

    return RedirectResponse(
        url=pdf_url
    )


# =====================================================
# SEND PRESCRIPTION WHATSAPP
# =====================================================

@router.post("/send/{visit_id}")
async def send_prescription_whatsapp(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        doctor_only
    )
):

    # =====================================================
    # GENERATE PDF
    # =====================================================

    result = generate_prescription(

        db,

        visit_id,

        current_user.clinic_id
    )

    # =====================================================
    # FETCH VISIT
    # =====================================================

    visit = db.query(Visit).filter(

        Visit.id == visit_id

    ).first()

    if not visit:

        raise HTTPException(

            status_code=404,

            detail="Visit not found"
        )

    # =====================================================
    # FETCH PATIENT
    # =====================================================

    patient = db.query(Patient).filter(

        Patient.id == visit.patient_id

    ).first()

    if not patient:

        raise HTTPException(

            status_code=404,

            detail="Patient not found"
        )

    # =====================================================
    # FETCH CLINIC
    # =====================================================

    clinic = db.query(Clinic).filter(

        Clinic.id == current_user.clinic_id

    ).first()

    if not clinic:

        raise HTTPException(

            status_code=404,

            detail="Clinic not found"
        )

    # =====================================================
    # VALIDATE PHONE
    # =====================================================

    if not getattr(patient, "phone_mobile", None):

        raise HTTPException(

            status_code=400,

            detail="Patient has no mobile number"
        )

    # =====================================================
    # OPT OUT CHECK
    # =====================================================

    if getattr(patient, "whatsapp_opted_out", False):

        return {

            "success": False,

            "message": "Patient opted out of WhatsApp",

            "patient": (
                f"{patient.first_name} "
                f"{patient.last_name or ''}"
            ).strip()
        }

    # =====================================================
    # BUILD MESSAGE
    # =====================================================

    clinic_name = clinic.name or "Clinic"

    doctor_name = clinic.doctor_name or "Doctor"

    clinic_phone = clinic.phone or ""

    patient_name = (

        f"{patient.first_name} "
        f"{patient.last_name or ''}"

    ).strip()

    message = (

        f"Dear {patient_name},\n\n"

        f"Your prescription from "
        f"{clinic_name} is ready.\n\n"

        f"Doctor: Dr. {doctor_name}\n\n"

        f"Prescription PDF:\n"

        f"{result['pdf_url']}\n\n"

        f"For assistance call:\n"

        f"{clinic_phone}\n\n"

        f"- Powered by Vennova"
    )

    # =====================================================
    # SEND WHATSAPP
    # =====================================================

    try:

        whatsapp_result = await send_text_message(

            phone=patient.phone_mobile,

            message=message,

            db=db,

            clinic_id=str(current_user.clinic_id),

            patient_id=str(patient.id),

            trigger="prescription_send"
        )

    except Exception as e:

        whatsapp_result = {

            "status": "failed",

            "error": str(e)
        }

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {

        "success": (

            whatsapp_result.get("status")

            in ["sent", "mocked"]

        ),

        "message": (

            "Prescription sent successfully"

            if whatsapp_result.get("status")

            in ["sent", "mocked"]

            else "Prescription send failed"
        ),

        "pdf_url":

            result.get("pdf_url"),

        "patient":

            patient_name,

        "visit_type":

            result.get("visit_type"),

        "whatsapp":

            whatsapp_result
    }