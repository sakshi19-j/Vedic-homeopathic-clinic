from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime

from app.models.visit import (
    Visit,
    VisitStatus,
    PaymentStatus,
    HomeopathyCase,
    Vitals
)

from app.models.billing import Payment

from app.schemas.visit import CloseVisitRequest

from app.models.queue import Queue
from datetime import datetime, timedelta
import json as _json

def _safe_json(value, default=None):
    if not value:
        return default
    try:
        return _json.loads(value)
    except Exception:
        return default if default is not None else value
# =====================================================
# PRIVATE HELPERS
# =====================================================
# =====================================================
# CREATE VISIT
# =====================================================

def create_visit(
    db: Session,
    data,
    clinic_id: str,
    doctor_id: str
):

    visit = Visit(

        patient_id=data.patient_id,

        clinic_id=clinic_id,

        doctor_id=doctor_id,

        appointment_id=getattr(data,"appointment_id",None),

        type=data.type,

        visit_status=VisitStatus.ACTIVE,

        chief_complaint=(
            data.chief_complaint
            if hasattr(data, "chief_complaint")
            else None
        ),

        notes=(
            data.notes
            if hasattr(data, "notes")
            else None
        ),

        fee=(
            data.fee
            if hasattr(data, "fee")
            else 0
        ),

        payment_status=PaymentStatus.PENDING,

        visit_date=datetime.utcnow()
    )

    db.add(visit)

    db.commit()

    db.refresh(visit)

    queue_entry = db.query(Queue).filter(
        Queue.visit_id == visit.id
    ).first()

    if not queue_entry:

        queue_entry = db.query(Queue).filter(
            Queue.patient_id == visit.patient_id,
            Queue.status == "IN_TREATMENT"
        ).first()

    if queue_entry:

        queue_entry.visit_id = visit.id
        queue_entry.status = "BILLING_PENDING"

        try:
            queue_entry.completed_at = datetime.utcnow()
        except:
            pass

        try:
            queue_entry.end_time = datetime.utcnow()
        except:
            pass

    # =====================================================
    # AUTO ADD TO QUEUE
    # =====================================================

    queue_entry = (
        db.query(Queue)
        .filter(
            Queue.patient_id == visit.patient_id,
            Queue.clinic_id == clinic_id,
            Queue.status.in_(["WAITING", "IN_TREATMENT"])
        )
        .order_by(Queue.created_at.desc())
        .first()
    )

    if queue_entry:
        queue_entry.visit_id = visit.id

    db.commit()

    return visit

def _get_visit(
    db: Session,
    visit_id: str,
    clinic_id: str
) -> Visit:

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == clinic_id
    ).first()

    if not visit:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found"
        )

    return visit


# =====================================================
# GET VISIT
# =====================================================

