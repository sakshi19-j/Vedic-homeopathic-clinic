from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# =====================================================
# VISIT CREATE
# =====================================================

class VisitCreate(BaseModel):

    patient_id: str

    doctor_id: str

    type: str

    chief_complaint: Optional[str] = None

    disease_type: Optional[str] = None

    notes: Optional[str] = None

    fee: Optional[float] = 0


# =====================================================
# ALLPATHY INPUT
# =====================================================

class MedicineItem(BaseModel):

    medicine_name: str

    dosage: Optional[str] = None

    frequency: Optional[str] = None

    duration: Optional[str] = None


class AllopathyInput(BaseModel):

    medicines: Optional[List[MedicineItem]] = None

    advice: Optional[str] = None

    next_visit_date: Optional[str] = None


# =====================================================
# RUBRIC
# =====================================================

class RubricSchema(BaseModel):

    text: str

    grade: int

    chapter: Optional[str] = None


# =====================================================
# HOMEOPATHY CASE
# =====================================================

class HomeopathyCaseCreate(BaseModel):

    chief_complaint: Optional[str] = None

    history_present: Optional[str] = None

    history_past: Optional[str] = None

    history_surgical: Optional[str] = None

    history_family: Optional[str] = None

    thermal_sensation: Optional[str] = None

    appetite: Optional[str] = None

    thirst: Optional[str] = None

    sleep: Optional[str] = None

    dreams: Optional[str] = None

    menstrual: Optional[str] = None

    mind_symptoms: Optional[str] = None

    particulars: Optional[Dict[str, Any]] = None

    rubrics: Optional[List[RubricSchema]] = None

    remedy: Optional[str] = None

    potency: Optional[str] = None

    repetition: Optional[str] = None

    miasm: Optional[str] = None


# =====================================================
# VITALS
# =====================================================

class VitalsCreate(BaseModel):

    weight_kg: Optional[float] = None

    height_cm: Optional[float] = None

    bp_systolic: Optional[int] = None

    bp_diastolic: Optional[int] = None

    temperature: Optional[float] = None

    pulse_rate: Optional[int] = None


# =====================================================
# CLOSE VISIT
# =====================================================

class CloseVisitRequest(BaseModel):

    fee: float

    payment_mode: Optional[str] = "CASH"

    disease_type: Optional[str] = "default"

    followup_channel: Optional[str] = "WHATSAPP"


# =====================================================
# COMPATIBILITY ALIASES
# =====================================================

VitalsInput = VitalsCreate

HomeopathyCaseInput = HomeopathyCaseCreate
