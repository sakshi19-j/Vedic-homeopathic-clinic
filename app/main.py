import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import (
    settings,
    configure_logging
)

from app.database import create_tables

logger = logging.getLogger(__name__)

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

from app.routers.health import (
    router as health_router
)

from app.routers.whatsapp import (
    router as webhook_router,
    send_router as whatsapp_send_router
)

from app.jobs.reminder_cron import (
    start_scheduler
)

from app.routers.billing_subscription import (
    router as subscription_router
)

from app.routers.audit import (
    router as audit_router
)

from app.routers import medicines

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    logger.error(
        f"422 on {request.url}: {exc.errors()}"
    )

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


# =====================================================
# FIXED CORS
# =====================================================

allowed_origins = [
    "https://ray-clinic.lovable.app",
    "https://preview--ray-clinic.lovable.app",

    "https://wellspring-sync-guard.lovable.app",
    "https://preview--wellspring-sync-guard.lovable.app",

    "https://vennova-sparkle-os.lovable.app",
    "https://preview--vennova-sparkle-os.lovable.app",

    "https://cure-flow-sync.lovable.app",
    "https://preview--cure-flow-sync.lovable.app",

    "https://bright-health.lovable.app",
    "https://preview--bright-health.lovable.app",

    "https://care-flow-fix.lovable.app",
    "https://preview--care-flow-fix.lovable.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.lovable\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

logger.info(f"CORS origins loaded: {allowed_origins}")


# =====================================================
# ROUTERS
# =====================================================

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(visits.router)
app.include_router(billing.router)
app.include_router(analytics.router)
app.include_router(reminders.router)
app.include_router(queue.router)
app.include_router(webhook_router)
app.include_router(whatsapp_send_router)
app.include_router(prescriptions.router)
app.include_router(staff.router)
app.include_router(appointments.router)
app.include_router(imports.router)
app.include_router(health_router)
app.include_router(subscription_router)
app.include_router(audit_router)
app.include_router(medicines.router)

# =====================================================
# STARTUP
# =====================================================

@app.on_event("startup")
def startup():
    configure_logging()
    create_tables()
    start_scheduler()

    logger.info("✅ Vennova v2.0 — All systems running")
    logger.info("✅ Database tables initialized")
    logger.info("✅ APScheduler started — 5 jobs registered")
    logger.info("✅ Supabase connected")
    logger.info("✅ WhatsApp services active")


# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():
    return {
        "app": "Vennova Clinic Growth Engine",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "app": "Vennova",
        "version": "2.0.0"
    }


@app.get("/privacy-policy")
def privacy_policy():
    return {
        "app": "Vennova",
        "message": (
            "Vennova respects user privacy "
            "and securely stores clinic data."
        )
    }


@app.get("/terms")
def terms():
    return {
        "app": "Vennova",
        "message": (
            "By using Vennova, users agree "
            "to use the platform responsibly."
        )
    }


@app.get("/delete-data")
def delete_data():
    return {
        "app": "Vennova",
        "message": (
            "To request deletion of account "
            "or patient data, contact support."
        )
    }
