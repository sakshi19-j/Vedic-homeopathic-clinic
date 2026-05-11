from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import BaseModel
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    clinic_id   = Column(String, nullable=False, index=True)
    user_id     = Column(String, nullable=False, index=True)
    user_name   = Column(String, nullable=True)
    user_role   = Column(String, nullable=True)

    action      = Column(String, nullable=False)
    # Examples: PATIENT_CREATED, VISIT_CLOSED, STAFF_CREATED,
    #           PAYMENT_RECORDED, PRESCRIPTION_GENERATED

    resource    = Column(String, nullable=True)
    # Examples: patient, visit, staff, billing

    resource_id = Column(String, nullable=True)
    # ID of the affected record

    detail      = Column(Text, nullable=True)
    # Human-readable: "Registered patient Ramesh Kumar (REG-0042)"

    meta        = Column(JSONB, nullable=True)
    # Extra data: { "fee": 500, "payment_mode": "cash" }

    ip_address  = Column(String, nullable=True)
    user_agent  = Column(String, nullable=True)