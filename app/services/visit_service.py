from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime

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


# =====================================================
# PRIVATE HELPERS
# =====================================================

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
        "chief_complaint": visit.chief_complaint,
        "disease_type": visit.disease_type,
        "fee": float(visit.fee or 0),
        "notes": visit.notes,
        "episode_id": visit.episode_id,

        "payment_status": (
            visit.payment_status.value
            if visit.payment_status
            else None
        ),

        "payment_mode": (
            visit.payment_mode.value
            if visit.payment_mode
            else None
        ),

        "visit_date": visit.visit_date,
        "created_at": visit.created_at,
        "closed_at": visit.closed_at
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

                "chief_complaint": (
                    homeopathy_case.chief_complaint
                ),

                "history_present": (
                    homeopathy_case.history_present
                ),

                "history_past": (
                    homeopathy_case.history_past
                ),

                "history_surgical": (
                    homeopathy_case.history_surgical
                ),

                "history_family": (
                    homeopathy_case.history_family
                ),

                "thermal_sensation": (
                    homeopathy_case.thermal_sensation
                ),

                "appetite": (
                    homeopathy_case.appetite
                ),

                "thirst": (
                    homeopathy_case.thirst
                ),

                "sleep": (
                    homeopathy_case.sleep
                ),

                "dreams": (
                    homeopathy_case.dreams
                ),

                "menstrual": (
                    homeopathy_case.menstrual
                ),

                "mind_symptoms": (
                    homeopathy_case.mind_symptoms
                ),

                "particulars": (
                    homeopathy_case.particulars
                ),

                "rubrics": (
                    homeopathy_case.rubrics
                ),

                "remedy": (
                    homeopathy_case.remedy
                ),

                "potency": (
                    homeopathy_case.potency
                ),

                "repetition": (
                    homeopathy_case.repetition
                ),

                "miasm": (
                    homeopathy_case.miasm
                )
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

                "mode": payment.mode
            }

            if payment else None
        )
    }


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

    visit.payment_status = (
        PaymentStatus.PAID
    )

    visit.visit_status = (
        VisitStatus.COMPLETED
    )

    visit.closed_at = (
        datetime.utcnow()
    )

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

            mode=(
                data.payment_mode.value
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

        payment.mode = (
            data.payment_mode.value
            if data.payment_mode
            else "CASH"
        )

    # =====================================================
    # SAVE
    # =====================================================

    db.commit()

    db.refresh(visit)

    return {

        "success": True,

        "message": (
            "Visit closed successfully"
        ),

        "visit_id": visit.id
    }