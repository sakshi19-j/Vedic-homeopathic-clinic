from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request
)

from sqlalchemy.orm import Session

from pydantic import BaseModel

import razorpay
import os
import hmac
import hashlib
import json

from datetime import datetime

import pytz

from app.database import get_db

from app.middleware.auth_middleware import (
    get_current_user,
    require_plan
)

from app.models.user import User

from app.models.clinic import Clinic


# =====================================================
# ROUTER
# =====================================================

router = APIRouter(
    prefix="/subscription",
    tags=["Subscription"]
)


# =====================================================
# TIMEZONE
# =====================================================

IST = pytz.timezone("Asia/Kolkata")


# =====================================================
# PLAN CONFIG
# =====================================================

PLAN_MAP = {
    "starter_monthly":    "RAZORPAY_STARTER_MONTHLY",
    "starter_6month":     "RAZORPAY_STARTER_6MONTH",
    "starter_yearly":     "RAZORPAY_STARTER_YEARLY",
    "growth_monthly":     "RAZORPAY_GROWTH_MONTHLY",
    "growth_6month":      "RAZORPAY_GROWTH_6MONTH",
    "growth_yearly":      "RAZORPAY_GROWTH_YEARLY",
    "clinicpro_monthly":  "RAZORPAY_CLINICPRO_MONTHLY",
    "clinicpro_6month":   "RAZORPAY_CLINICPRO_6MONTH",
    "clinicpro_yearly":   "RAZORPAY_CLINICPRO_YEARLY",
}


PLAN_LIMITS = {

    "starter": {

        "max_patients_per_month": 100,

        "max_staff": 0,

        "max_doctors": 1
    },

    "growth": {

        "max_patients_per_month": -1,

        "max_staff": 3,

        "max_doctors": 1
    },

    "clinicpro": {

        "max_patients_per_month": -1,

        "max_staff": -1,

        "max_doctors": 5
    },
}


# =====================================================
# RAZORPAY CLIENT
# =====================================================

def get_razorpay_client():

    return razorpay.Client(

        auth=(

            os.getenv("RAZORPAY_KEY_ID"),

            os.getenv("RAZORPAY_KEY_SECRET")
        )
    )


# =====================================================
# REQUEST MODELS
# =====================================================

class CreateSubscriptionRequest(BaseModel):

    plan_key: str


class VerifyPaymentRequest(BaseModel):

    razorpay_payment_id: str

    razorpay_subscription_id: str

    razorpay_signature: str


# =====================================================
# GET SUBSCRIPTION STATUS
# =====================================================

@router.get("/status")
def get_subscription_status(

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)
):

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:

        raise HTTPException(
            status_code=404,
            detail="Clinic not found"
        )

    days_left = None

    if clinic.trial_end_date:

        # ---------------------------------------------
        # SAFE TIMEZONE HANDLING
        # ---------------------------------------------

        trial_end = (

            IST.localize(clinic.trial_end_date)

            if clinic.trial_end_date.tzinfo is None

            else clinic.trial_end_date
        )

        delta = trial_end - datetime.now(IST)

        days_left = max(0, delta.days)

    return {

        "subscription_status":
            (clinic.subscription_status or "").upper(),

        "plan":
            (clinic.subscription_plan or "trial").upper(),

        "trial_end_date":
            clinic.trial_end_date,

        "days_left":
            days_left,

        "max_patients_per_month":
            clinic.max_patients_per_month,

        "max_staff":
            clinic.max_staff,

        "max_doctors":
            clinic.max_doctors,

        "razorpay_sub_id":
            clinic.razorpay_subscription_id,
    }


# =====================================================
# CREATE SUBSCRIPTION
# =====================================================

