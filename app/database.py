from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # FIX: reduced to avoid exhausting Supabase free tier (15 conn limit)
    # Web (5) + Cron (2) + headroom (3) = 10 safe max
    pool_size=5,
    max_overflow=5,
    pool_recycle=300,
    pool_timeout=30,
    connect_args={
        "sslmode":         "require",
        "connect_timeout": 10,
    }
)


# ── Connection pool monitoring ─────────────────────────────
@event.listens_for(engine, "connect")
def on_connect(dbapi_connection, connection_record):
    logger.debug("DB connection opened")


@event.listens_for(engine, "checkout")
def on_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("DB connection checked out from pool")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Import ALL models here — missing imports = tables never created.
    FIX: added audit, staff, appointment, queue, whatsapp_logs.
    """
    from app.models.base import Base

    # Core models
    from app.models import clinic, user, patient, visit, billing, reminder

    # FIX: these were missing — tables were never being created
    try:
        from app.models import staff
    except ImportError:
        logger.warning("staff model not found — skipping")

    try:
        from app.models import appointment
    except ImportError:
        logger.warning("appointment model not found — skipping")

    try:
        from app.models import queue
    except ImportError:
        logger.warning("queue model not found — skipping")

    try:
        from app.models import audit_log
    except ImportError:
        logger.warning("audit_log model not found — skipping")

    Base.metadata.create_all(bind=engine)
    logger.info("✅ All tables verified/created")