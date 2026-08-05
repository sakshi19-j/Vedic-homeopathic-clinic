from pydantic import BaseModel
from typing import Optional
from datetime import date

class PatientCreate(BaseModel):
    """
    Matches Hompath Classic new patient form exactly.
    All fields your dad currently fills on paper.
    """
    # Name
    title:        Optional[str] = None   # Mr. Mrs. Dr.
    first_name:   str
    middle_name:  Optional[str] = None
    last_name:    Optional[str] = None

    # Personal
    dob:            Optional[date] = None
    age:            Optional[int]  = None
    gender:         Optional[str]  = None  # MALE | FEMALE | OTHER
    marital_status: Optional[str]  = None

    # Residential Address
    res_address:  Optional[str] = None
    res_city:     Optional[str] = None
    res_state:    Optional[str] = None
    res_postal:   Optional[str] = None
    res_country:  Optional[str] = "India"

    # Office Address
    off_address:  Optional[str] = None
    off_city:     Optional[str] = None
    off_state:    Optional[str] = None
    off_postal:   Optional[str] = None

    # Contact
    phone_mobile:  Optional[str] = None
    phone_res:     Optional[str] = None
    phone_office:  Optional[str] = None
    fax:           Optional[str] = None
    email:         Optional[str] = None

    # Referral
    referred_by_name:    Optional[str] = None
    referred_by_contact: Optional[str] = None

    # System
    language_pref:  Optional[str] = "en"    # en | hi | mr
    patient_type:   Optional[str] = "HOMEOPATHY"
    anniversary:    Optional[date] = None

class PatientUpdate(BaseModel):
    """All fields optional — only send what changed"""
    title:          Optional[str]  = None
    first_name:     Optional[str]  = None
    middle_name:    Optional[str]  = None
    last_name:      Optional[str]  = None
    dob:            Optional[date] = None
    age:            Optional[int]  = None
    gender:         Optional[str]  = None
    marital_status: Optional[str]  = None
    res_address:    Optional[str]  = None
    res_city:       Optional[str]  = None
    res_state:      Optional[str]  = None
    res_postal:     Optional[str]  = None
    phone_mobile:   Optional[str]  = None
    phone_res:      Optional[str]  = None
    email:          Optional[str]  = None
    referred_by_name:    Optional[str] = None
    referred_by_contact: Optional[str] = None
    language_pref:  Optional[str]  = None
    anniversary:    Optional[date] = None
    expected_followup_days: Optional[int] = None

class PatientResponse(BaseModel):
    """What we send back — full patient profile"""
    id:           str
    reg_no:       int
    title:        Optional[str]
    first_name:   str
    middle_name:  Optional[str]
    last_name:    Optional[str]
    full_name:    Optional[str] = None
    dob:          Optional[date]
    age:          Optional[int]
    gender:       Optional[str]
    marital_status: Optional[str]
    res_address:  Optional[str]
    res_city:     Optional[str]
    res_state:    Optional[str]
    res_postal:   Optional[str]
    res_country:  Optional[str]
    phone_mobile: Optional[str]
    phone_res:    Optional[str]
    email:        Optional[str]
    referred_by_name:    Optional[str]
    referred_by_contact: Optional[str]
    language_pref:  str
    patient_type:   str
    total_visits:   Optional[int]
    total_spent:    Optional[float]
    last_visit_date: Optional[str]
    patient_value_score: Optional[float]
    is_missed:      Optional[bool]
    added_by_staff_name: Optional[str] = None

    class Config:
        from_attributes = True