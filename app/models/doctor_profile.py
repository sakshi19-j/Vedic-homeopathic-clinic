from sqlalchemy import Column, String

from app.models.base import BaseModel


class DoctorProfile(BaseModel):

    __tablename__ = "doctor_profiles"

    clinic_id = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    doctor_name = Column(
        String,
        nullable=False
    )

    clinic_name = Column(
        String,
        nullable=False
    )

    qualification = Column(
        String,
        nullable=True
    )

    registration_number = Column(
        String,
        nullable=True
    )

    specialty = Column(
        String,
        nullable=True
    )

    whatsapp_number = Column(
        String,
        nullable=True
    )

    clinic_address = Column(
        String,
        nullable=True
    )

    clinic_logo_url = Column(
        String,
        nullable=True
    )

    signature_url = Column(
        String,
        nullable=True
    )