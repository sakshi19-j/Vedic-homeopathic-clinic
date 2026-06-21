from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.queue import QueueAdd
from app.services import queue_service
from app.middleware.auth_middleware import (
    get_current_user, receptionist_or_doctor, doctor_only
)
from app.models.user import User

router = APIRouter(prefix="/queue", tags=["Queue"])

@router.post("/add")
def add_to_queue(
    data:         QueueAdd,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Receptionist adds patient to today's queue.
    Auto-assigns next token number.
    """
    return queue_service.add_to_queue(
        db, data, current_user.clinic_id
    )

@router.get("/today")
def get_queue(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Full queue for today.
    Both doctor and receptionist see this.
    Receptionist screen polls this every 5 seconds.
    """
    return {
        "queue": queue_service.get_todays_queue(
            db, current_user.clinic_id
        )
    }

@router.get("/current")
def current_patient(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """Who is with doctor right now"""
    return queue_service.get_current_patient(
        db, current_user.clinic_id
    )

@router.post("/next")
def call_next(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Call next patient.
    Doctor or receptionist clicks this.
    Current patient marked complete, next one starts.
    """
    return queue_service.call_next(db, current_user.clinic_id)

@router.post("/{queue_id}/done")
def mark_done(
    queue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    return queue_service.mark_done(
        db,
        queue_id,
        current_user.clinic_id
    )

@router.put("/{queue_id}/no-show")
def no_show(
    queue_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """Mark patient as no-show"""
    return queue_service.mark_no_show(
        db, queue_id, current_user.clinic_id
    )

@router.delete("/{queue_id}")
def remove(
    queue_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """Remove patient from queue"""
    return queue_service.remove_from_queue(
        db, queue_id, current_user.clinic_id
    )

@router.get("/stats/today")
def queue_stats(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """
    Today's stats — total seen, waiting, avg wait time.
    Shows on receptionist dashboard header.
    """
    return queue_service.get_queue_stats(
        db, current_user.clinic_id
    )