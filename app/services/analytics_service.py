from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import pytz

from app.models.visit import Visit, PaymentStatus
from app.models.patient import Patient
from app.models.reminder import (
    FollowUp,
    FollowUpStatus,
    WhatsAppLog,
    DeliveryStatus
)

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────
# DAILY REVENUE
# ─────────────────────────────────────────────
def daily_revenue(db: Session, clinic_id: str):

    now_ist = datetime.now(IST)
    start_of_day = IST.localize(
        datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0)
    )
    end_of_day = IST.localize(
        datetime(now_ist.year, now_ist.month, now_ist.day, 23, 59, 59)
    )

    revenue = db.query(
        func.sum(Visit.fee)
    ).filter(
        Visit.clinic_id == clinic_id,
        Visit.payment_status == PaymentStatus.PAID,
        Visit.closed_at >= start_of_day,
        Visit.closed_at <= end_of_day
    ).scalar()

    return {
        "date": now_ist.strftime("%Y-%m-%d"),
        "revenue": float(revenue or 0)
    }


# ─────────────────────────────────────────────
# WEEKLY REVENUE (last 7 days breakdown)
# ─────────────────────────────────────────────
def weekly_revenue(db: Session, clinic_id: str):

    now_ist = datetime.now(IST)
    days = []

    for i in range(6, -1, -1):
        day_ist = now_ist - timedelta(days=i)
        start = IST.localize(
            datetime(day_ist.year, day_ist.month, day_ist.day, 0, 0, 0)
        )
        end = IST.localize(
            datetime(day_ist.year, day_ist.month, day_ist.day, 23, 59, 59)
        )
        revenue = db.query(
            func.sum(Visit.fee)
        ).filter(
            Visit.clinic_id == clinic_id,
            Visit.payment_status == PaymentStatus.PAID,
            Visit.closed_at >= start,
            Visit.closed_at <= end
        ).scalar()

        days.append({
            "date": day_ist.strftime("%Y-%m-%d"),
            "day": day_ist.strftime("%a"),
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

    now_ist = datetime.now(IST)
    start_of_month = IST.localize(
        datetime(now_ist.year, now_ist.month, 1, 0, 0, 0)
    )
    if now_ist.month == 12:
        end_of_month = IST.localize(
            datetime(now_ist.year + 1, 1, 1, 0, 0, 0)
        ) - timedelta(seconds=1)
    else:
        end_of_month = IST.localize(
            datetime(now_ist.year, now_ist.month + 1, 1, 0, 0, 0)
        ) - timedelta(seconds=1)

    revenue = db.query(
        func.sum(Visit.fee)
    ).filter(
        Visit.clinic_id == clinic_id,
        Visit.payment_status == PaymentStatus.PAID,
        Visit.closed_at >= start_of_month,
        Visit.closed_at <= end_of_month
    ).scalar()

    return {
        "month": now_ist.strftime("%B"),
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

        if (
            last_visit and
            last_visit.visit_date and
            last_visit.visit_date.replace(tzinfo=None)
            < cutoff.replace(tzinfo=None)
        ):

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

# =====================================================
# FOLLOWUPS DUE TODAY
# =====================================================

def followups_due_today(
    db: Session,
    clinic_id: str
):

    today = datetime.utcnow().date()

    followups = db.query(
        FollowUp
    ).filter(
        FollowUp.clinic_id == clinic_id,
        FollowUp.status == FollowUpStatus.PENDING
    ).all()

    due_today = [

        f for f in followups

        if (
            f.due_date
            and
            f.due_date <= today
        )
    ]

    return {

        "date":
            str(today),

        "count":
            len(due_today),

        "followups":
            due_today
    }





# ─────────────────────────────────────────────
# TOP PATIENTS
# ─────────────────────────────────────────────
def top_patients(
    db: Session,
    clinic_id: str,
    limit: int = 5
):

    rows = (
        db.query(
            Patient.id,
            Patient.first_name,
            Patient.last_name,
            func.count(Visit.id).label("visits")
        )
        .join(
            Visit,
            Visit.patient_id == Patient.id
        )
        .filter(
            Patient.clinic_id == clinic_id
        )
        .group_by(
            Patient.id,
            Patient.first_name,
            Patient.last_name
        )
        .order_by(
            func.count(Visit.id).desc()
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "patient_id": row.id,
            "name": f"{row.first_name} {row.last_name or ''}".strip(),
            "visits": row.visits
        }
        for row in rows
    ]


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

    total = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == clinic_id
    ).count()

    sent = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == clinic_id,
        WhatsAppLog.delivery_status.in_([
            DeliveryStatus.SENT,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.READ
        ])
    ).count()

    delivered = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == clinic_id,
        WhatsAppLog.delivery_status == DeliveryStatus.DELIVERED
    ).count()

    read = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == clinic_id,
        WhatsAppLog.delivery_status == DeliveryStatus.READ
    ).count()

    failed = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == clinic_id,
        WhatsAppLog.delivery_status == DeliveryStatus.FAILED
    ).count()

    pending = db.query(WhatsAppLog).filter(
        WhatsAppLog.clinic_id == clinic_id,
        WhatsAppLog.delivery_status == DeliveryStatus.SENT
    ).count()

    rate = round(
        (delivered / total * 100),
        2
    ) if total > 0 else 0

    return {
        "total": total,
        "sent": sent,
        "delivered": delivered,
        "read": read,
        "failed": failed,
        "pending": pending,
        "delivery_rate_percent": rate
    }

