from sqlalchemy.orm import Session
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.visit import Visit
import os

def get_onboarding_status(db: Session, clinic_id: str) -> dict:
    """
    Returns setup progress for the clinic.
    WHY: Doctors who complete setup use the product daily.
    Incomplete setup = churn within 7 days.
    Gamified progress = activation = retention.
    """
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        return {}
    
    # Auto-detect completed steps
    has_logo = bool(clinic.logo_url)
    has_signature = bool( clinic.signature_url)
    has_whatsapp  = bool(os.getenv("WHATSAPP_ACCESS_TOKEN"))
    
    has_patient = db.query(Patient).filter(
        Patient.clinic_id == clinic_id
    ).first() is not None
    
    has_consultation = db.query(Visit).filter(
        Visit.clinic_id == clinic_id
    ).first() is not None
    
    # Update clinic flags
    clinic.has_logo               = has_logo
    clinic.has_signature          = has_signature
    clinic.has_whatsapp           = has_whatsapp
    clinic.has_first_patient      = has_patient
    clinic.has_first_consultation = has_consultation
    
    steps = [
        {
            "id":          "clinic_profile",
            "title":       "Complete clinic profile",
            "description": "Add your clinic address and timings",
            "completed":   bool(clinic.address and clinic.timings),
            "action":      "/settings",
            "icon":        "building"
        },
        {
            "id":          "upload_logo",
            "title":       "Upload clinic logo",
            "description": "Logo appears on receipts and prescriptions",
            "completed":   has_logo,
            "action":      "/settings",
            "icon":        "image"
        },
        {
            "id":          "upload_signature",
            "title":       "Upload doctor signature",
            "description": "Digital signature for prescriptions",
            "completed":   has_signature,
            "action":      "/settings",
            "icon":        "pen"
        },
        {
            "id":          "add_patient",
            "title":       "Add your first patient",
            "description": "Register a patient to start consultations",
            "completed":   has_patient,
            "action":      "/patients",
            "icon":        "user"
        },
        {
            "id":          "first_consultation",
            "title":       "Complete first consultation",
            "description": "Run through the full clinic workflow",
            "completed":   has_consultation,
            "action":      "/consultation",
            "icon":        "stethoscope"
        },
        {
            "id":          "whatsapp",
            "title":       "Connect WhatsApp",
            "description": "Auto-send reminders to patients",
            "completed":   has_whatsapp,
            "action":      "/settings",
            "icon":        "message"
        }
    ]
    
    completed_count = sum(1 for s in steps if s["completed"])
    total_count     = len(steps)
    progress_pct    = round((completed_count / total_count) * 100)
    
    # Auto-mark complete
    if completed_count == total_count:
        clinic.onboarding_complete = True
    
    db.commit()
    
    return {
        "dismissed":       clinic.onboarding_dismissed,
        "complete":        clinic.onboarding_complete,
        "completed_count": completed_count,
        "total_count":     total_count,
        "progress_pct":    progress_pct,
        "steps":           steps,
        "message":         _get_progress_message(progress_pct)
    }

def dismiss_onboarding(db: Session, clinic_id: str) -> dict:
    """Doctor dismisses the onboarding card"""
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if clinic:
        clinic.onboarding_dismissed = True
        db.commit()
    return {"message": "Onboarding dismissed"}

def _get_progress_message(pct: int) -> str:
    if pct == 100:
        return "🎉 Setup complete! Your clinic is ready."
    elif pct >= 80:
        return "Almost there! Just a couple more steps."
    elif pct >= 50:
        return "Good progress! Keep going."
    elif pct >= 25:
        return "You've started! Complete setup to unlock full power."
    else:
        return "Welcome to Vennova! Let's set up your clinic."