from sqlalchemy import Column, String, DateTime, Integer, Boolean
from app.models.base import BaseModel
from app.enums import AppointmentStatus, VisitType


class Appointment(BaseModel):
    __tablename__ = "appointments"

    clinic_id = Column(String, nullable=False, index=True)
    patient_id = Column(String, nullable=False, index=True)
    doctor_id = Column(String, nullable=False)

    scheduled_at = Column(DateTime, nullable=False, index=True)

    visit_type = Column(String, default=VisitType.HOMEOPATHY)
    status = Column(String, default=AppointmentStatus.SCHEDULED)

    chief_complaint = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    duration_mins = Column(Integer, default=30)

    queue_id = Column(String, nullable=True)  # linked when checked in

    # 🔥 Reminder tracking
    reminder_sent = Column(Boolean, default=False)