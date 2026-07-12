from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date, timedelta

from app.database import get_db
from app.middleware.auth_middleware import (
    receptionist_or_doctor,
    get_current_user
)

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.user import User

from app.enums import AppointmentStatus, VisitType

import pytz


IST = pytz.timezone("Asia/Kolkata")

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"]
)


# =========================================================
# Schemas
# =========================================================

class AppointmentCreate(BaseModel):
    patient_id:      str
    scheduled_at:    datetime
    visit_type:      Optional[str] = "HOMEOPATHY"
    chief_complaint: Optional[str] = None
    notes:           Optional[str] = None
    duration_mins:   Optional[int] = 30


class AppointmentUpdate(BaseModel):
    scheduled_at:    Optional[datetime] = None
    status:          Optional[str]      = None
    notes:           Optional[str]      = None
    chief_complaint: Optional[str]      = None


# =========================================================
# Helper
# =========================================================

def _format_appointment(a: Appointment, patient: Patient) -> dict:
    return {
        "id":              a.id,
        "patient_id":      a.patient_id,
        "patient_name": (
            f"{patient.first_name} {patient.last_name or ''}".strip()
            if patient else "Unknown"
        ),
        "patient_phone": (
            patient.phone_mobile if patient else None
        ),
        "scheduled_at": (
            a.scheduled_at.isoformat()
            if a.scheduled_at else None
        ),
        "visit_type":      a.visit_type,
        "status":          a.status,
        "chief_complaint": a.chief_complaint,
        "notes":           a.notes,
        "duration_mins":   a.duration_mins
    }


# =========================================================
# Create Appointment
# =========================================================

@router.post("/")
def create_appointment(
    data:         AppointmentCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """Book new appointment"""

    patient = db.query(Patient).filter(
        Patient.id == data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    appt = Appointment(
        clinic_id       = current_user.clinic_id,
        patient_id      = data.patient_id,
        doctor_id       = current_user.id,
        scheduled_at    = data.scheduled_at,
        visit_type      = data.visit_type,
        chief_complaint = data.chief_complaint,
        notes           = data.notes,
        duration_mins   = data.duration_mins
    )

    db.add(appt)
    db.commit()
    db.refresh(appt)

    return {
        "message":        "Appointment booked",
        "appointment_id": appt.id,
        "patient": (
            f"{patient.first_name} {patient.last_name or ''}".strip()
        ),
        "scheduled_at": appt.scheduled_at.strftime("%d-%m-%Y %H:%M")
    }


# =========================================================
# Get Today's Appointments
# =========================================================

@router.get("/today")
def get_todays_appointments(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """All appointments for today"""

    now = datetime.now(IST)

    start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    end = now.replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=999999
    )

    appts = db.query(Appointment).filter(
        and_(
            Appointment.clinic_id == current_user.clinic_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at <= end
        )
    ).order_by(Appointment.scheduled_at).all()

    result = []

    for a in appts:
        patient = db.query(Patient).filter(
            Patient.id == a.patient_id
        ).first()

        result.append(_format_appointment(a, patient))

    return {
        "date": str(now.date()),
        "total": len(result),
        "appointments": result
    }


# =========================================================
# Get All Appointments With Filters
# =========================================================

@router.get("/")
def get_appointments(
    status:       Optional[str]  = None,
    from_date:    Optional[date] = None,
    to_date:      Optional[date] = None,
    patient_id:   Optional[str]  = None,
    limit:        int            = 20,
    page:         int            = 1,
    db:           Session        = Depends(get_db),
    current_user: User           = Depends(receptionist_or_doctor)
):
    """List appointments with filters"""

    query = db.query(Appointment).filter(
        Appointment.clinic_id == current_user.clinic_id
    )

    if status:
        query = query.filter(
            Appointment.status == status
        )

    if patient_id:
        query = query.filter(
            Appointment.patient_id == patient_id
        )

    if from_date:
        query = query.filter(
            func.date(Appointment.scheduled_at) >= from_date
        )

    if to_date:
        query = query.filter(
            func.date(Appointment.scheduled_at) <= to_date
        )

    total = query.count()

    offset = (page - 1) * limit

    appts = query.order_by(
        Appointment.scheduled_at
    ).offset(offset).limit(limit).all()

    result = []

    for a in appts:
        patient = db.query(Patient).filter(
            Patient.id == a.patient_id
        ).first()

        result.append(_format_appointment(a, patient))

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "appointments": result
    }


# =========================================================
# Get Upcoming Appointments
# =========================================================

@router.get("/upcoming")
def get_upcoming_appointments(
    days:         int     = 7,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """Next N days appointments"""

    now = datetime.now(IST)

    end = now + timedelta(days=days)

    appts = db.query(Appointment).filter(
        and_(
            Appointment.clinic_id == current_user.clinic_id,
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= end,
            Appointment.status != "CANCELLED"
        )
    ).order_by(Appointment.scheduled_at).all()

    result = []

    for a in appts:
        patient = db.query(Patient).filter(
            Patient.id == a.patient_id
        ).first()

        result.append(_format_appointment(a, patient))

    return {
        "days": days,
        "total": len(result),
        "appointments": result
    }


# =========================================================
# Update Appointment
# =========================================================

@router.put("/{appointment_id}")
def update_appointment(
    appointment_id: str,
    data:           AppointmentUpdate,
    db:             Session = Depends(get_db),
    current_user:   User    = Depends(receptionist_or_doctor)
):
    """Update appointment"""

    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.clinic_id == current_user.clinic_id
    ).first()

    if not appt:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(appt, key, value)

    db.commit()
    db.refresh(appt)

    return {
        "message": "Appointment updated",
        "id": appointment_id
    }

@router.post("/{appointment_id}/checkin")
def checkin_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.clinic_id == current_user.clinic_id
    ).first()

    if not appt:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    if not appt.patient_id:
        raise HTTPException(
            status_code=400,
            detail="Appointment has no linked patient"
        )

    from app.schemas.queue import QueueAdd
    from app.services.queue_service import add_to_queue

    try:
        result = add_to_queue(
            db=db,
            clinic_id=current_user.clinic_id,
            data=QueueAdd(
                patient_id=str(appt.patient_id),
                visit_type=appt.visit_type or "HOMEOPATHY",
                notes=appt.chief_complaint or None,
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not add to queue: {str(e)}"
        )

    appt.status = "CHECKED_IN"
    db.commit()

    return {
        "message": "Patient checked in and added to queue",
        "appointment_id": appointment_id,
        "patient_id": str(appt.patient_id),
        **(result if isinstance(result, dict) else {})
    }
        
# =========================================================
# Cancel Appointment
# =========================================================

@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: str,
    db:             Session = Depends(get_db),
    current_user:   User    = Depends(receptionist_or_doctor)
):
    """Cancel appointment"""

    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.clinic_id == current_user.clinic_id
    ).first()

    if not appt:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    appt.status = "CANCELLED"

    db.commit()

    return {
        "message": "Appointment cancelled",
        "id": appointment_id
    }