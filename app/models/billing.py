import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Payment(Base):

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

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    visit = relationship(
        "Visit",
        back_populates="payment"
    )