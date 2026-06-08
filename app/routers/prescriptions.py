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

    current_user: User = Depends(
        doctor_only
    )
):

    # =================================================
    # GENERATE PRESCRIPTION
    # =================================================

    result = generate_prescription(

        db,

        visit_id,

        current_user.clinic_id
    )

    # =================================================
    # FETCH VISIT
    # =================================================

    visit = db.query(Visit).filter(

        Visit.id == visit_id,

        Visit.clinic_id == current_user.clinic_id

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

        Patient.clinic_id == current_user.clinic_id

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

        Clinic.id == current_user.clinic_id

    ).first()

    if not clinic:

        raise HTTPException(

            status_code=404,

            detail="Clinic not found"
        )

    # =================================================
    # CHECK MOBILE
    # =================================================

    if not patient.phone_mobile:

        raise HTTPException(

            status_code=400,

            detail="Patient mobile number missing"
        )

    # =================================================
    # WHATSAPP OPT OUT
    # =================================================

    opted_out = getattr(

        patient,

        "whatsapp_opted_out",

        False
    )

    if opted_out:

        raise HTTPException(

            status_code=400,

            detail=(
                "Patient has opted out "
                "from WhatsApp messages"
            )
        )

    # =================================================
    # SECURE URL
    # =================================================

    secure_url = (

        f"https://rx.vennovahealth.com/rx/"
        f"{visit.prescription_token}"
    )

    # =================================================
    # BUILD MESSAGE
    # =================================================

    patient_name = (

        f"{patient.first_name} "
        f"{patient.last_name or ''}"

    ).strip()

    message = (

        f"Hi {patient_name},\n\n"

        f"Your prescription from "
        f"Dr. {clinic.doctor_name} "
        f"is ready.\n\n"

        f"📄 Secure Prescription Link:\n\n"

        f"{secure_url}\n\n"

        f"Please save this prescription "
        f"for future reference.\n\n"

        f"For help contact:\n"

        f"{clinic.phone}\n\n"

        f"- Team Vennova"
    )

    # =================================================
    # SEND WHATSAPP
    # =================================================

    try:

        whatsapp_result = await send_text_message(

            phone=patient.phone_mobile,

            message=message,

            db=db,

            clinic_id=str(
                current_user.clinic_id
            ),

            patient_id=str(patient.id),

            trigger="prescription_send"
        )

    except Exception as e:

        whatsapp_result = {

            "status": "failed",

            "error": str(e)
        }

    # =================================================
    # RESPONSE
    # =================================================

    return {

        "success": (

            whatsapp_result.get("status")

            == "sent"
        ),

        "message": (

            f"Prescription sent to "
            f"{patient_name}"
        ),

        "pdf_url": (

            result.get("pdf_url")
        ),

        "secure_url": (

            secure_url
        ),

        "whatsapp": (

            whatsapp_result
        )
    }