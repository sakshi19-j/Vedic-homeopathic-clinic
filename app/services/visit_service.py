from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timedelta

from app.models.visit import (
    Visit,
    VisitStatus,
    PaymentStatus,
    PaymentMode,
    HomeopathyCase,
    Vitals
)

from app.models.billing import Payment

from app.schemas.visit import CloseVisitRequest

from app.services.whatsapp_service import (
    send_visit_thank_you
)

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

    # =====================================================
    # AUTO ADD TO QUEUE
    # =====================================================

    from app.models.queue import Queue

    queue_entry = Queue(
        clinic_id=clinic_id,
        patient_id=visit.patient_id,
        visit_id=visit.id,
        status="WAITING"
    )

    db.add(queue_entry)
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

    visit = _get_visit(
        db=db,
        visit_id=visit_id,
        clinic_id=clinic_id
    )

    return {

        "id": visit.id,

        "patient_id": visit.patient_id,

        "clinic_id": visit.clinic_id,

        "type": (
            visit.type.value
            if visit.type else None
        ),

        "status": (
            visit.visit_status.value
            if visit.visit_status else None
        ),

        "chief_complaint": (
            visit.chief_complaint
        ),

        "disease_type": (
            visit.disease_type
        ),

        "fee": float(
            visit.fee or 0
        ),

        "notes": visit.notes,

        "episode_id": (
            visit.episode_id
        ),

        "payment_status": (
            visit.payment_status.value
            if visit.payment_status
            else None
        ),

        "payment_mode": (
            visit.payment_mode
            if visit.payment_mode
            else None
        ),

        "visit_date": (
            visit.visit_date
        ),

        "created_at": (
            visit.created_at
        ),

        "closed_at": (
            visit.closed_at
        )
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

    if visit.visit_status == VisitStatus.COMPLETED:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visit already completed"
        )

    # =====================================================
    # UPDATE VISIT
    # =====================================================

    visit.fee = data.fee

    visit.payment_mode = (
        data.payment_mode
    )

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
    visit.payment_status = PaymentStatus.PENDING

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

            amount=data.fee,

            payment_mode=(

                data.payment_mode

                if data.payment_mode

                else "CASH"
            )
        )

        db.add(payment)

    # =====================================================
    # UPDATE PAYMENT
    # =====================================================

    else:

        payment.clinic_id = (
            visit.clinic_id
        )

        payment.amount = (
            data.fee
        )

        payment.payment_mode = (

            data.payment_mode

            if data.payment_mode

            else "CASH"
        )

    # =====================================================
    # UPDATE QUEUE STATUS
    # =====================================================

    queue_entry = db.query(Queue).filter(
        Queue.visit_id == visit.id
    ).first()

    if queue_entry:

        queue_entry.status = "BILLING_PENDING"

        # optional if fields exist
        try:
            queue_entry.completed_at = datetime.utcnow()
        except:
            pass

        try:
            queue_entry.end_time = datetime.utcnow()
        except:
            pass

    # =====================================================
    # CREATE FOLLOWUP FROM DOCTOR INPUT
    # =====================================================

    existing_followup = db.query(FollowUp).filter(
        FollowUp.visit_id == visit.id
    ).first()

    if not existing_followup and data.followup_date:

        from datetime import datetime

        followup_date = datetime.fromisoformat(
            data.followup_date
        )

        followup = FollowUp(

            clinic_id=visit.clinic_id,

            patient_id=visit.patient_id,

            visit_id=visit.id,

            due_date=followup_date,

            type=(
                data.followup_type
                if data.followup_type
                else "CUSTOM"
            ),

            status=FollowUpStatus.PENDING,
        )

        db.add(followup)

    # =====================================================
    # SAVE EVERYTHING
    # =====================================================

    db.commit()

    db.refresh(visit)

    # =====================================================
    # AUTO GENERATE PRESCRIPTION
    # =====================================================

    try:

        from app.services.prescription_service import (
            generate_prescription
        )

        generate_prescription(
            db=db,
            visit_id=visit.id,
            clinic_id=visit.clinic_id
        )

    except Exception as e:

        print(
            "Prescription generation failed:",
            str(e)
        )

    # =====================================================
    # SEND THANK YOU MESSAGE
    # =====================================================

    try:

        from app.models.patient import Patient

        import asyncio

        patient = db.query(Patient).filter(
            Patient.id == visit.patient_id
        ).first()

        if patient and patient.phone_mobile:

            loop = asyncio.new_event_loop()

            asyncio.set_event_loop(loop)

            loop.run_until_complete(

                send_visit_thank_you(

                    phone=patient.phone_mobile,

                    patient_name=(
                        f"{patient.first_name} "
                        f"{patient.last_name or ''}"
                    ).strip(),

                    clinic_name="Vennova Clinic"
                )
            )

            loop.close()

    except Exception as e:

        print(
            "WhatsApp thankyou failed:",
            str(e)
        )

    return {

        "success": True,

        "message": (
            "Visit closed successfully"
        ),

        "visit_id": visit.id
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
    # BASIC CASE
    # =================================================

    homeopathy_case.chief_complaint = data.chief_complaint
    homeopathy_case.history_present = data.history_present
    homeopathy_case.history_past = data.history_past
    homeopathy_case.history_surgical = data.history_surgical
    homeopathy_case.history_family = data.history_family

    # =================================================
    # GENERALS
    # =================================================

    homeopathy_case.thermal_sensation = data.thermal_sensation
    homeopathy_case.appetite = data.appetite
    homeopathy_case.thirst = data.thirst
    homeopathy_case.sleep = data.sleep
    homeopathy_case.dreams = data.dreams
    homeopathy_case.menstrual = data.menstrual
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

    homeopathy_case.remedy = data.remedy
    homeopathy_case.potency = data.potency
    homeopathy_case.repetition = data.repetition
    homeopathy_case.miasm = data.miasm

    # =================================================
    # SAFE PATIENT PRESCRIPTION
    # =================================================

    homeopathy_case.patient_rx = data.patient_rx

    db.commit()

    db.refresh(homeopathy_case)

    return {
        "message": "Homeopathy case saved",
        "visit_id": visit_id
    }