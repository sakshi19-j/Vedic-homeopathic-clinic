from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from fastapi import HTTPException
from datetime import datetime

from app.models.queue import (
    Queue,
    QueueStatus,
    VisitTypeQueue
)

from app.models.patient import Patient
from app.schemas.queue import QueueAdd

import pytz


IST = pytz.timezone("Asia/Kolkata")


# =========================================================
# IST Time
# =========================================================
def now_ist():
    return datetime.now(IST)


# =========================================================
# Next Token
# =========================================================
def get_next_token(
    db: Session,
    clinic_id: str
) -> int:

    today = now_ist().date()

    max_token = db.query(
        func.max(Queue.token_number)
    ).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today
        )
    ).scalar()

    return (max_token or 0) + 1


# =========================================================
# Add Patient To Queue
# =========================================================
def add_to_queue(
    db: Session,
    data: QueueAdd,
    clinic_id: str
) -> dict:

    patient = db.query(Patient).filter(
        Patient.id == data.patient_id
    ).first()

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    today = now_ist().date()

    existing = db.query(Queue).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.patient_id == data.patient_id,
            Queue.queue_date == today,
            Queue.status.in_([
                "WAITING",
                "IN_TREATMENT"
            ])
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Patient already in queue. Token: {existing.token_number}"
        )

    token = get_next_token(
        db,
        clinic_id
    )

    entry = Queue(
        clinic_id=clinic_id,
        patient_id=data.patient_id,

        token_number=token,
        queue_date=today,

        visit_type=(
            "WALKIN"
            if data.visit_type == "WALKIN"
            else "APPOINTMENT"
        ),

        priority=data.priority or 0,
        notes=data.notes,

        status="WAITING",

        check_in_time=now_ist()
    )

    db.add(entry)

    db.commit()

    db.refresh(entry)

    return {
        "message": "Added to queue",

        "queue_id": entry.id,

        "token_number": token,

        "patient_name": (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip(),

        "status": str(entry.status),

        "position": _get_position(
            db,
            clinic_id,
            token
        )
    }


# =========================================================
# Today's Queue
# =========================================================
def get_todays_queue(
    db: Session,
    clinic_id: str
) -> list:

    today = now_ist().date()

    entries = db.query(Queue).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today,
            Queue.status.in_([
                "WAITING",
                "IN_TREATMENT"
            ])
         )
    ).order_by(
            Queue.priority.desc(),
            Queue.token_number.asc()
    ).all()

    result = []

    for e in entries:

        patient = db.query(Patient).filter(
            Patient.id == e.patient_id
        ).first()

        wait_mins = None

        if (
            e.check_in_time
            and str(e.status) == "WAITING"
        ):

            diff = (
                now_ist()
                - e.check_in_time.replace(tzinfo=IST)
            )

            wait_mins = int(
                diff.total_seconds() / 60
            )

        result.append({
            "id": e.id,

            "token_number": e.token_number,

            "patient_id": e.patient_id,

            "patient_name": (
                f"{patient.first_name} "
                f"{patient.last_name or ''}"
            ).strip() if patient else "Unknown",

            "patient_phone": (
                patient.phone_mobile
                if patient else None
            ),

            "status": str(e.status),

            "visit_type": (
                str(e.visit_type)
                if e.visit_type else "WALKIN"
            ),

            "priority": e.priority,

            "check_in_time": (
                e.check_in_time.strftime("%H:%M")
                if e.check_in_time else None
            ),

            "called_time": (
                e.called_time.strftime("%H:%M")
                if e.called_time else None
            ),

            "wait_minutes": wait_mins,

            "notes": e.notes
        })

    return result


