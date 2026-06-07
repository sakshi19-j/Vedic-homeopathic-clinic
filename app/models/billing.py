from sqlalchemy import (
    Column,
    String,
    Numeric,
    Enum as SQLEnum,
    ForeignKey
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.visit import PaymentMode


class Payment(BaseModel):

    __tablename__ = "payments"

    clinic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id"),
        nullable=False
    )

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        unique=True
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False
    )

    mode = Column(
        SQLEnum(PaymentMode),
        nullable=False
    )

    transaction_ref = Column(
        String,
        nullable=True
    )

    receipt_url = Column(
        String,
        nullable=True
    )

    visit = relationship(
        "Visit",
        back_populates="payment"
    )
