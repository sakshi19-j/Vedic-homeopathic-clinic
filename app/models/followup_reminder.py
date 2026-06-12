from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime
)

from app.models.base import BaseModel


class FollowupReminder(BaseModel):

    __tablename__ = "followup_reminders"

    clinic_id = Column(String)

    patient_id = Column(String)

    visit_id = Column(String)

    followup_date = Column(DateTime)

    reminder_24h_sent = Column(
        Boolean,
        default=False
    )

    reminder_3h_sent = Column(
        Boolean,
        default=False
    )

    missed_followup_sent = Column(
        Boolean,
        default=False
    )

    status = Column(
        String,
        default="PENDING"
    )