# =========================================================
# Current Patient
# =========================================================
def get_current_patient(
    db: Session,
    clinic_id: str
) -> dict:

    today = now_ist().date()

    current = db.query(Queue).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today,
            Queue.status.in_(["IN_TREATMENT"])
        )
    ).first()

    if not current:
        return {
            "message": "No patient currently with doctor"
        }

    patient = db.query(Patient).filter(
        Patient.id == current.patient_id
    ).first()

    return {
        "queue_id": current.id,

        "token_number": current.token_number,

        "patient_id": current.patient_id,

        "patient_name": (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip() if patient else "Unknown",

        "patient_phone": (
            patient.phone_mobile
            if patient else None
        ),

        "start_time": (
            current.start_time.strftime("%H:%M")
            if current.start_time else None
        )
    }


# =========================================================
# Call Next Patient
# =========================================================
def call_next(
    db: Session,
    clinic_id: str
) -> dict:

    today = now_ist().date()

    current = db.query(Queue).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today,
            Queue.status == "IN_TREATMENT"
        )
    ).first()

    if current:
        current.status = "WAITING_BILLING"
        current.end_time = now_ist()

        db.commit()

    next_patient = db.query(Queue).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today,
            Queue.status == "WAITING"
        )
    ).order_by(
        Queue.priority.desc(),
        Queue.token_number.asc()
    ).first()

    if not next_patient:
        return {
            "message": "No patients waiting"
        }

    next_patient.status = "IN_TREATMENT"

    next_patient.called_time = now_ist()
    next_patient.start_time = now_ist()

    db.commit()

    patient = db.query(Patient).filter(
        Patient.id == next_patient.patient_id
    ).first()

    return {
        "message": "Next patient called",

        "queue_id": next_patient.id,

        "token_number": next_patient.token_number,

        "patient_id": next_patient.patient_id,

        "patient_name": (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip() if patient else "Unknown"
    }


# =========================================================
# Mark No Show
# =========================================================
def mark_no_show(
    db: Session,
    queue_id: str,
    clinic_id: str
) -> dict:

    entry = _get_entry(
        db,
        queue_id,
        clinic_id
    )

    entry.status = "NO_SHOW"

    db.commit()

    return {
        "message": "Marked as no-show",
        "queue_id": queue_id
    }


# =========================================================
# Remove From Queue
# =========================================================
def remove_from_queue(
    db: Session,
    queue_id: str,
    clinic_id: str
) -> dict:

    entry = _get_entry(
        db,
        queue_id,
        clinic_id
    )

    db.delete(entry)

    db.commit()

    return {
        "message": "Removed from queue"
    }


# =========================================================
# Queue Stats
# =========================================================
def get_queue_stats(
    db: Session,
    clinic_id: str
) -> dict:

    today = now_ist().date()

    entries = db.query(Queue).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today
        )
    ).all()

    waiting = len([
        e for e in entries
        if str(e.status) == "WAITING"
    ])

    in_treatment = len([
        e for e in entries
        if str(e.status) == "IN_TREATMENT"
    ])

    completed = len([
        e for e in entries
        if str(e.status) == "COMPLETED"
    ])

    no_show = len([
        e for e in entries
        if str(e.status) == "NO_SHOW"
    ])

    return {
        "date": str(today),

        "total_today": len(entries),

        "waiting": waiting,

        "in_treatment": in_treatment,

        "completed": completed,

        "no_show": no_show
    }


# =========================================================
# Helpers
# =========================================================
def _get_entry(
    db: Session,
    queue_id: str,
    clinic_id: str
) -> Queue:

    entry = db.query(Queue).filter(
        Queue.id == queue_id,
        Queue.clinic_id == clinic_id
    ).first()

    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found"
        )

    return entry


def _get_position(
    db: Session,
    clinic_id: str,
    token: int
) -> int:

    today = now_ist().date()

    waiting = db.query(
        func.count(Queue.id)
    ).filter(
        and_(
            Queue.clinic_id == clinic_id,
            Queue.queue_date == today,
            Queue.status == "WAITING",
            Queue.token_number <= token
        )
    ).scalar()

    return waiting or 1