def get_visit(
    db: Session,
    visit_id: str,
    clinic_id: str
):
    from app.models.medicine import Medicine
    from app.models.reminder import FollowUp

    visit = _get_visit(
        db=db,
        visit_id=visit_id,
        clinic_id=clinic_id
    )

    homeopathy_case = db.query(HomeopathyCase).filter(
        HomeopathyCase.visit_id == visit.id
    ).first()

    vitals = db.query(Vitals).filter(
        Vitals.visit_id == visit.id
    ).first()

    medicines = db.query(Medicine).filter(
        Medicine.visit_id == visit.id
    ).all()

    followup = db.query(FollowUp).filter(
        FollowUp.visit_id == visit.id
    ).order_by(FollowUp.created_at.desc()).first()

    return {

        "id": visit.id,
        "patient_id": visit.patient_id,
        "clinic_id": visit.clinic_id,
        "type": visit.type.value if visit.type else None,
        "status": visit.visit_status.value if visit.visit_status else None,
        "chief_complaint": visit.chief_complaint,
        "diagnosis": visit.diagnosis,
        "disease_type": visit.disease_type,
        "fee": float(visit.fee or 0),
        "notes": visit.notes,
        "episode_id": visit.episode_id,
        "payment_status": visit.payment_status.value if visit.payment_status else None,
        "payment_mode": visit.payment_mode if visit.payment_mode else None,
        "visit_date": visit.visit_date,
        "created_at": visit.created_at,
        "closed_at": visit.closed_at,

        "followup_date": (
            visit.followup_date.strftime("%Y-%m-%d")
            if visit.followup_date else None
        ),
        "followup_type": followup.type if followup else None,

        "medicines": [
            {
                "name": m.name,
                "potency": m.potency,
                "timing": m.timing,
                "days": m.days,
                "food_relation": m.food_relation,
                "notes": m.notes,
            }
            for m in medicines
        ],

        "homeopathy_case": (
            {
                "chief_complaint": homeopathy_case.chief_complaint,
                "history_present": homeopathy_case.history_present,
                "history_past": homeopathy_case.history_past,
                "history_surgical": homeopathy_case.history_surgical,
                "history_family": homeopathy_case.history_family,
                "thermal_sensation": homeopathy_case.thermal_sensation,
                "appetite": homeopathy_case.appetite,
                "thirst": homeopathy_case.thirst,
                "sleep": homeopathy_case.sleep,
                "dreams": homeopathy_case.dreams,
                "menstrual": homeopathy_case.menstrual,
                "mind_symptoms": homeopathy_case.mind_symptoms,
                "particulars": _safe_json(homeopathy_case.particulars, default={}),
                "rubrics": _safe_json(homeopathy_case.rubrics, default=[]),
                "remedy": homeopathy_case.remedy,
                "potency": homeopathy_case.potency,
                "repetition": homeopathy_case.repetition,
                "miasm": homeopathy_case.miasm,
                "patient_rx": homeopathy_case.patient_rx,
            }
            if homeopathy_case else None
        ),

        "vitals": (
            {
                "weight_kg": float(vitals.weight_kg) if vitals.weight_kg else None,
                "height_cm": float(vitals.height_cm) if vitals.height_cm else None,
                "bp_systolic": vitals.bp_systolic,
                "bp_diastolic": vitals.bp_diastolic,
                "temperature": float(vitals.temperature) if vitals.temperature else None,
                "pulse_rate": vitals.pulse_rate,
            }
            if vitals else None
        ),
    }

def save_vitals(
    db,
    visit_id,
    clinic_id,
    data
):
    visit = _get_visit(
        db=db,
        visit_id=visit_id,
        clinic_id=clinic_id
    )

    vitals = db.query(Vitals).filter(
        Vitals.visit_id == visit.id
    ).first()

    if not vitals:
        vitals = Vitals(
            visit_id=visit.id
        )
        db.add(vitals)

    vitals.weight_kg = data.weight_kg
    vitals.height_cm = data.height_cm
    vitals.bp_systolic = data.bp_systolic
    vitals.bp_diastolic = data.bp_diastolic
    vitals.temperature = data.temperature
    vitals.pulse_rate = data.pulse_rate

    db.commit()

    return {
        "message": "Vitals saved",
        "visit_id": visit.id
    }
# =====================================================
# VISIT WIZARD STATE
# =====================================================

