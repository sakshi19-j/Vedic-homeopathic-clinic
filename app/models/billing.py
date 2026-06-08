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

    id = Column(
        String,
        primary_key=True
    )

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

    payment_mode = Column(
        String,
        nullable=False
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

    visit = relationship(
        "Visit",
        back_populates="payments"
    )
