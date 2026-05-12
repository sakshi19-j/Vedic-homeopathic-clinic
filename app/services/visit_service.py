import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.visit import (
    Visit, VisitType, PaymentStatus, PaymentMode,
    AllopathyRx, HomeopathyCase, Vitals
)
from app.models.billing import Payment
from app.schemas.visit import (
    VisitCreate, VitalsInput, AllopathyInput,
    HomeopathyInput, CloseVisitInput
)
from app.services.growth_service import (
    schedule_followups, update_patient_stats
)
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


# =====================================================
# DYNAMIC CONSULTATION SCHEMA
# =====================================================

CLINIC_FIELDS = {
    "HOMEOPATHY": [
        "chief_complaint", "miasm", "constitution",
        "mental_generals", "physical_generals",
        "modalities", "remedy", "potency", "dose"
    ],
    "ALLOPATHY": [
        "chief_complaint", "history", "examination",
        "diagnosis", "icd_code", "rx", "advice", "follow_up_days"
    ],
    "AYURVEDIC": [
        "chief_complaint", "prakriti", "dosha",
        "nadi", "remedy", "anupaan", "pathya_apathya"
    ],
}

# Safe type map — built dynamically from actual enum values
# so adding a new VisitType never needs a change here
VISIT_TYPE_MAP = {
    v.value: v for v in VisitType
}


# =====================================================
# GET CONSULTATION SCHEMA
# =====================================================

def get_consultation_schema(clinic_type: str) -> list:
    return CLINIC_FIELDS.get(
        clinic_type.upper(),
        CLINIC_FIELDS["ALLOPATHY"]
    )


# =====================================================
# CREATE VISIT
# =====================================================

def create_visit(
    db: Session,
    data: VisitCreate,
    clinic_id: str,
    doctor_id: str
) -> Visit:

    visit_type = VISIT_TYPE_MAP.get(
        (data.type or "HOMEOPATHY").upper(),
        VisitType.HOMEOPATHY
    )

    visit = Visit(
        clinic_id       = clinic_id,
        patient_id      = data.patient_id,
        doctor_id       = doctor_id,
        type            = visit_type,
        visit_status    = "DRAFT",
        chief_complaint = data.chief_complaint,
        disease_type    = data.disease_type or "default",
        fee             = data.fee or 0,
        notes           = data.notes,
        episode_id      = data.episode_id,
        visit_date      = datetime.now(IST)
    )

    db.add(visit)
    db.commit()
    db.refresh(visit)

    logger.info(
        f"Visit created: {visit.id} | "
        f"Clinic: {clinic_id} | Type: {visit_type.value}"
    )

    return visit


# =====================================================
# SAVE VITALS
# =====================================================

def save_vitals(
    db: Session,
    visit_id: str,
    clinic_id: str,
    data: VitalsInput
) -> dict:

    visit = _get_visit(db, visit_id, clinic_id)

    vitals = visit.vitals

    if not vitals:
        vitals = Vitals(visit_id=visit_id)
        db.add(vitals)

    vitals.weight_kg    = data.weight_kg
    vitals.height_cm    = data.height_cm
    vitals.bp_systolic  = data.bp_systolic
    vitals.bp_diastolic = data.bp_diastolic
    vitals.temperature  = data.temperature
    vitals.pulse_rate   = data.pulse_rate

    db.commit()

    bp = ""
    if data.bp_systolic and data.bp_diastolic:
        bp = f"{data.bp_systolic}/{data.bp_diastolic}"

    return {
        "message":     "Vitals saved",
        "weight_kg":   data.weight_kg,
        "height_cm":   data.height_cm,
        "bp":          bp,
        "temperature": data.temperature,
        "pulse_rate":  data.pulse_rate
    }


# =====================================================
# SAVE ALLOPATHY RX
# =====================================================

