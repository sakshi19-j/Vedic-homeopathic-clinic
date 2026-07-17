from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class VisitCreate(BaseModel):
    patient_id: str
    doctor_id: str
    type: str
    chief_complaint: Optional[str] = None
    notes: Optional[str] = None
    fee: Optional[float] = 0


class VitalsCreate(BaseModel):
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bp_systolic: Optional[int] = None
    bp_diastolic: Optional[int] = None
    temperature: Optional[float] = None
    pulse_rate: Optional[int] = None


class AllopathyPrescriptionCreate(BaseModel):
    medicines: Optional[List[Dict[str, Any]]] = None
    advice: Optional[str] = None
    next_visit_date: Optional[str] = None


class RubricInput(BaseModel):
    text: str
    grade: int
    chapter: Optional[str] = None


class PatientMedicineBox(BaseModel):
    box_name: str
    timing: str
    duration: str
    instruction: Optional[str] = None


class HomeopathyCaseCreate(BaseModel):
    chief_complaint: Optional[str] = None
    patient_rx: Optional[str] = None
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
    rubrics: Optional[List[RubricInput]] = None
    remedy: Optional[str] = None
    potency: Optional[str] = None
    repetition: Optional[str] = None
    miasm: Optional[str] = None


class MedicineBoxInput(BaseModel):
    name: str
    potency: Optional[str] = None
    timing: Optional[str] = None
    days: Optional[str] = None
    food_relation: Optional[str] = None
    notes: Optional[str] = None


class MedicinesCreate(BaseModel):
    medicines: List[MedicineBoxInput]


class CloseVisitRequest(BaseModel):
    fee: Optional[float] = 0   # was: fee: float (required)
    payment_mode: Optional[str] = None
    disease_type: Optional[str] = "default"
    followup_channel: Optional[str] = "WHATSAPP"
    followup_date: Optional[str] = None
    followup_type: Optional[str] = None

class VisitResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    type: str
    chief_complaint: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


VitalsInput = VitalsCreate
AllopathyInput = AllopathyPrescriptionCreate
HomeopathyCaseInput = HomeopathyCaseCreate
HomeopathyInput = HomeopathyCaseCreate
CloseVisitInput = CloseVisitRequest