from sqlalchemy import (
    Column,
    String,
    Numeric,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Payment(BaseModel):

    __tablename__ = "payments"

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        nullable=False,
        unique=True
    )

    clinic_id = Column(
        String,
        nullable=False,
        index=True
    )

    amount = Column(
        Numeric(10, 2),
        default=0
    )

    payment_mode = Column(
        String,
        nullable=True
    )

    # =====================================================
    # RELATIONSHIP
    # =====================================================

    visit = relationship(
        "Visit",
        back_populates="payments"
    )