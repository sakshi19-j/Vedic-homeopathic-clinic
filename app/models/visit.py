from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    Enum as SQLEnum,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.models.base import BaseModel

from datetime import datetime

import enum


# =====================================================
# ENUMS
# =====================================================

class VisitType(str, enum.Enum):

    ALLOPATHY = "ALLOPATHY"
    HOMEOPATHY = "HOMEOPATHY"
    AYURVEDIC = "AYURVEDIC"


class VisitStatus(str, enum.Enum):

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    BILLING = "BILLING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):

    PENDING = "PENDING"
    PAID = "PAID"
    WAIVED = "WAIVED"


class PaymentMode(str, enum.Enum):

    CASH = "CASH"
    UPI = "UPI"
    ONLINE = "ONLINE"
    CARD = "CARD"


# =====================================================
# VISIT
# =====================================================

class Visit(BaseModel):

    __tablename__ = "visits"

    clinic_id = Column(
        String,
        nullable=False,
        index=True
    )

    patient_id = Column(
        String,
        ForeignKey("patients.id"),
        nullable=False
    )

    doctor_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    episode_id = Column(
        String,
        nullable=True
    )

    type = Column(
        SQLEnum(VisitType),
        nullable=False
    )

    visit_status = Column(
        SQLEnum(VisitStatus),
        default=VisitStatus.DRAFT,
        nullable=False,
        index=True
    )

    disease_type = Column(
        String,
        nullable=True
    )

    chief_complaint = Column(
        String,
        nullable=True
    )

    diagnosis = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    fee = Column(
        Numeric(10, 2),
        default=0
    )

    payment_status = Column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING
    )

    payment_mode = Column(
        SQLEnum(PaymentMode),
        nullable=True
    )

    visit_date = Column(
        DateTime,
        default=datetime.utcnow
    )

    closed_at = Column(
        DateTime,
        nullable=True
    )

    prescription_url = Column(
        String,
        nullable=True
    )

    followup_date = Column(
        DateTime,
        nullable=True
    )

    followup_status = Column(
        String,
        default="PENDING"
    )

    from sqlalchemy import Boolean

    followup_reminder_sent = Column(
        Boolean,
        default=False
    )
    # =====================================================
    # PRESCRIPTION TOKEN
    # =====================================================

    prescription_token = Column(
        String,
        nullable=True,
        unique=True,
        index=True
    )

    patient = relationship(
        "Patient",
        back_populates="visits"
    )

    doctor = relationship(
        "User",
        back_populates="visits"
    )

    allopathy_rx = relationship(
        "AllopathyRx",
        back_populates="visit",
        uselist=False
    )

    homeopathy_case = relationship(
        "HomeopathyCase",
        back_populates="visit",
        uselist=False
    )

    vitals = relationship(
        "Vitals",
        back_populates="visit",
        uselist=False
    )

    payments = relationship(
        "Payment",
        back_populates="visit",
        cascade="all, delete-orphan"
    )

    follow_ups = relationship(
        "FollowUp",
        back_populates="visit"
    )

    medicines = relationship(
        "Medicine",
        backref="visit",
        cascade="all, delete-orphan"
    )

# =====================================================
# ALLOPATHY RX
# =====================================================

class AllopathyRx(BaseModel):

    __tablename__ = "allopathy_rx"

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        unique=True
    )

    medicines = Column(
        String,
        nullable=True
    )

    advice = Column(
        String,
        nullable=True
    )

    next_visit_date = Column(
        DateTime,
        nullable=True
    )

    visit = relationship(
        "Visit",
        back_populates="allopathy_rx"
    )


# =====================================================
# HOMEOPATHY CASE
# =====================================================

class HomeopathyCase(BaseModel):

    __tablename__ = "homeopathy_cases"

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        unique=True
    )

    chief_complaint = Column(
        String,
        nullable=True
    )

    history_present = Column(
        String,
        nullable=True
    )

    history_past = Column(
        String,
        nullable=True
    )

    history_surgical = Column(
        String,
        nullable=True
    )

    history_family = Column(
        String,
        nullable=True
    )

    thermal_sensation = Column(
        String,
        nullable=True
    )

    appetite = Column(
        String,
        nullable=True
    )

    thirst = Column(
        String,
        nullable=True
    )

    sleep = Column(
        String,
        nullable=True
    )

    dreams = Column(
        String,
        nullable=True
    )

    menstrual = Column(
        String,
        nullable=True
    )

    mind_symptoms = Column(
        String,
        nullable=True
    )

    particulars = Column(
        String,
        nullable=True
    )

    rubrics = Column(
        String,
        nullable=True
    )

    # INTERNAL ONLY
    remedy = Column(
        String,
        nullable=True
    )

    potency = Column(
        String,
        nullable=True
    )

    repetition = Column(
        String,
        nullable=True
    )

    miasm = Column(
        String,
        nullable=True
    )

    # SAFE PATIENT VIEW
    patient_rx = Column(
        String,
        nullable=True
    )

    visit = relationship(
        "Visit",
        back_populates="homeopathy_case"
    )


# =====================================================
# VITALS
# =====================================================

class Vitals(BaseModel):

    __tablename__ = "vitals"

    visit_id = Column(
        String,
        ForeignKey("visits.id"),
        unique=True
    )

    weight_kg = Column(
        Numeric(5, 2),
        nullable=True
    )

    height_cm = Column(
        Numeric(5, 2),
        nullable=True
    )

    bp_systolic = Column(
        Integer,
        nullable=True
    )

    bp_diastolic = Column(
        Integer,
        nullable=True
    )

    temperature = Column(
        Numeric(4, 1),
        nullable=True
    )

    pulse_rate = Column(
        Integer,
        nullable=True
    )

    visit = relationship(
        "Visit",
        back_populates="vitals"
    )