from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session
from sqlalchemy import func

from typing import Optional
from datetime import date, datetime

from app.database import get_db
from app.services import billing_service

from app.middleware.auth_middleware import (
    receptionist_or_doctor
)

from app.models.user import User


router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)


# =========================================================
# Get Payment Details
# =========================================================

@router.get("/visit/{visit_id}")
def get_payment(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Get payment details for a visit
    """

    payment = billing_service.get_payment_by_visit(
        db,
        visit_id,
        current_user.clinic_id
    )

    return {
        "id": payment.id,
        "visit_id": payment.visit_id,
        "amount": float(payment.amount),

        "mode": payment.payment_mode or None,

        "transaction_ref": getattr(payment, 'transaction_ref', None),
        "receipt_url": getattr(payment, 'receipt_url', None),

        "created_at": (
            payment.created_at.strftime("%d-%m-%Y %H:%M")
            if payment.created_at
            else None
        )
    }


# =========================================================
# Generate Receipt
# =========================================================

@router.post("/receipt/{visit_id}")
def generate_receipt(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Generate PDF receipt for closed visit.
    Uploads to Supabase Storage.
    Returns permanent public URL.
    """

    return billing_service.generate_receipt(
        db,
        visit_id,
        current_user.clinic_id
    )


# =========================================================
# Open / Download Receipt
# =========================================================

@router.get("/receipt/{visit_id}/download")
def download_receipt(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Redirect user to Supabase public receipt URL.
    Frontend can open/download directly.
    """

    result = billing_service.generate_receipt(
        db,
        visit_id,
        current_user.clinic_id
    )

    pdf_url = result.get("pdf_url")

    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="Receipt URL not found"
        )

    return RedirectResponse(
        url=pdf_url
    )


# =========================================================
# Billing History
# =========================================================

@router.get("/history")
def get_billing_history(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = 50,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    All payments for clinic — billing history page.
    """

    from app.models.billing import Payment
    from app.models.visit import Visit
    from app.models.patient import Patient

    query = db.query(Payment).join(
        Visit,
        Payment.visit_id == Visit.id
    ).filter(
        Visit.clinic_id == current_user.clinic_id
    )

    if from_date:
        query = query.filter(
            func.date(Payment.created_at) >= from_date
        )

    if to_date:
        query = query.filter(
            func.date(Payment.created_at) <= to_date
        )

    total = query.count()

    offset = (page - 1) * limit

    payments = query.order_by(
        Payment.created_at.desc()
    ).offset(offset).limit(limit).all()

    result = []

    for p in payments:

        visit = db.query(Visit).filter(
            Visit.id == p.visit_id
        ).first()

        patient = (
            db.query(Patient).filter(
                Patient.id == visit.patient_id
            ).first()
            if visit else None
        )

        result.append({
            "payment_id": p.id,
            "visit_id": p.visit_id,

            "patient_name": (
                f"{patient.first_name} {patient.last_name or ''}".strip()
                if patient else "Unknown"
            ),

            "patient_id": (
                patient.id if patient else None
            ),

            "amount": float(p.amount),

            "mode": (
                p.mode.value
                if p.payment_mode else None
            ),

            "receipt_url": p.receipt_url,

            "date": (
                p.created_at.strftime("%d-%m-%Y")
                if p.created_at else None
            ),

            "visit_type": (
                visit.type.value
                if visit and visit.type
                else None
            ),
        })

    total_amount = db.query(
        func.sum(Payment.amount)
    ).join(
        Visit,
        Payment.visit_id == Visit.id
    ).filter(
        Visit.clinic_id == current_user.clinic_id
    ).scalar()

    return {
        "total_records": total,
        "total_amount": float(total_amount or 0),
        "page": page,
        "payments": result
    }


# =========================================================
# Pending Payments
# =========================================================

@router.get("/pending")
def get_pending_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Visits that are closed but payment is still PENDING.
    Receptionist billing panel uses this.
    """

    from app.models.visit import (
        Visit,
        PaymentStatus,
        VisitStatus
    )

    from app.models.patient import Patient

    visits = db.query(Visit).filter(
        Visit.clinic_id == current_user.clinic_id,
        Visit.payment_status == PaymentStatus.PENDING,
        Visit.visit_status == VisitStatus.COMPLETED
    ).order_by(
        Visit.closed_at.desc()
    ).all()

    result = []

    for v in visits:

        patient = db.query(Patient).filter(
            Patient.id == v.patient_id
        ).first()

        result.append({
            "visit_id": v.id,

            "patient_name": (
                f"{patient.first_name} {patient.last_name or ''}".strip()
                if patient else "Unknown"
            ),

            "patient_id": (
                patient.id if patient else None
            ),

            "patient_phone": (
                patient.phone_mobile
                if patient else None
            ),

            "fee": float(v.fee or 0),

            "visit_date": (
                v.visit_date.strftime("%d-%m-%Y")
                if v.visit_date else None
            ),

            "visit_type": (
                v.type.value
                if v.type else None
            ),

            "days_pending": (
                (
                    datetime.utcnow().date()
                    - v.closed_at.date()
                ).days
                if v.closed_at else 0
            )
        })

    return {
        "total": len(result),

        "total_pending": sum(
            r["fee"] for r in result
        ),

        "pending_visits": result
    }