def get_visit_wizard_state(
    db: Session,
    visit_id: str,
    clinic_id: str
):

    visit = _get_visit(
        db=db,
        visit_id=visit_id,
        clinic_id=clinic_id
    )

    homeopathy_case = db.query(
        HomeopathyCase
    ).filter(
        HomeopathyCase.visit_id == visit.id
    ).first()

    vitals = db.query(
        Vitals
    ).filter(
        Vitals.visit_id == visit.id
    ).first()

    payment = db.query(
        Payment
    ).filter(
        Payment.visit_id == visit.id
    ).first()

    return {

        "visit": {

            "id": visit.id,

            "type": (
                visit.type.value
                if visit.type else None
            ),

            "status": (
                visit.visit_status.value
                if visit.visit_status
                else None
            ),

            "chief_complaint": (
                visit.chief_complaint
            ),

            "notes": visit.notes,

            "fee": float(
                visit.fee or 0
            )
        },

        "homeopathy_case": (

            {
                "id": homeopathy_case.id,
                "chief_complaint": homeopathy_case.chief_complaint,
                "history_present": homeopathy_case.history_present,
                "history_past": homeopathy_case.history_past,
                "history_surgical": homeopathy_case.history_surgical,
                "history_family": homeopathy_case.history_family,
                "thermal_sensation": homeopathy_case.thermal_sensation,
                "appetite": homeopathy_case.appetite,
                "thirst": homeopathy_case.thirst,
                "sleep": homeopathy_case.sleep,
                "dreams": homeopathy_case.dreams,
                "menstrual": homeopathy_case.menstrual,
                "mind_symptoms": homeopathy_case.mind_symptoms,
                "particulars": homeopathy_case.particulars,
                "rubrics": homeopathy_case.rubrics,
                "remedy": homeopathy_case.remedy,
                "potency": homeopathy_case.potency,
                "repetition": homeopathy_case.repetition,
                "miasm": homeopathy_case.miasm
            }

            if homeopathy_case else None
        ),

        "vitals": (

            {
                "weight_kg": (
                    float(vitals.weight_kg)
                    if vitals.weight_kg
                    else None
                ),

                "height_cm": (
                    float(vitals.height_cm)
                    if vitals.height_cm
                    else None
                ),

                "bp_systolic": (
                    vitals.bp_systolic
                ),

                "bp_diastolic": (
                    vitals.bp_diastolic
                ),

                "temperature": (
                    float(vitals.temperature)
                    if vitals.temperature
                    else None
                ),

                "pulse_rate": (
                    vitals.pulse_rate
                )
            }

            if vitals else None
        ),

        "payment": (

            {
                "id": payment.id,

                "amount": float(
                    payment.amount or 0
                ),

                "payment_mode": (
                    payment.payment_mode
                )
            }

            if payment else None
        )
    }


# =====================================================
# CLOSE VISIT
# =====================================================

# =====================================================
# CLOSE VISIT
# =====================================================

def close_visit(
    db: Session,
    clinic_id: str,
    visit_id: str,
    data: CloseVisitRequest
):

    visit = _get_visit(
        db=db,
        visit_id=visit_id,
        clinic_id=clinic_id
    )

    # =====================================================
    # PREVENT DUPLICATE CLOSE
    # =====================================================

    if visit.visit_status in (VisitStatus.BILLING, VisitStatus.COMPLETED):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visit already closed"
        )

    # =====================================================
    # UPDATE VISIT
    # =====================================================

    visit.fee = data.fee

    visit.payment_mode = None

    # =====================================================
    # FINAL VISIT LIFECYCLE UPDATE
    # =====================================================

    from app.models.queue import Queue

    from app.models.reminder import (
        FollowUp,
        FollowUpStatus
    )

    from app.models.queue import Queue

    queue_entry = db.query(Queue).filter(
        Queue.visit_id == visit.id
    ).first()

    # keep pending until billing

    visit.visit_status = VisitStatus.BILLING
    visit.payment_status = PaymentStatus.PENDING
    visit.fee = float(data.fee or 0)
    visit.closed_at = datetime.utcnow()

    # =====================================================
    # FIND EXISTING PAYMENT
    # =====================================================

    payment = db.query(
        Payment
    ).filter(
        Payment.visit_id == visit.id
    ).first()

    # =====================================================
    # CREATE PAYMENT
    # =====================================================

    if not payment:

        payment = Payment(
            visit_id=visit.id,
            clinic_id=visit.clinic_id,
            amount=float(data.fee),
            payment_mode=None,
            status=PaymentStatus.PENDING
        )

        db.add(payment)

    # =====================================================
    # UPDATE PAYMENT
    # =====================================================

    else:

        payment.clinic_id = visit.clinic_id

        payment.amount = data.fee

        payment.payment_mode = None

        payment.status = "PENDING"
        db.add(payment)
    # =====================================================
    # UPDATE QUEUE STATUS
    # =====================================================

    queue_entry = db.query(Queue).filter(
        Queue.visit_id == visit.id
    ).first()

    if queue_entry:

        queue_entry.status = "BILLING_PENDING"
        db.add(queue_entry)

        # optional if fields exist
        try:
            queue_entry.completed_at = datetime.utcnow()
        except:
            pass

        try:
            queue_entry.end_time = datetime.utcnow()
        except:
            pass

    # Sync original appointment status to COMPLETED
    if queue_entry and getattr(queue_entry, "appointment_id", None):
        from app.models.appointment import Appointment
        appt = db.query(Appointment).filter(
            Appointment.id == queue_entry.appointment_id
        ).first()
        if appt:
            appt.status = "COMPLETED"
            db.add(appt)
    # =====================================================
    # CREATE FOLLOWUPS FROM DOCTOR INPUT
    # =====================================================

    # =====================================================
