from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import base


class Payment(base):

    __tablename__ = "payments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    visit_id = Column(
        UUID(as_uuid=True),
        ForeignKey("visits.id"),
        nullable=False
    )

    clinic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id"),
        nullable=False
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False
    )

    # ✅ IMPORTANT FIX
    payment_mode = Column(
        "mode",
        String,
        nullable=False
    )

    reference_no = Column(
        String,
        nullable=True
    )

    notes = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )