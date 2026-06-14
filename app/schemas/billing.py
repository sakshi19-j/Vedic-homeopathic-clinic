from pydantic import BaseModel
from typing import Optional

class PaymentResponse(BaseModel):
    id:              str
    visit_id:        str
    amount:          float
    mode:            str
    transaction_ref: Optional[str]
    receipt_url:     Optional[str]
    created_at:      Optional[str]

    class Config:
        from_attributes = True

class ReceiptData(BaseModel):
    """All data needed to generate PDF receipt"""
    # Clinic info
    clinic_name:      str
    doctor_name:      str
    qualification:    Optional[str]
    clinic_address:   Optional[str]
    clinic_phone:     Optional[str]
    clinic_timings:   Optional[str]

    # Patient info
    patient_name:     str
    patient_age:      Optional[int]
    patient_gender:   Optional[str]
    patient_phone:    Optional[str]
    reg_no:           int

    # Visit info
    visit_date:       str
    visit_type:       str
    chief_complaint:  Optional[str]

    # Payment
    amount:           float
    payment_mode:     str
    receipt_no:       str

    logo_url: str | None = None
    signature_url: str | None = None
    primary_color: str | None = "#2563eb"
    secondary_color: str | None = "#14b8a6"
    footer_text: str | None = None