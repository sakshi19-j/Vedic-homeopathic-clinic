from sqlalchemy import Column, String, ForeignKey
from app.models.base import BaseModel


class DoctorProfile(BaseModel):

    __tablename__ = "doctor_profiles"

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    doctor_name = Column(String)
    clinic_name = Column(String)
    degree = Column(String)
    registration_number = Column(String)
    whatsapp_number = Column(String)
    signature_url = Column(String)
    clinic_logo_url = Column(String)
    specialty = Column(String)