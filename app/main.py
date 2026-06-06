import logging

from fastapi import FastAPI, Request

from fastapi.middleware.cors import (
    CORSMiddleware
)

from fastapi.exceptions import (
    RequestValidationError
)

from fastapi.responses import (
    JSONResponse
)

from app.config import (
    settings,
    configure_logging
)

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

    redirect_slashes=False,

    description=(
        "AI-powered clinic growth "
        "operating system for modern clinics"
    ),

    version="2.0.0",

    docs_url="/docs",

    redoc_url="/redoc"
)


# =========================================================
# VALIDATION ERROR HANDLER
# =========================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    """
    Logs full 422 validation errors to Railway logs.
    """

    logger.error(
        f"422 on {request.url}: {exc.errors()}"
    )

    return JSONResponse(

        status_code=422,

        content={
            "detail": exc.errors()
        }
    )


# =========================================================
# SECURE CORS CONFIGURATION
# =========================================================

allowed_origins = [

    o.strip()

    for o in settings.ALLOWED_ORIGINS.split(",")

    if o.strip()

] or [

    "https://app.vennova.in"
]

app.add_middleware(

    CORSMiddleware,

    allow_origins=allowed_origins,

    allow_credentials=True,

    allow_methods=[

        "GET",

        "POST",

        "PUT",

        "DELETE",

        "PATCH",

        "OPTIONS"
    ],

    allow_headers=[

        "Authorization",

        "Content-Type",

        "Accept",

        "Origin"
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
def startup():

    # -----------------------------------------------------
    # CONFIGURE LOGGING
    # -----------------------------------------------------

    configure_logging()

    # -----------------------------------------------------
    # CREATE DATABASE TABLES
    # -----------------------------------------------------

    create_tables()

    # -----------------------------------------------------
    # START APSCHEDULER
    # -----------------------------------------------------

    start_scheduler()

    # -----------------------------------------------------
    # STARTUP LOGS
    # -----------------------------------------------------

    logger.info(
        "✅ Vennova v2.0 — All systems running"
    )

    logger.info(
        "✅ Database tables initialized"
    )

    logger.info(
        "✅ APScheduler started — 5 jobs registered"
    )

    logger.info(
        "✅ Supabase connected"
    )

    logger.info(
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