@router.post("/create")
def create_subscription(

    data: CreateSubscriptionRequest,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)
):

    # -------------------------------------------------
    # VALIDATE PLAN
    # -------------------------------------------------

    if data.plan_key not in PLAN_MAP:

        raise HTTPException(

            status_code=400,

            detail=(
                f"Invalid plan. "
                f"Choose from: {list(PLAN_MAP.keys())}"
            )
        )

    # -------------------------------------------------
    # GET PLAN ID
    # -------------------------------------------------

    plan_id = os.getenv(
        PLAN_MAP[data.plan_key]
    )

    if not plan_id:

        raise HTTPException(

            status_code=500,

            detail="Plan not configured in env vars"
        )

    client = get_razorpay_client()

    # -------------------------------------------------
    # GET CLINIC
    # -------------------------------------------------

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:

        raise HTTPException(
            status_code=404,
            detail="Clinic not found"
        )

    # -------------------------------------------------
    # CREATE SUBSCRIPTION
    # -------------------------------------------------

    if data.plan_key.endswith("_yearly"):
        total_count = 10
    elif data.plan_key.endswith("_6month"):
        total_count = 20
    else:
        total_count = 120

    subscription = client.subscription.create({
        "plan_id": plan_id,
        "total_count": total_count,
        "quantity": 1,
        "customer_notify": 1,
        "notes": {
            "clinic_id": str(current_user.clinic_id),
            "clinic_name": clinic.name,
            "plan_key": data.plan_key,
        }
    })

    return {

        "subscription_id":
            subscription["id"],

        "plan_key":
            data.plan_key,

        "razorpay_key":
            os.getenv("RAZORPAY_KEY_ID"),

        "clinic_name":
            clinic.name,

        "clinic_email":
            current_user.email,
    }


# =====================================================
# VERIFY PAYMENT
# =====================================================

@router.post("/verify")
def verify_payment(

    data: VerifyPaymentRequest,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)
):

    client = get_razorpay_client()

    # -------------------------------------------------
    # VERIFY PAYMENT SIGNATURE
    # -------------------------------------------------

    try:

        client.utility.verify_payment_signature({

            "razorpay_payment_id":
                data.razorpay_payment_id,

            "razorpay_subscription_id":
                data.razorpay_subscription_id,

            "razorpay_signature":
                data.razorpay_signature,
        })

    except Exception:

        raise HTTPException(

            status_code=400,

            detail=(
                "Payment signature invalid "
                "— possible fraud"
            )
        )

    # -------------------------------------------------
    # FETCH SUBSCRIPTION
    # -------------------------------------------------

    sub = client.subscription.fetch(
        data.razorpay_subscription_id
    )

    plan_key = sub.get(
        "notes",
        {}
    ).get(
        "plan_key",
        "growth_monthly"
    )

    tier = plan_key.split("_")[0]

    period = plan_key.split("_")[1]

    # -------------------------------------------------
    # GET CLINIC
    # -------------------------------------------------

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:

        raise HTTPException(
            status_code=404,
            detail="Clinic not found"
        )

    # -------------------------------------------------
    # UPDATE SUBSCRIPTION
    # -------------------------------------------------

    clinic.subscription_status = "ACTIVE"

    clinic.subscription_plan = tier

    clinic.subscription_period = period

    clinic.razorpay_subscription_id = (
        data.razorpay_subscription_id
    )

    clinic.subscription_start_date = (
        datetime.now(IST)
    )

    # -------------------------------------------------
    # APPLY PLAN LIMITS
    # -------------------------------------------------

    limits = PLAN_LIMITS.get(
        tier,
        PLAN_LIMITS["growth"]
    )

    clinic.max_patients_per_month = (
        limits["max_patients_per_month"]
    )

    clinic.max_staff = (
        limits["max_staff"]
    )

    clinic.max_doctors = (
        limits["max_doctors"]
    )

    db.commit()

    return {

        "status":
            "activated",

        "plan":
            tier,

        "period":
            period,

        "features": {

            "max_patients_per_month":
                clinic.max_patients_per_month,

            "max_staff":
                clinic.max_staff,

            "max_doctors":
                clinic.max_doctors
        },

        "message":
            f"Welcome to Vennova {tier.title()}!"
    }


# =====================================================
# WEBHOOK
# =====================================================

