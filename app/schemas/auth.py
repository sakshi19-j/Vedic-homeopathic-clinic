from pydantic import BaseModel
from typing import Optional


# =====================================================
# SIGNUP
# =====================================================

class SignupRequest(BaseModel):
    """
    Public clinic signup.

    Creates clinic + doctor account in one step.

    Only doctors can signup —
    receptionists are added later by doctor.
    """

    clinic_name: str

    doctor_name: str

    qualification: Optional[str] = "B.H.M.S."

    email: str

    phone: str

    password: str

    city: Optional[str] = None

    timings: Optional[str] = None

    # -------------------------------------------------
    # CLINIC TYPE
    # -------------------------------------------------
    # HOMEOPATHY
    # ALLOPATHY
    # AYURVEDIC
    # MULTI
    # -------------------------------------------------

    clinic_type: Optional[str] = "HOMEOPATHY"


# =====================================================
# LOGIN
# =====================================================

class LoginRequest(BaseModel):
    """
    Login using email.
    """

    # frontend sends this field
    email: str

    password: str


# =====================================================
# CREATE STAFF
# =====================================================

class CreateStaffRequest(BaseModel):
    """
    Doctor creates receptionist/staff account.

    Staff CANNOT self-signup.
    Only doctor can create staff accounts.
    """

    name: str

    phone: Optional[str] = None

    email: Optional[str] = None

    password: str

    role: str = "RECEPTIONIST"


# =====================================================
# LOGIN RESPONSE
# =====================================================

class LoginResponse(BaseModel):
    """
    Returned after successful login/signup.
    Frontend stores this in localStorage.
    """

    access_token: str

    token_type: str = "bearer"

    role: str

    name: str

    clinic_id: str

    clinic_name: Optional[str] = ""

    user_id: str

    plan: Optional[str] = "STARTER"

    branding: Optional[dict] = None


# =====================================================
# USER RESPONSE
# =====================================================

class UserResponse(BaseModel):
    """
    Current logged-in user details.
    """

    id: str

    name: str

    phone: Optional[str] = None

    email: Optional[str] = None

    role: str

    clinic_id: str

    is_active: bool

    class Config:
        from_attributes = True


# =====================================================
# CLINIC SETUP
# =====================================================

class ClinicSetupRequest(BaseModel):
    """
    Update clinic details after signup.

    Doctor fills this from settings page.
    """

    name: Optional[str] = None

    doctor_name: Optional[str] = None

    qualification: Optional[str] = None

    address: Optional[str] = None

    city: Optional[str] = None

    phone: Optional[str] = None

    email: Optional[str] = None

    timings: Optional[str] = None

    primary_color: Optional[str] = None

    secondary_color: Optional[str] = None