from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship

from datetime import datetime

from app.models.base import BaseModel


class Medicine(BaseModel):

    __tablename__ = "medicines"

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        nullable=False,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )

    potency = Column(
        String,
        nullable=True
    )

    timing = Column(
        String,
        nullable=True
    )

    days = Column(
        Integer,
        nullable=True
    )

    food_relation = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )