import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.middleware.auth_middleware import (
    get_current_user,
    receptionist_or_doctor,
    doctor_only
)
from app.models.user import User
from app.schemas.visit import (
    VisitCreate,
    VitalsInput,
    AllopathyInput,
    HomeopathyInput,
    CloseVisitInput
)
from app.services import visit_service
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visits", tags=["Visits"])


# =====================================================
# CONSULTATION SCHEMA — dynamic by clinic type
# =====================================================

@router.get("/consultation-schema")
def consultation_schema(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns fields to render for consultation form
    based on clinic type (HOMEOPATHY / ALLOPATHY / AYURVEDIC).
    Frontend calls this on mount.
    """
    from app.models.clinic import Clinic
    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    clinic_type = clinic.clinic_type if clinic and clinic.clinic_type else "ALLOPATHY"

    return {
        "clinic_type": clinic_type,
        "fields":      visit_service.get_consultation_schema(clinic_type)
    }


# =====================================================
# CREATE VISIT
# =====================================================

@router.post("/")
def create_visit(
    request: Request,
    data: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Open a new visit for a patient.
    Receptionist or doctor creates this when patient arrives.
    """
    visit = visit_service.create_visit(
        db        = db,
        data      = data,
        clinic_id = current_user.clinic_id,
        doctor_id = str(current_user.id)
    )

    log_action(
        db          = db,
        user        = current_user,
        action      = "VISIT_CREATED",
        resource    = "visit",
        resource_id = visit.id,
        detail      = f"Opened visit for patient {data.patient_id} — type {data.type}",
        ip_address  = request.client.host if request else None,
    )

    return {
        "message":  "Visit created",
        "visit_id": visit.id,
        "status":   visit.visit_status,
        "type":     visit.type.value if visit.type else None
    }


# =====================================================
# GET VISIT
# =====================================================

@router.get("/{visit_id}")
def get_visit(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    return visit_service.get_visit(
        db        = db,
        visit_id  = visit_id,
        clinic_id = current_user.clinic_id
    )


# =====================================================
# WIZARD STATE — which step is the visit on?
# =====================================================

@router.get("/{visit_id}/wizard")
def get_wizard_state(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Returns current step (1-4) and completion status of each step.
    Frontend uses this to show the consultation wizard progress.
    """
    return visit_service.get_visit_wizard_state(
        db        = db,
        visit_id  = visit_id,
        clinic_id = current_user.clinic_id
    )


# =====================================================
# SAVE VITALS — Step 1
# =====================================================

@router.post("/{visit_id}/vitals")
def save_vitals(
    visit_id: str,
    data: VitalsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Save patient vitals for this visit.
    Receptionist or nurse fills this at front desk.
    """
    return visit_service.save_vitals(
        db        = db,
        visit_id  = visit_id,
        clinic_id = current_user.clinic_id,
        data      = data
    )


# =====================================================
# SAVE ALLOPATHY RX — Step 2 (Allopathy clinics)
# =====================================================

@router.post("/{visit_id}/allopathy")
def save_allopathy(
    visit_id: str,
    data: AllopathyInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(doctor_only)
):
    """
    Save allopathy prescription — doctor only.
    """
    result = visit_service.save_allopathy_rx(
        db        = db,
        visit_id  = visit_id,
        clinic_id = current_user.clinic_id,
        data      = data
    )

    log_action(
        db          = db,
        user        = current_user,
        action      = "PRESCRIPTION_SAVED",
        resource    = "visit",
        resource_id = visit_id,
        detail      = f"Allopathy prescription saved — {result.get('medicines_count', 0)} medicines",
    )

    return result


# =====================================================
# SAVE HOMEOPATHY CASE — Step 2 (Homeopathy clinics)
# =====================================================

@router.post("/{visit_id}/homeopathy")
def save_homeopathy(
    visit_id: str,
    data: HomeopathyInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(doctor_only)
):
    """
    Save homeopathy case — doctor only.
    """
    result = visit_service.save_homeopathy_case(
        db        = db,
        visit_id  = visit_id,
        clinic_id = current_user.clinic_id,
        data      = data
    )

    log_action(
        db          = db,
        user        = current_user,
        action      = "HOMEOPATHY_CASE_SAVED",
        resource    = "visit",
        resource_id = visit_id,
        detail      = f"Homeopathy case saved — remedy: {data.remedy or 'not set'}",
    )

    return result


# =====================================================
# CLOSE VISIT — Step 3 (billing)
# =====================================================

@router.post("/{visit_id}/close")
def close_visit(
    visit_id: str,
    request: Request,
    data: CloseVisitInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Close visit and record payment.
    Receptionist fills fee + payment mode.
    Auto-schedules followup reminders.
    Auto-sends WhatsApp thank-you.
    """
    result = visit_service.close_visit(
        db        = db,
        visit_id  = visit_id,
        clinic_id = current_user.clinic_id,
        data      = data
    )

    log_action(
        db          = db,
        user        = current_user,
        action      = "VISIT_CLOSED",
        resource    = "visit",
        resource_id = visit_id,
        detail      = f"Visit closed — fee ₹{data.fee} via {data.payment_mode}",
        meta        = {"fee": float(data.fee), "payment_mode": data.payment_mode},
        ip_address  = request.client.host if request else None,
    )

    return result


# =====================================================
# UPDATE VISIT STATUS
# =====================================================

@router.patch("/{visit_id}/status")
def update_status(
    visit_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    return visit_service.update_visit_status(
        db         = db,
        visit_id   = visit_id,
        clinic_id  = current_user.clinic_id,
        new_status = status
    )


# =====================================================
# LIST VISITS FOR PATIENT
# =====================================================

@router.get("/patient/{patient_id}")
def list_patient_visits(
    patient_id: str,
    skip:  int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    All visits for a patient — newest first.
    Used in patient history timeline.
    """
    from app.models.visit import Visit

    visits = db.query(Visit).filter(
        Visit.patient_id == patient_id,
        Visit.clinic_id  == current_user.clinic_id
    ).order_by(
        Visit.visit_date.desc()
    ).offset(skip).limit(limit).all()

    return {
        "total": len(visits),
        "visits": [
            {
                "id":             v.id,
                "type":           v.type.value if v.type else None,
                "visit_status":   v.visit_status,
                "chief_complaint": v.chief_complaint,
                "fee":            float(v.fee or 0),
                "payment_status": v.payment_status.value if v.payment_status else None,
                "visit_date":     v.visit_date.strftime("%d-%m-%Y %H:%M") if v.visit_date else None,
                "closed_at":      v.closed_at.strftime("%d-%m-%Y %H:%M") if v.closed_at else None,
            }
            for v in visits
        ]
    }


# =====================================================
# TODAY'S VISITS FOR CLINIC
# =====================================================

@router.get("/today/all")
def todays_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    All visits opened today for this clinic.
    Used on dashboard summary.
    """
    from app.models.visit import Visit
    from datetime import datetime
    import pytz

    IST   = pytz.timezone("Asia/Kolkata")
    today = datetime.now(IST).date()

    visits = db.query(Visit).filter(
        Visit.clinic_id == current_user.clinic_id,
        Visit.visit_date >= datetime.combine(today, datetime.min.time())
    ).order_by(Visit.visit_date.desc()).all()

    total_revenue = sum(
        float(v.fee or 0)
        for v in visits
        if v.payment_status and v.payment_status.value == "PAID"
    )

    return {
        "date":          str(today),
        "total_visits":  len(visits),
        "total_revenue": total_revenue,
        "visits": [
            {
                "id":           v.id,
                "patient_id":   v.patient_id,
                "type":         v.type.value if v.type else None,
                "visit_status": v.visit_status,
                "fee":          float(v.fee or 0),
                "visit_time":   v.visit_date.strftime("%H:%M") if v.visit_date else None,
            }
            for v in visits
        ]
    }


# =====================================================
# PDF PRESCRIPTION
# =====================================================

@router.get("/{visit_id}/pdf")
def get_prescription_pdf(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Generate and return branded PDF prescription.
    """
    from fastapi.responses import Response
    from app.models.visit import Visit
    from app.models.patient import Patient
    from app.models.clinic import Clinic

    visit = db.query(Visit).filter(
        Visit.id        == visit_id,
        Visit.clinic_id == current_user.clinic_id
    ).first()

    if not visit:
        raise HTTPException(404, "Visit not found")

    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    clinic  = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()

    try:
        from app.services.pdf_service import generate_prescription_pdf
        pdf_bytes = generate_prescription_pdf(
            visit   = visit.__dict__,
            clinic  = clinic.__dict__ if clinic else {},
            doctor  = current_user.__dict__,
            patient = patient.__dict__ if patient else {}
        )
        return Response(
            content    = pdf_bytes,
            media_type = "application/pdf",
            headers    = {
                "Content-Disposition":
                    f"inline; filename=rx_{visit_id[:8]}.pdf"
            }
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(500, f"PDF generation failed: {str(e)}")


# =====================================================
# SEND PRESCRIPTION VIA WHATSAPP
# =====================================================

@router.post("/{visit_id}/send-whatsapp")
async def send_prescription_whatsapp(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Send prescription PDF link to patient via WhatsApp.
    """
    import os
    from app.models.visit import Visit
    from app.models.patient import Patient
    from app.services.whatsapp_service import send_text_message

    visit = db.query(Visit).filter(
        Visit.id        == visit_id,
        Visit.clinic_id == current_user.clinic_id
    ).first()

    if not visit:
        raise HTTPException(404, "Visit not found")

    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()

    if not patient or not patient.phone_mobile:
        raise HTTPException(400, "Patient has no phone number")

    if getattr(patient, "whatsapp_opted_out", False):
        raise HTTPException(400, "Patient has opted out of WhatsApp")

    base_url = os.getenv(
        "APP_BASE_URL",
        "https://natural-success-production.up.railway.app"
    )
    pdf_url = f"{base_url}/visits/{visit_id}/pdf"

    message = (
        f"Dear {patient.first_name}, your prescription "
        f"from today's consultation is ready.\n\n"
        f"View/Download: {pdf_url}\n\n"
        f"Please save this for your records. 🙏"
    )

    result = await send_text_message(patient.phone_mobile, message)

    return {
        "status":  result.get("status"),
        "message": f"Prescription sent to {patient.first_name}",
        "phone":   patient.phone_mobile
    }