import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Numeric,
    ForeignKey
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Payment(Base):

    __tablename__ = "payments"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    # =====================================================
    # RELATIONS
    # =====================================================

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

    # =====================================================
    # PAYMENT DATA
    # =====================================================

    amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0
    )

    payment_mode = Column(
        String,
        nullable=True
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    visit = relationship(
        "Visit",
        back_populates="payments"
    )

    status = Column(
        String,
        default="PENDING"
    )

    receipt_url = Column(
        String,
        nullable=True
    )

    transaction_ref = Column(
        String,
        nullable=True
    )