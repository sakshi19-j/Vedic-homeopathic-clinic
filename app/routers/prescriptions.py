from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.responses import (
    RedirectResponse
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.services.prescription_service import (
    generate_prescription
)

from app.middleware.auth_middleware import (
    doctor_only,
    CurrentUser,
    check_subscription_with_grace
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
async def create_prescription(
     visit_id: str,
     db: Session = Depends(get_db),
     _: CurrentUser = Depends(check_subscription_with_grace),
     current_user: CurrentUser = Depends(doctor_only)
):
     # PDF only — does NOT message the patient.
     # Use /send/{visit_id} to deliver via WhatsApp.
     return await generate_prescription(
         db,
         visit_id,
         current_user.clinic_id,
         send_whatsapp=False
    )


# =====================================================
# DOWNLOAD PRESCRIPTION
# =====================================================

@router.get("/download/{visit_id}")
async def download_prescription(

    visit_id: str,

    db: Session = Depends(get_db),

    _: CurrentUser = Depends(check_subscription_with_grace),
    current_user: CurrentUser = Depends(
        doctor_only
    )
):

    result = await generate_prescription(

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
# SECURE PUBLIC RX LINK
# =====================================================

@router.get("/rx/{token}")
def open_prescription(

    token: str,

    db: Session = Depends(get_db)
):

    visit = db.query(Visit).filter(

        Visit.prescription_token == token

    ).first()

    if not visit:

        raise HTTPException(

            status_code=404,

            detail="Prescription not found"
        )

    if not visit.prescription_url:

        raise HTTPException(

            status_code=404,

            detail="PDF missing"
        )

    return RedirectResponse(

        url=visit.prescription_url
    )


# =====================================================
# SEND PRESCRIPTION WHATSAPP
# =====================================================

@router.post("/send/{visit_id}")
async def send_prescription_whatsapp(

    visit_id: str,

    db: Session = Depends(get_db),

    _: CurrentUser = Depends(check_subscription_with_grace),
    current_user: CurrentUser = Depends(
        doctor_only
    )
):

    # =================================================
    # FETCH PATIENT NAME FOR RESPONSE MESSAGE ONLY
    # generate_prescription() does its own validation
    # and already sends the WhatsApp message internally
    # =================================================

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == current_user.clinic_id
    ).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    patient = db.query(Patient).filter(
        Patient.id == visit.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not patient.phone_mobile:
        raise HTTPException(status_code=400, detail="Patient mobile number missing")

    if getattr(patient, "whatsapp_opted_out", False):
        raise HTTPException(
            status_code=400,
            detail="Patient has opted out from WhatsApp messages"
        )

    patient_name = f"{patient.first_name} {patient.last_name or ''}".strip()

    # =================================================
    # GENERATE + SEND (single source of truth — same
    # function visits.py calls, so PDF + WhatsApp stay
    # consistent no matter which route is hit)
    # =================================================

    result = await generate_prescription(
        db,
        visit_id,
        current_user.clinic_id
    )

    return {
        "success": True,
        "message": f"Prescription sent to {patient_name}",
        "pdf_url": result.get("pdf_url"),
        "secure_url": result.get("secure_url"),
    }