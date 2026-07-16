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
    CloseVisitInput,
    MedicinesCreate,   # ADD THIS
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

@router.post("/{visit_id}/medicines")
def save_medicines(
    visit_id: str,
    data: MedicinesCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(doctor_only)
):
    from app.models.medicine import Medicine

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == current_user.clinic_id
    ).first()
    if not visit:
        raise HTTPException(404, "Visit not found")

    db.query(Medicine).filter(Medicine.visit_id == visit_id).delete()

    for m in data.medicines:
        db.add(Medicine(
            visit_id=visit_id,
            name=m.name,
            potency=m.potency,
            timing=m.timing,
            days=m.days,
            food_relation=m.food_relation,
            notes=m.notes,
        ))
    db.commit()

    return {"message": "Medicines saved", "count": len(data.medicines)}

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
from app.models.visit import Visit
@router.get("/patient/{patient_id}")
def get_patient_visits(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from app.models.medicine import Medicine
    from app.models.reminder import FollowUp

    visits = db.query(Visit).filter(
        Visit.patient_id == patient_id,
        Visit.clinic_id == current_user.clinic_id
    ).order_by(Visit.created_at.desc()).all()

    result = []
    for v in visits:
        # Get medicines for this visit
        medicines = db.query(Medicine).filter(
            Medicine.visit_id == str(v.id)
        ).all()

        medicine_list = [
            {
                "name": m.name,
                "potency": m.potency,
                "timing": m.timing,
                "days": m.days,
                "food_relation": m.food_relation,
                "notes": m.notes,
            }
            for m in medicines
        ]

        # Get followup date
        followup = db.query(FollowUp).filter(
            FollowUp.visit_id == str(v.id)
        ).order_by(FollowUp.created_at.desc()).first()

        result.append({
            "id": str(v.id),
            "visit_date": v.visit_date.isoformat() if v.visit_date else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "closed_at": v.closed_at.isoformat() if v.closed_at else None,
            "chief_complaint": v.chief_complaint,
            "visit_type": str(v.type.value) if v.type else None,
            "visit_status": str(v.visit_status) if v.visit_status else None,
            "payment_status": str(v.payment_status) if v.payment_status else None,
            "fee": float(v.fee) if v.fee else 0,
            "diagnosis": getattr(v, "diagnosis", None),
            "advice": getattr(v, "advice", None),
            "notes": getattr(v, "notes", None),
            "remedy": getattr(v, "remedy", None),
            "potency": getattr(v, "potency", None),
            "patient_rx": getattr(v, "patient_rx", None),
            "medicines": medicine_list,
            "followup_date": (
                followup.due_date.isoformat()
                if followup and followup.due_date else None
            ),
            "followup_type": (
                str(followup.type)
                if followup and followup.type else None
            ),
        })

    return result


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

# =====================================================
# SEND PRESCRIPTION VIA WHATSAPP
# (FIXED — no longer builds/sends its own duplicate
# message. generate_prescription() already saves the
# PDF correctly AND sends the WhatsApp message. This
# route just triggers it and returns the result.)
# =====================================================

@router.post("/{visit_id}/send-whatsapp")
async def send_prescription_whatsapp(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Generate (or re-generate) the prescription PDF and
    send it to the patient via WhatsApp.
    """

    from app.models.visit import Visit
    from app.models.patient import Patient
    from app.services.prescription_service import generate_prescription

    # =====================================================
    # GET VISIT (just to confirm it exists + check patient phone
    # before doing any PDF work)
    # =====================================================

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == current_user.clinic_id
    ).first()

    if not visit:
        raise HTTPException(404, "Visit not found")

    patient = db.query(Patient).filter(
        Patient.id == visit.patient_id
    ).first()

    if not patient or not patient.phone_mobile:
        raise HTTPException(
            status_code=400,
            detail="Patient has no phone number"
        )

    if getattr(patient, "whatsapp_opted_out", False):
        raise HTTPException(
            status_code=400,
            detail="Patient has opted out of WhatsApp"
        )

    # =====================================================
    # GENERATE + SEND (single source of truth)
    # =====================================================

    result = generate_prescription(
        db=db,
        visit_id=visit_id,
        clinic_id=current_user.clinic_id
    )

    return {
        "status": "sent",
        "message": f"Prescription sent to {patient.first_name}",
        "phone": patient.phone_mobile,
        "pdf_url": result.get("pdf_url"),
        "secure_url": result.get("secure_url")
    }