# CREATE FOLLOWUPS FROM DOCTOR INPUT
# =====================================================

    mapping = {
        "THREE_DAY": 3,
        "SEVEN_DAY": 7,
        "FIFTEEN_DAY": 15,
        "THIRTY_DAY": 30,

        "3_DAY": 3,
        "7_DAY": 7,
        "15_DAY": 15,
        "30_DAY": 30,
    }

    followup_date = None

    if data.followup_type == "CUSTOM":

        followup_date = data.followup_date

    else:

        days = mapping.get(data.followup_type)

        if days:
            followup_date = datetime.utcnow() + timedelta(days=days)

        if followup_date:

            visit.followup_date = followup_date
            visit.followup_status = "PENDING"
            visit.followup_reminder_sent = False

            db.query(FollowUp).filter(
                FollowUp.visit_id == visit.id,
                FollowUp.status == FollowUpStatus.PENDING
            ).delete()

            from app.services.reminder_service import (
                schedule_followups_after_visit
            )

            schedule_followups_after_visit(
                db=db,
                visit_id=visit.id,
                patient_id=visit.patient_id,
                clinic_id=visit.clinic_id,
                followup_date=followup_date,
                followup_type=data.followup_type
            )
# =====================================================
# UPDATE PATIENT VISIT STATS
# =====================================================
    from app.models.patient import Patient
    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    if patient:
        patient.total_visits = (patient.total_visits or 0) + 1
        patient.last_visit_date = datetime.utcnow()
        db.add(patient)

        # =====================================================
        # SAVE EVERYTHING
        # =====================================================

    db.commit()
    payment_check = db.query(Payment).filter(
    Payment.visit_id == visit.id
    ).first()

    if payment_check is None:
        raise Exception(
            f"Payment row was not created for visit {visit.id}"
        )
    db.refresh(visit)

    # =====================================================
    # AUTO GENERATE PRESCRIPTION
    # =====================================================

    try:

        from app.services.prescription_service import (
            generate_prescription
        )
        import asyncio

        # PDF only — prescription is already sent via the
        # dedicated /prescriptions/send/{visit_id} call from
        # the doctor's prescription screen. Don't double-send.
        asyncio.run(
            generate_prescription(
                db=db,
                visit_id=visit.id,
                clinic_id=visit.clinic_id,
                send_whatsapp=False
            )
        )
        print(
            f"Visit {visit.id} closed successfully."
        )

        print(
            f"Payment Pending created."
        )

        print(
            f"Queue moved to BILLING_PENDING."
        )

    except Exception as e:

        print(
            "Prescription generation failed:",
            str(e)
        )

    db.commit()
    db.refresh(visit)

    print("Visit Status:", visit.visit_status)
    print("Payment Status:", visit.payment_status)
    print("Fee:", visit.fee)
    print("Closed:", visit.closed_at)
    return {
        "success": True,
        "visit_id": visit.id,
        "status": visit.visit_status.value,
        "payment_status": visit.payment_status.value
    }
# =====================================================
# UPDATE VISIT STATUS
# =====================================================

