from functools import lru_cache
import logging

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):

    # ─────────────────────────────────────────────
    # App
    # ─────────────────────────────────────────────
    APP_NAME: str = "Vennova Clinic Growth Engine"
    DEBUG: bool = False
    PORT: int = 8000
    ENVIRONMENT: str = "production"

    # ─────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────
    DATABASE_URL: str

    # ─────────────────────────────────────────────
    # JWT — Railway variable: JWT_SECRET
    # This same secret is used by Supabase to sign tokens
    # AND by FastAPI to verify them — one key, one system
    # ─────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # ─────────────────────────────────────────────
    # Supabase
    # ─────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_KEY: str = ""          # anon key
    SUPABASE_SERVICE_KEY: str = ""  # service role key

    # SUPABASE_JWT_SECRET maps to JWT_SECRET
    # Supabase signs tokens with the JWT secret
    # FastAPI reads it from JWT_SECRET — same value
    @property
    def SUPABASE_JWT_SECRET(self) -> str:
        return self.JWT_SECRET

    # ─────────────────────────────────────────────
    # WhatsApp Cloud API
    # ─────────────────────────────────────────────
    WHATSAPP_API_VERSION: str = "v19.0"
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v19.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""

    # ─────────────────────────────────────────────
    # Razorpay
    # ─────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ─────────────────────────────────────────────
    # CORS
    # ─────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "https://app.vennova.in"
    
    CRON_SECRET: str = ""
    # ─────────────────────────────────────────────
    # Logging + Rate Limits
    # ─────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    WHATSAPP_DAILY_LIMIT: int = 950

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def configure_logging():
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)