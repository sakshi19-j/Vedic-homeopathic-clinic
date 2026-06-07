from sqlalchemy import (
    Column,
    String,
    DateTime,
    Numeric,
    ForeignKey
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class Payment(BaseModel):

    __tablename__ = "payments"

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        nullable=False,
        index=True
    )

    clinic_id = Column(
        String,
        nullable=False,
        index=True
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0
    )

    # ✅ KEEP payment_mode because DB column already exists
    payment_mode = Column(
        String,
        nullable=True
    )

    reference_no = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    visit = relationship(
        "Visit",
        back_populates="payments"
    )
