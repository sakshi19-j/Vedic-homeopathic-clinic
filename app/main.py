import os
import logging

from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware
)

from app.config import settings

from app.database import create_tables


# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)


# =========================================================
# ROUTERS
# =========================================================

from app.routers import (
    analytics,
    auth,
    patients,
    visits,
    billing,
    reminders,
    queue,
    prescriptions,
    staff,
    appointments,
    imports
)

# Health Router
from app.routers.health import (
    router as health_router
)

# WhatsApp Routers
from app.routers.whatsapp import (

    router as webhook_router,

    send_router as whatsapp_send_router
)

# Scheduler
from app.jobs.reminder_cron import (
    start_scheduler
)

# Subscription Router
from app.routers.billing_subscription import (
    router as subscription_router
)

# Audit Router
from app.routers.audit import (
    router as audit_router
)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(

    title="Vennova Clinic Growth Engine API",

    description=(
        "AI-powered clinic growth "
        "operating system for modern clinics"
    ),

    version="2.0.0",

    docs_url="/docs",

    redoc_url="/redoc"
)


# =========================================================
# SECURE CORS CONFIGURATION
# =========================================================

allowed_origins = os.getenv(

    "ALLOWED_ORIGINS",

    "https://app.vennova.in"
).split(",")

app.add_middleware(

    CORSMiddleware,

    allow_origins=allowed_origins,

    allow_credentials=True,

    allow_methods=[

        "GET",

        "POST",

        "PUT",

        "DELETE",

        "PATCH"
    ],

    allow_headers=[

        "Authorization",

        "Content-Type"
    ],
)


# =========================================================
# INCLUDE ROUTERS
# =========================================================

# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------

app.include_router(
    auth.router
)

# ---------------------------------------------------------
# PATIENTS
# ---------------------------------------------------------

app.include_router(
    patients.router
)

# ---------------------------------------------------------
# VISITS / CONSULTATIONS
# ---------------------------------------------------------

app.include_router(
    visits.router
)

# ---------------------------------------------------------
# BILLING / PAYMENTS
# ---------------------------------------------------------

app.include_router(
    billing.router
)

# ---------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------

app.include_router(
    analytics.router
)

# ---------------------------------------------------------
# FOLLOWUPS / REMINDERS
# ---------------------------------------------------------

app.include_router(
    reminders.router
)

# ---------------------------------------------------------
# QUEUE
# ---------------------------------------------------------

app.include_router(
    queue.router
)

# ---------------------------------------------------------
# WHATSAPP
# ---------------------------------------------------------

app.include_router(
    webhook_router
)

app.include_router(
    whatsapp_send_router
)

# ---------------------------------------------------------
# PRESCRIPTIONS
# ---------------------------------------------------------

app.include_router(
    prescriptions.router
)

# ---------------------------------------------------------
# STAFF MANAGEMENT
# ---------------------------------------------------------

app.include_router(
    staff.router
)

# ---------------------------------------------------------
# APPOINTMENTS
# ---------------------------------------------------------

app.include_router(
    appointments.router
)

# ---------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------

app.include_router(
    imports.router
)

# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

app.include_router(
    health_router
)

# ---------------------------------------------------------
# SUBSCRIPTIONS
# ---------------------------------------------------------

app.include_router(
    subscription_router
)

# ---------------------------------------------------------
# AUDIT LOGS
# ---------------------------------------------------------

app.include_router(
    audit_router
)


# =========================================================
# STARTUP EVENT
# =========================================================

@app.on_event("startup")
async def startup():
    """
    Runs when FastAPI server starts.

    Production-safe startup:
    - doesn't crash on DB init errors
    - handles Railway cold starts better
    - safely starts APScheduler
    """

    # -------------------------------------------------
    # CREATE DATABASE TABLES
    # -------------------------------------------------

    try:

        create_tables()

        print(
            "✅ Database tables initialized"
        )

    except Exception as e:

        logger.error(
            f"❌ DB init error: {e}"
        )

    # -------------------------------------------------
    # START APSCHEDULER
    # -------------------------------------------------

    try:

        start_scheduler()

        print(
            "✅ APScheduler started"
        )

    except Exception as e:

        logger.error(
            f"❌ Scheduler startup error: {e}"
        )

    # -------------------------------------------------
    # FINAL STARTUP LOGS
    # -------------------------------------------------

    print(
        "✅ Vennova v2.0 — All systems running"
    )

    print(
        "✅ Supabase connected"
    )

    print(
        "✅ WhatsApp services active"
    )


# =========================================================
# ROOT ENDPOINT
# =========================================================

@app.get("/")
def root():

    return {

        "app":
            "Vennova Clinic Growth Engine",

        "version":
            "2.0.0",

        "status":
            "running",

        "docs":
            "/docs"
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {

        "status":
            "healthy",

        "app":
            "Vennova",

        "version":
            "2.0.0"
    }


# =========================================================
# PRIVACY POLICY
# =========================================================

@app.get("/privacy-policy")
def privacy_policy():
    """
    Meta required privacy policy endpoint.
    """

    return {

        "app":
            "Vennova",

        "message":
            (
                "Vennova respects user privacy "
                "and securely stores clinic data. "
                "Users may contact support for "
                "data-related requests."
            )
    }


# =========================================================
# TERMS & CONDITIONS
# =========================================================

@app.get("/terms")
def terms():
    """
    Meta required terms endpoint.
    """

    return {

        "app":
            "Vennova",

        "message":
            (
                "By using Vennova, users agree "
                "to use the platform responsibly "
                "for clinic management and "
                "patient communication purposes."
            )
    }


# =========================================================
# DELETE USER DATA
# =========================================================

@app.get("/delete-data")
def delete_data():
    """
    Meta required data deletion endpoint.
    """

    return {

        "app":
            "Vennova",

        "message":
            (
                "To request deletion of account "
                "or patient data, contact support."
            )
    }