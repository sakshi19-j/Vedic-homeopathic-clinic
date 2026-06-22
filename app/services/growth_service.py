from sqlalchemy.orm import Session
from sqlalchemy import and_

from datetime import (
    datetime,
    timedelta,
    date
)

from app.models.patient import Patient
from app.models.reminder import (
    FollowUp,
    FollowUpType,
    Channel
)

import pytz


IST = pytz.timezone("Asia/Kolkata")


# =========================================================
# Followup Rules
# =========================================================
FOLLOWUP_RULES = {
    "acute": [3],
    "acute_fever": [3, 7],
    "chronic": [7, 15, 30],
    "chronic_skin": [15, 30, 90],
    "chronic_joint": [7, 30, 90],
    "homeopathy": [7, 15, 30],
    "cardiology": [30, 180],
    "default": [7, 15]
}


# =========================================================
# Schedule Followups
# =========================================================
def schedule_followups(
    db: Session,
    visit_id: str,
    patient_id: str,
    clinic_id: str,
    disease_type: str,
    channel: str = "WHATSAPP"
):
    """
    Automatically create followup reminders
    after visit completion.
    """

    rules = FOLLOWUP_RULES.get(
            (disease_type or "default").lower(),
            FOLLOWUP_RULES["default"]
        )

    now = datetime.now(IST)

    created = []

    for days in rules:

        # IMPORTANT:
        # Store clean DATE only
        due_date = (
            now + timedelta(days=days)
        )

        # -----------------------------------------
        # Followup Type Mapping
        # -----------------------------------------
        if days == 3:
            ftype = FollowUpType.THREE_DAY

        elif days == 7:
            ftype = FollowUpType.SEVEN_DAY

        elif days == 15:
            ftype = FollowUpType.FIFTEEN_DAY

        elif days >= 30:
            ftype = FollowUpType.MONTHLY

        else:
            ftype = FollowUpType.CUSTOM

        # -----------------------------------------
        # Channel Mapping
        # -----------------------------------------
        try:
            followup_channel = Channel[
                channel.upper()
            ]
        except:
            followup_channel = Channel.WHATSAPP

        # -----------------------------------------
        # Prevent duplicate reminders
        # -----------------------------------------
        existing = db.query(FollowUp).filter(
            FollowUp.visit_id == visit_id,
            FollowUp.due_date == due_date,
            FollowUp.type == ftype
        ).first()

        if existing:
            continue

        # -----------------------------------------
        # Create Followup
        # -----------------------------------------
        followup = FollowUp(
            visit_id=visit_id,
            patient_id=patient_id,
            clinic_id=clinic_id,

            due_date=due_date,

            type=ftype,
            channel=followup_channel,

        )

        db.add(followup)

        created.append({
            "days": days,
            "scheduled_for": due_date.strftime("%Y-%m-%d"),
            "type": ftype.value
        })

    db.commit()

    return created


# =========================================================
# Update Patient Lifetime Stats
# =========================================================
def update_patient_stats(
    db: Session,
    patient_id: str,
    fee: float
):

    patient = db.query(Patient).filter(
        Patient.id == patient_id
    ).first()

    if not patient:
        return

    patient.last_visit_date = datetime.now(IST)

    patient.total_visits = (
        patient.total_visits or 0
    ) + 1

    patient.total_spent = float(
        patient.total_spent or 0
    ) + fee

    patient.is_missed = False
    patient.missed_since = None

    # =============================================
    # Patient Value Score
    # =============================================
    score = (
        float(patient.total_spent) * 0.6
    ) + (
        patient.total_visits * 10 * 0.4
    )

    patient.patient_value_score = round(
        score,
        2
    )

    db.commit()


# =========================================================
# Flag Missed Patients
# =========================================================
def flag_missed_patients(
    db: Session,
    clinic_id: str
) -> int:

    now = datetime.now(IST)

    flagged = 0

    patients = db.query(Patient).filter(
        and_(
            Patient.clinic_id == clinic_id,
            Patient.is_active == True,
            Patient.last_visit_date != None,
            Patient.is_missed == False
        )
    ).all()

    for patient in patients:

        expected_return = (
            patient.last_visit_date
            + timedelta(
                days=patient.expected_followup_days or 7
            )
        )

        # Grace period
        if now > expected_return + timedelta(days=2):

            patient.is_missed = True
            patient.missed_since = expected_return

            flagged += 1

    db.commit()

    return flagged

# =========================================================
# Birthday Patients — due today
# =========================================================
def get_birthday_patients(db: Session, clinic_id: str) -> list:
    """
    Returns all patients whose birthday is today.
    Checks month + day only (ignores year).
    """
    from app.models.patient import Patient
    today = datetime.now(IST).date()

    patients = db.query(Patient).filter(
        Patient.clinic_id  == clinic_id,
        Patient.is_active  == True,
        Patient.dob        != None,
        Patient.whatsapp_opt_out == False
    ).all()

    birthday_patients = []
    for p in patients:
        if p.dob and p.dob.month == today.month and p.dob.day == today.day:
            birthday_patients.append(p)

    return birthday_patients


# =========================================================
# Missed Patient Re-engagement List
# =========================================================
def get_reengagement_patients(db: Session, clinic_id: str) -> list:
    """
    Returns missed patients at 30 / 60 / 90 day marks.
    Only returns patients exactly on those milestones (±1 day grace).
    """
    from app.models.patient import Patient
    now   = datetime.now(IST)
    today = now.date()

    patients = db.query(Patient).filter(
        Patient.clinic_id    == clinic_id,
        Patient.is_active    == True,
        Patient.is_missed    == True,
        Patient.missed_since != None,
        Patient.whatsapp_opt_out == False
    ).all()

    targets = []
    for p in patients:
        if not p.missed_since:
            continue
        missed_date = p.missed_since.date() if hasattr(p.missed_since, 'date') else p.missed_since
        days_missed = (today - missed_date).days

        # Hit 30 / 60 / 90 day marks (±1 day window)
        if days_missed in range(29, 32) or \
           days_missed in range(59, 62) or \
           days_missed in range(89, 92):
            targets.append({
                "patient":     p,
                "days_missed": days_missed
            })

    return targets


# =========================================================
# Appointment Reminders Due
# =========================================================
def get_appointment_reminders(db: Session, clinic_id: str, hours_ahead: int) -> list:
    """
    Returns appointments happening in exactly `hours_ahead` hours.
    Used for 24hr and 1hr reminders.
    """
    from app.models.appointment import Appointment
    now        = datetime.now(IST)
    target     = now + timedelta(hours=hours_ahead)
    window_start = target - timedelta(minutes=15)
    window_end   = target + timedelta(minutes=15)

    appointments = db.query(Appointment).filter(
        Appointment.clinic_id      == clinic_id,
        Appointment.status         == "SCHEDULED",
        Appointment.scheduled_time >= window_start,
        Appointment.scheduled_time <= window_end,
        Appointment.reminder_sent  == False
    ).all()

    return appointments