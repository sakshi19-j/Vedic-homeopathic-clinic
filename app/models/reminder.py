from sqlalchemy import (
    Column, String, DateTime, Boolean,
    Enum as SQLEnum, ForeignKey, Text, Integer
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import enum


class FollowUpType(str, enum.Enum):
    THREE_DAY   = "THREE_DAY"
    SEVEN_DAY   = "SEVEN_DAY"
    FIFTEEN_DAY = "FIFTEEN_DAY"
    MONTHLY     = "MONTHLY"
    CUSTOM      = "CUSTOM"


class FollowUpStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT    = "SENT"
    DONE    = "DONE"
    SKIPPED = "SKIPPED"
    FAILED  = "FAILED"


class Channel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    SMS      = "SMS"
    VOICE    = "VOICE"
    EMAIL    = "EMAIL"


class DeliveryStatus(str, enum.Enum):
    SENT      = "SENT"       # accepted by Meta API
    DELIVERED = "DELIVERED"  # reached patient's phone
    READ      = "READ"       # patient opened it
    FAILED    = "FAILED"     # Meta rejected / undeliverable
    MOCKED    = "MOCKED"     # local dev mock


# =====================================================
# FOLLOW UP
# =====================================================

class FollowUp(BaseModel):
    __tablename__ = "follow_ups"

    visit_id    = Column(String, ForeignKey("visits.id"), nullable=False)
    patient_id  = Column(String, ForeignKey("patients.id"), nullable=False)
    clinic_id   = Column(String, nullable=False, index=True)
    due_date    = Column(DateTime, nullable=False)
    type        = Column(SQLEnum(FollowUpType), nullable=False)
    status      = Column(SQLEnum(FollowUpStatus), default=FollowUpStatus.PENDING)
    channel     = Column(SQLEnum(Channel), default=Channel.WHATSAPP)
    template_id = Column(String, nullable=True)
    sent_at     = Column(DateTime, nullable=True)

    # Separated — message_id for WhatsApp, response for patient text reply
    message_id  = Column(String, nullable=True)   # NEW — WhatsApp message ID
    response    = Column(String, nullable=True)    # patient reply text

    visit   = relationship("Visit", back_populates="follow_ups")
    patient = relationship("Patient", back_populates="follow_ups")


# =====================================================
# WHATSAPP LOG  — every message tracked here
# =====================================================

class WhatsAppLog(BaseModel):
    __tablename__ = "whatsapp_logs"

    clinic_id    = Column(String, nullable=False, index=True)
    patient_id   = Column(String, ForeignKey("patients.id"), nullable=True)

    # Direction
    direction    = Column(String, default="outbound")  # outbound | inbound

    # Message content
    phone        = Column(String, nullable=False)
    message_type = Column(String, default="text")      # text | template
    template_key = Column(String, nullable=True)       # followup_7d | thankyou | birthday
    body         = Column(Text, nullable=True)         # message text sent

    # WhatsApp IDs
    message_id   = Column(String, nullable=True, index=True)  # from Meta response

    # Delivery tracking — updated by webhook events
    delivery_status = Column(
        SQLEnum(DeliveryStatus),
        default=DeliveryStatus.SENT
    )
    delivered_at = Column(DateTime, nullable=True)
    read_at      = Column(DateTime, nullable=True)
    failed_at    = Column(DateTime, nullable=True)
    error_text   = Column(String, nullable=True)

    # Context
    trigger      = Column(String, nullable=True)  # cron | manual | visit_close | birthday

    patient = relationship("Patient")


# =====================================================
# NOTIFICATION TEMPLATE
# =====================================================

class NotificationTemplate(BaseModel):
    __tablename__ = "notification_templates"

    clinic_id    = Column(String, nullable=False)
    template_key = Column(String, nullable=False)
    language     = Column(String, nullable=False)
    channel      = Column(SQLEnum(Channel), nullable=False)
    body         = Column(String, nullable=False)


# =====================================================
# CONSENT
# =====================================================

class Consent(BaseModel):
    __tablename__ = "consents"

    patient_id         = Column(String, ForeignKey("patients.id"), nullable=False)
    consent_text       = Column(String, nullable=False)
    patient_sign_url   = Column(String, nullable=True)
    patient_thumb_url  = Column(String, nullable=True)
    attender_name      = Column(String, nullable=True)
    attender_sign_url  = Column(String, nullable=True)
    attender_thumb_url = Column(String, nullable=True)
    consent_date       = Column(DateTime, nullable=True)

    patient = relationship("Patient", back_populates="consents")