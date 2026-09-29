from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://rra:rra_secret@localhost:5432/revenue_recovery"
    SYNC_DATABASE_URL: str = "postgresql://rra:rra_secret@localhost:5432/revenue_recovery"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-change-in-production"

    # ── Groq AI ─────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Razorpay Standard Checkout ─────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # ── Razorpay seed values (test merchant) ──────────────────────────────────
    SEED_RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    SEED_RAZORPAY_KEY_SECRET: str = "placeholder_secret"
    SEED_RAZORPAY_WEBHOOK_SECRET: str = "placeholder_webhook_secret"

    # ── Attribution ───────────────────────────────────────────────────────────
    ATTRIBUTION_WINDOW_DAYS: int = 7
    ATTRIBUTION_SCAN_INTERVAL: int = 300  # seconds

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
