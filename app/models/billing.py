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
        index=True
    )

    amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0
    )

    # ONLY keep columns that REALLY exist in DB

    reference_no = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    visit = relationship(
        "Visit",
        back_populates="payment"
    )