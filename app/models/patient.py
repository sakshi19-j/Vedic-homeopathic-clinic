from sqlalchemy import Column, String, Integer, Date, DateTime, Boolean, Numeric, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class MaritalStatus(str, enum.Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    WIDOWED = "WIDOWED"
    DIVORCED = "DIVORCED"


class PatientType(str, enum.Enum):
    ALLOPATHY = "ALLOPATHY"
    HOMEOPATHY = "HOMEOPATHY"
    BOTH = "BOTH"


class Patient(BaseModel):
    __tablename__ = "patients"

    # 🔥 ID comes from BaseModel (UUID string)

    clinic_id = Column(String, nullable=False, index=True)
    reg_no = Column(Integer, nullable=False)

    title = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

    dob = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(SQLEnum(Gender), nullable=True)
    marital_status = Column(SQLEnum(MaritalStatus), nullable=True)

    res_address = Column(String, nullable=True)
    res_city = Column(String, nullable=True)
    res_state = Column(String, nullable=True)
    res_postal = Column(String, nullable=True)
    res_country = Column(String, default="India")

    off_address = Column(String, nullable=True)
    off_city = Column(String, nullable=True)
    off_state = Column(String, nullable=True)
    off_postal = Column(String, nullable=True)
    off_country = Column(String, nullable=True)

    phone_mobile = Column(String, nullable=True, index=True)
    phone_res = Column(String, nullable=True)
    phone_office = Column(String, nullable=True)
    fax = Column(String, nullable=True)
    email = Column(String, nullable=True)

    referred_by_name = Column(String, nullable=True)
    referred_by_contact = Column(String, nullable=True)
    
    anniversary = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)

    # 🔥 Growth Engine Fields
    last_visit_date = Column(DateTime, nullable=True)
    expected_followup_days = Column(Integer, default=7)
    total_visits = Column(Integer, default=0)
    total_spent = Column(Numeric(10, 2), default=0)
    patient_value_score = Column(Numeric(5, 2), default=0)

    is_missed = Column(Boolean, default=False)
    missed_since = Column(DateTime, nullable=True)

    # ── NEW: WhatsApp opt-out ──────────────────────
    whatsapp_opted_out = Column(Boolean, default=False)
    whatsapp_opted_out_at = Column(DateTime, nullable=True)
    # ──────────────────────────────────────────────

    # Relationships
    visits = relationship("Visit", back_populates="patient")
    follow_ups = relationship("FollowUp", back_populates="patient")
    consents = relationship("Consent", back_populates="patient")