def save_allopathy_rx(
    db: Session,
    visit_id: str,
    clinic_id: str,
    data: AllopathyInput
) -> dict:

    visit = _get_visit(db, visit_id, clinic_id)

    rx = visit.allopathy_rx

    if not rx:
        rx = AllopathyRx(visit_id=visit_id)
        db.add(rx)

    rx.medicines       = json.dumps([m.model_dump() for m in data.medicines])
    rx.advice          = data.advice
    rx.next_visit_date = data.next_visit_date

    db.commit()

    return {
        "message":         "Prescription saved",
        "medicines_count": len(data.medicines),
        "advice":          data.advice,
        "next_visit_date": str(data.next_visit_date or "")
    }


# =====================================================
# SAVE HOMEOPATHY CASE
# =====================================================

def save_homeopathy_case(
    db: Session,
    visit_id: str,
    clinic_id: str,
    data: HomeopathyInput
) -> dict:

    visit = _get_visit(db, visit_id, clinic_id)

    case = visit.homeopathy_case

    if not case:
        case = HomeopathyCase(visit_id=visit_id)
        db.add(case)

    case.chief_complaint   = data.chief_complaint
    case.history_present   = data.history_present
    case.history_past      = data.history_past
    case.history_surgical  = data.history_surgical
    case.history_family    = data.history_family
    case.thermal_sensation = data.thermal_sensation
    case.appetite          = data.appetite
    case.thirst            = data.thirst
    case.sleep             = data.sleep
    case.dreams            = data.dreams
    case.menstrual         = data.menstrual
    case.mind_symptoms     = data.mind_symptoms
    case.particulars       = json.dumps(data.particulars or {})
    case.rubrics           = json.dumps(
        [r.model_dump() for r in data.rubrics] if data.rubrics else []
    )
    case.remedy     = data.remedy
    case.potency    = data.potency
    case.repetition = data.repetition
    case.miasm      = data.miasm

    db.commit()

    return {
        "message":       "Homeopathy case saved",
        "remedy":        data.remedy,
        "potency":       data.potency,
        "rubrics_count": len(data.rubrics) if data.rubrics else 0
    }


# =====================================================
# CLOSE VISIT
# =====================================================

def close_visit(
    db: Session,
    visit_id: str,
    clinic_id: str,
    data: CloseVisitInput
) -> dict:

    visit = _get_visit(db, visit_id, clinic_id)

    if visit.closed_at or visit.visit_status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visit is already closed"
        )

    try:
        pay_mode = PaymentMode[data.payment_mode.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid payment mode: {data.payment_mode}. "
                f"Valid: CASH, CARD, UPI, ONLINE"
            )
        )

    existing_payment = db.query(Payment).filter(
        Payment.visit_id == visit_id
    ).first()

    if not existing_payment:
        payment = Payment(
            visit_id = visit_id,
            amount   = data.fee,
            mode     = pay_mode
        )
        db.add(payment)
    else:
        existing_payment.amount = data.fee
        existing_payment.mode   = pay_mode

    visit.fee            = data.fee
    visit.disease_type   = data.disease_type or visit.disease_type or "default"
    visit.payment_status = PaymentStatus.PAID
    visit.payment_mode   = pay_mode
    visit.closed_at      = datetime.now(IST)
    visit.visit_status   = "COMPLETED"

    db.commit()
    db.refresh(visit)

    update_patient_stats(db, visit.patient_id, float(data.fee))

    followups = schedule_followups(
        db           = db,
        visit_id     = visit_id,
        patient_id   = visit.patient_id,
        clinic_id    = clinic_id,
        disease_type = visit.disease_type,
        channel      = data.followup_channel or "WHATSAPP"
    )

    _send_thankyou_async(visit, clinic_id, db)

    logger.info(
        f"Visit closed: {visit_id} | "
        f"Fee: {data.fee} | Followups: {len(followups)}"
    )

    return {
        "status":              "closed",
        "visit_id":            visit_id,
        "amount_paid":         float(data.fee),
        "payment_mode":        data.payment_mode.upper(),
        "followups_scheduled": followups,
        "followups_count":     len(followups),
        "message": (
            f"Visit closed. "
            f"{len(followups)} follow-up reminders scheduled."
        )
    }


# =====================================================
# UPDATE VISIT STATUS
# =====================================================