def update_visit_status(
    db: Session,
    clinic_id: str,
    visit_id: str,
    new_status: str
):

    visit = _get_visit(
        db=db,
        visit_id=visit_id,
        clinic_id=clinic_id
    )

    # =====================================================
    # VALIDATE STATUS
    # =====================================================

    try:

        status_enum = VisitStatus[
            new_status.upper()
        ]

    except KeyError:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid visit status"
        )

    # =====================================================
    # UPDATE STATUS
    # =====================================================

    visit.visit_status = status_enum

    # Auto close if completed
    if status_enum == VisitStatus.COMPLETED:

        visit.closed_at = datetime.utcnow()
        db.add(visit)
    db.commit()

    db.refresh(visit)

    return {

        "success": True,

        "visit_id": visit.id,

        "status": visit.visit_status.value,

        "message": "Visit status updated"
    }

import json

from fastapi import HTTPException

from app.models.visit import (
    Visit,
    HomeopathyCase
)


# =====================================================
# SAVE HOMEOPATHY CASE
# =====================================================

def save_homeopathy_case(
    db,
    visit_id,
    clinic_id,
    data
):

    visit = db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.clinic_id == clinic_id
    ).first()

    if not visit:
        raise HTTPException(
            status_code=404,
            detail="Visit not found"
        )

    homeopathy_case = db.query(
        HomeopathyCase
    ).filter(
        HomeopathyCase.visit_id == visit_id
    ).first()

    if not homeopathy_case:

        homeopathy_case = HomeopathyCase(
            visit_id=visit_id
        )

        db.add(homeopathy_case)

    # =================================================
    # BASIC CASE — only overwrite fields that were sent
    # =================================================

    if data.chief_complaint is not None:
        homeopathy_case.chief_complaint = data.chief_complaint
    if data.history_present is not None:
        homeopathy_case.history_present = data.history_present
    if data.history_past is not None:
        homeopathy_case.history_past = data.history_past
    if data.history_surgical is not None:
        homeopathy_case.history_surgical = data.history_surgical
    if data.history_family is not None:
        homeopathy_case.history_family = data.history_family

    # =================================================
    # GENERALS
    # =================================================

    if data.thermal_sensation is not None:
        homeopathy_case.thermal_sensation = data.thermal_sensation
    if data.appetite is not None:
        homeopathy_case.appetite = data.appetite
    if data.thirst is not None:
        homeopathy_case.thirst = data.thirst
    if data.sleep is not None:
        homeopathy_case.sleep = data.sleep
    if data.dreams is not None:
        homeopathy_case.dreams = data.dreams
    if data.menstrual is not None:
        homeopathy_case.menstrual = data.menstrual
    if data.mind_symptoms is not None:
        homeopathy_case.mind_symptoms = data.mind_symptoms

    # =================================================
    # PARTICULARS
    # =================================================

    if data.particulars:
        homeopathy_case.particulars = json.dumps(
            data.particulars
        )

    # =================================================
    # RUBRICS
    # =================================================

    if data.rubrics:

        rubrics_data = []

        for rubric in data.rubrics:

            rubrics_data.append({
                "text": rubric.text,
                "grade": rubric.grade,
                "chapter": rubric.chapter
            })

        homeopathy_case.rubrics = json.dumps(
            rubrics_data
        )

    # =================================================
    # INTERNAL DOCTOR DATA
    # =================================================

    if data.remedy is not None:
        homeopathy_case.remedy = data.remedy
    if data.potency is not None:
        homeopathy_case.potency = data.potency
    if data.repetition is not None:
        homeopathy_case.repetition = data.repetition
    if data.miasm is not None:
        homeopathy_case.miasm = data.miasm

    # =================================================
    # SAFE PATIENT PRESCRIPTION
    # =================================================

    if data.patient_rx is not None:
        homeopathy_case.patient_rx = data.patient_rx

    # =================================================
    # KEEP VISIT SUMMARY IN SYNC
    # =================================================

    if data.chief_complaint is not None:
        visit.chief_complaint = data.chief_complaint

    if hasattr(data, "diagnosis") and data.diagnosis is not None:
        visit.diagnosis = data.diagnosis

    if hasattr(data, "notes") and data.notes is not None:
        visit.notes = data.notes

    db.add(visit)
    db.commit()

    db.refresh(homeopathy_case)
    
    return {
        "message": "Homeopathy case saved",
        "visit_id": visit_id
    }