@router.post("/webhook")
async def razorpay_webhook(

    request: Request,

    db: Session = Depends(get_db)
):
    """
    Razorpay webhook endpoint.

    Handles:
    - renewals
    - cancellations
    - expiry
    """

    # -------------------------------------------------
    # READ BODY
    # -------------------------------------------------

    body = await request.body()

    # -------------------------------------------------
    # GET SIGNATURE
    # -------------------------------------------------

    signature = request.headers.get(
        "X-Razorpay-Signature",
        ""
    )

    secret = os.getenv(
        "RAZORPAY_WEBHOOK_SECRET",
        ""
    )

    # -------------------------------------------------
    # GENERATE SIGNATURE
    # -------------------------------------------------

    expected = hmac.new(

        key=secret.encode(),

        msg=body,

        digestmod=hashlib.sha256

    ).hexdigest()

    # -------------------------------------------------
    # VERIFY SIGNATURE
    # -------------------------------------------------

    if not hmac.compare_digest(
        expected,
        signature
    ):

        raise HTTPException(

            status_code=400,

            detail="Invalid webhook signature"
        )

    # -------------------------------------------------
    # PARSE JSON
    # -------------------------------------------------

    try:

        event = json.loads(body)

    except Exception:

        raise HTTPException(

            status_code=400,

            detail="Invalid webhook payload"
        )

    etype = event.get("event")

    payload = event.get("payload", {})

    subscription_data = payload.get(
        "subscription",
        {}
    ).get(
        "entity",
        {}
    )

    sub_id = subscription_data.get("id")

    # -------------------------------------------------
    # INVALID SUBSCRIPTION
    # -------------------------------------------------

    if not sub_id:

        return {
            "status": "ignored"
        }

    # -------------------------------------------------
    # SUBSCRIPTION CHARGED
    # -------------------------------------------------

    if etype == "subscription.charged":

        clinic = db.query(Clinic).filter(

            Clinic.razorpay_subscription_id
            == sub_id

        ).first()

        if clinic:

            clinic.subscription_status = "ACTIVE"

            db.commit()

    # -------------------------------------------------
    # SUBSCRIPTION CANCELLED / EXPIRED
    # -------------------------------------------------

    elif etype in [

        "subscription.cancelled",

        "subscription.expired"

    ]:

        clinic = db.query(Clinic).filter(

            Clinic.razorpay_subscription_id
            == sub_id

        ).first()

        if clinic:

            clinic.subscription_status = "EXPIRED"

            db.commit()

    # -------------------------------------------------
    # SUCCESS RESPONSE
    # -------------------------------------------------

    return {
        "status": "ok"
    }


# =====================================================
# EXAMPLE FEATURE LOCKED ROUTES
# =====================================================

@router.get("/features/growth-only")
def growth_feature_example(

    current_user: User = Depends(
        require_plan("growth")
    )
):
    """
    Growth plan feature example.
    """

    return {

        "status":
            "success",

        "feature":
            "Growth plan unlocked"
    }


@router.get("/features/clinicpro-only")
def clinicpro_feature_example(

    current_user: User = Depends(
        require_plan("clinicpro")
    )
):
    """
    ClinicPro feature example.
    """

    return {

        "status":
            "success",

        "feature":
            "ClinicPro feature unlocked"
    }

# =====================================================
# USAGE DASHBOARD
# =====================================================

@router.get("/usage")
def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns current month usage vs plan limits.
    Used by frontend usage dashboard widget.
    """
    from app.models.patient import Patient
    from app.models.staff import Staff
    from datetime import datetime
    import pytz

    IST         = pytz.timezone("Asia/Kolkata")
    now         = datetime.now(IST)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        raise HTTPException(404, "Clinic not found")

    # Patients this month
    patients_this_month = db.query(Patient).filter(
        Patient.clinic_id  == current_user.clinic_id,
        Patient.created_at >= month_start,
        Patient.is_active  == True
    ).count()

    # Active staff
    active_staff = db.query(Staff).filter(
        Staff.clinic_id == current_user.clinic_id,
        Staff.is_active == True
    ).count()

    max_patients = clinic.max_patients_per_month or 100
    max_staff    = clinic.max_staff if clinic.max_staff is not None else 0

    return {
        "plan":    clinic.subscription_plan or "trial",
        "status":  clinic.subscription_status,

        "patients": {
            "used":      patients_this_month,
            "limit":     max_patients,
            "unlimited": max_patients == -1,
            "percent":   0 if max_patients == -1 else round((patients_this_month / max_patients) * 100)
        },
        "staff": {
            "used":      active_staff,
            "limit":     max_staff,
            "unlimited": max_staff == -1,
            "percent":   0 if max_staff <= 0 else round((active_staff / max_staff) * 100)
        },
        "features": {
            "pdf_prescriptions": True,
            "whatsapp":          True,
            "analytics_export":  clinic.subscription_plan in ["growth", "clinicpro"],
            "bulk_import":       clinic.subscription_plan in ["growth", "clinicpro"],
            "multi_doctor":      clinic.subscription_plan == "clinicpro",
            "priority_support":  clinic.subscription_plan == "clinicpro",
        }
    }