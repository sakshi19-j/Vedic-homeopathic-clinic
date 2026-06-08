from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.models.visit import Visit, PaymentStatus
from app.models.patient import Patient
from app.models.reminder import FollowUp, FollowUpStatus


# ─────────────────────────────────────────────
# DAILY REVENUE
# ─────────────────────────────────────────────
def daily_revenue(db: Session, clinic_id: str):

    today = datetime.utcnow().date()

    revenue = db.query(
        func.sum(Visit.fee)
    ).filter(
        Visit.clinic_id == clinic_id,
        Visit.payment_status == PaymentStatus.PAID,
        func.date(Visit.visit_date) == today
    ).scalar()

    return {
        "date": str(today),
        "revenue": float(revenue or 0)
    }


# ─────────────────────────────────────────────
# WEEKLY REVENUE (last 7 days breakdown)
# ─────────────────────────────────────────────
def weekly_revenue(db: Session, clinic_id: str):

    today = datetime.utcnow().date()

    days = []

    for i in range(6, -1, -1):

        day = today - timedelta(days=i)

        revenue = db.query(
            func.sum(Visit.fee)
        ).filter(
            Visit.clinic_id == clinic_id,
            Visit.payment_status == PaymentStatus.PAID,
            func.date(Visit.visit_date) == day
        ).scalar()

        days.append({
            "date": str(day),
            "day": day.strftime("%a"),
            "revenue": float(revenue or 0)
        })

    return {
        "week": days,
        "total": sum(d["revenue"] for d in days)
    }


# ─────────────────────────────────────────────
# MONTHLY REVENUE
# ─────────────────────────────────────────────
def monthly_revenue(db: Session, clinic_id: str):

    now = datetime.utcnow()

    revenue = db.query(
        func.sum(Visit.fee)
    ).filter(
        Visit.clinic_id == clinic_id,
        Visit.payment_status == PaymentStatus.PAID,
        func.extract("month", Visit.visit_date) == now.month,
        func.extract("year", Visit.visit_date) == now.year
    ).scalar()

    return {
        "month": now.strftime("%B"),
        "revenue": float(revenue or 0)
    }


# ─────────────────────────────────────────────
# MISSED PATIENTS
# ─────────────────────────────────────────────
def missed_patients(db: Session, clinic_id: str):

    cutoff = datetime.utcnow() - timedelta(days=30)

    patients = db.query(Patient).filter(
        Patient.clinic_id == clinic_id
    ).all()

    missed = []

    for patient in patients:

        last_visit = db.query(Visit).filter(
            Visit.patient_id == patient.id
        ).order_by(
            Visit.visit_date.desc()
        ).first()

        if last_visit and last_visit.visit_date and last_visit.visit_date.replace(tzinfo=None) < cutoff.replace(tzinfo=None):

            missed.append({
                "patient_id": patient.id,
                "name": (
                    f"{patient.first_name} "
                    f"{patient.last_name or ''}"
                ).strip(),
                "last_visit": str(last_visit.visit_date.date())
            })

    return {
        "count": len(missed),
        "patients": missed
    }


# ─────────────────────────────────────────────
# REVENUE LOST — MISSED PATIENTS ESTIMATE
# ─────────────────────────────────────────────
def revenue_lost_estimate(db: Session, clinic_id: str):

    # Average fee per visit for this clinic
    avg_fee = db.query(
        func.avg(Visit.fee)
    ).filter(
        Visit.clinic_id == clinic_id,
        Visit.payment_status == PaymentStatus.PAID
    ).scalar()

    avg_fee = float(avg_fee or 0)

    missed = missed_patients(db, clinic_id)

    missed_count = missed["count"]

    estimated_loss = round(
        avg_fee * missed_count,
        2
    )

    return {
        "missed_patients": missed_count,
        "avg_fee_per_visit": round(avg_fee, 2),
        "estimated_revenue_lost": estimated_loss
    }


# ─────────────────────────────────────────────
# RETENTION RATE
# ─────────────────────────────────────────────
def retention_rate(db: Session, clinic_id: str):

    total_patients = db.query(Patient).filter(
        Patient.clinic_id == clinic_id
    ).count()

    returning = db.query(
        Visit.patient_id
    ).filter(
        Visit.clinic_id == clinic_id
    ).distinct().count()

    rate = 0

    if total_patients > 0:
        rate = (returning / total_patients) * 100

    return {
        "total_patients": total_patients,
        "returning_patients": returning,
        "retention_rate": round(rate, 2)
    }


# ─────────────────────────────────────────────
# FOLLOWUPS DUE TODAY
# ─────────────────────────────────────────────
def followups_due_today(db: Session, clinic_id: str):

    today = datetime.utcnow().date()

    followups = db.query(FollowUp).filter(
        FollowUp.clinic_id == clinic_id,
        FollowUp.status == FollowUpStatus.PENDING
    ).all()

    due_today = [
        f for f in followups
        if f.due_date and f.due_date.date() <= today
    ]

    return {
        "date": str(today),
        "count": len(due_today)
    }


# ─────────────────────────────────────────────
# TOP PATIENTS
# ─────────────────────────────────────────────
def top_patients(
    db: Session,
    clinic_id: str,
    limit: int = 5
):

    patients = db.query(Patient).filter(
        Patient.clinic_id == clinic_id
    ).limit(limit).all()

    result = []

    for patient in patients:

        visits = db.query(Visit).filter(
            Visit.patient_id == patient.id
        ).count()

        result.append({
            "patient_id": patient.id,
            "name": (
                f"{patient.first_name} "
                f"{patient.last_name or ''}"
            ).strip(),
            "visits": visits
        })

    return result


# ─────────────────────────────────────────────
# TOP DISEASES TREATED
# ─────────────────────────────────────────────
def top_diseases(
    db: Session,
    clinic_id: str,
    limit: int = 10
):

    rows = db.query(
        Visit.diagnosis,
        func.count(Visit.id).label("count")
    ).filter(
        Visit.clinic_id == clinic_id,
        Visit.diagnosis.isnot(None),
        Visit.diagnosis != ""
    ).group_by(
        Visit.diagnosis
    ).order_by(
        func.count(Visit.id).desc()
    ).limit(limit).all()

    return [
        {
            "disease": row.diagnosis,
            "count": row.count
        }
        for row in rows
    ]


# ─────────────────────────────────────────────
# WHATSAPP DELIVERY RATE
# ─────────────────────────────────────────────
def whatsapp_delivery_rate(
    db: Session,
    clinic_id: str
):

    from app.models.reminder import (
        Reminder,
        ReminderStatus
    )

    total = db.query(Reminder).filter(
        Reminder.clinic_id == clinic_id
    ).count()

    sent = db.query(Reminder).filter(
        Reminder.clinic_id == clinic_id,
        Reminder.status == ReminderStatus.SENT
    ).count()

    failed = db.query(Reminder).filter(
        Reminder.clinic_id == clinic_id,
        Reminder.status == ReminderStatus.FAILED
    ).count()

    pending = db.query(Reminder).filter(
        Reminder.clinic_id == clinic_id,
        Reminder.status == ReminderStatus.PENDING
    ).count()

    rate = round(
        (sent / total * 100),
        2
    ) if total > 0 else 0

    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "pending": pending,
        "delivery_rate_percent": rate
    }