def update_visit_status(
    db: Session,
    visit_id: str,
    clinic_id: str,
    new_status: str
) -> dict:

    VALID_STATUSES = {"DRAFT", "IN_PROGRESS", "COMPLETED", "CANCELLED"}

    if new_status.upper() not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Valid: {VALID_STATUSES}"
        )

    visit = _get_visit(db, visit_id, clinic_id)
    visit.visit_status = new_status.upper()
    db.commit()

    return {
        "visit_id": visit_id,
        "status":   new_status.upper(),
        "message":  f"Visit moved to {new_status.upper()}"
    }


# =====================================================
# GET VISIT WIZARD STATE
# =====================================================

def get_visit_wizard_state(
    db: Session,
    visit_id: str,
    clinic_id: str
) -> dict:

    visit = _get_visit(db, visit_id, clinic_id)

    steps = {
        "step_1_vitals":       visit.vitals is not None,
        "step_2_consultation": (
            visit.homeopathy_case is not None
            or visit.allopathy_rx is not None
        ),
        "step_3_billing":      visit.payment_status == PaymentStatus.PAID,
        "step_4_complete":     visit.closed_at is not None
    }

    if not steps["step_1_vitals"]:
        current_step = 1
    elif not steps["step_2_consultation"]:
        current_step = 2
    elif not steps["step_3_billing"]:
        current_step = 3
    else:
        current_step = 4

    return {
        "visit_id":     visit_id,
        "visit_type":   visit.type.value if visit.type else None,
        "visit_status": visit.visit_status,
        "current_step": current_step,
        "steps":        steps,
        "patient_id":   visit.patient_id
    }


# =====================================================
# GET VISIT
# =====================================================

def get_visit(
    db: Session,
    visit_id: str,
    clinic_id: str
) -> dict:

    visit = _get_visit(db, visit_id, clinic_id)

    return {
        "id":             visit.id,
        "patient_id":     visit.patient_id,
        "type":           visit.type.value if visit.type else None,
        "visit_status":   visit.visit_status,
        "chief_complaint": visit.chief_complaint,
        "disease_type":   visit.disease_type,
        "fee":            float(visit.fee or 0),
        "payment_status": visit.payment_status.value if visit.payment_status else None,
        "payment_mode":   visit.payment_mode.value if visit.payment_mode else None,
        "visit_date":     visit.visit_date.strftime("%d-%m-%Y %H:%M") if visit.visit_date else None,
        "closed_at":      visit.closed_at.strftime("%d-%m-%Y %H:%M") if visit.closed_at else None,
        "notes":          visit.notes
    }


# =====================================================
# PRIVATE HELPERS
# =====================================================

def _get_visit(
    db: Session,
    visit_id: str,
    clinic_id: str
) -> Visit:
    """Always clinic-scoped. Never fetch visit by ID alone."""

    visit = db.query(Visit).filter(
        Visit.id        == visit_id,
        Visit.clinic_id == clinic_id
    ).first()

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )
    return visit


def _send_thankyou_async(visit: Visit, clinic_id: str, db: Session):
    """
    Fire-and-forget WhatsApp thank-you after visit close.
    Errors logged but never raised — visit close must always succeed
    even if WhatsApp is temporarily down.
    """
    try:
        import asyncio
        from app.models.patient import Patient
        from app.models.clinic import Clinic
        from app.services.whatsapp import send_thankyou_message

        patient = db.query(Patient).filter(
            Patient.id == visit.patient_id
        ).first()
        clinic = db.query(Clinic).filter(
            Clinic.id == clinic_id
        ).first()

        if not patient or not patient.phone_mobile:
            return
        if getattr(patient, "whatsapp_opted_out", False):
            return

        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            send_thankyou_message(
                phone        = patient.phone_mobile,
                patient_name = (
                    f"{patient.first_name} "
                    f"{patient.last_name or ''}"
                ).strip(),
                doctor_name  = clinic.doctor_name if clinic else "Doctor",
                clinic_name  = clinic.name if clinic else "Clinic",
                clinic_phone = clinic.phone if clinic else "",
                language     = patient.language_pref or "en"
            )
        )
        loop.close()

    except Exception as e:
        logger.error(
            f"Thank-you WhatsApp failed for visit {visit.id}: {e}"
        )