from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Subscription Tracker"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_ASSISTANT_ID: str | None = None

    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Email Processing
    DEFAULT_BATCH_SIZE: int = 100
    DEFAULT_CONFIDENCE_AUTO_ACCEPT: float = 85.0
    DEFAULT_CONFIDENCE_REVIEW_MIN: float = 50.0
    DEFAULT_SYNC_PERIOD_DAYS: int = 30  # Default email sync period

    # OpenAI Rate Limiting
    OPENAI_REQUEST_DELAY_SECONDS: float = 1.0  # Delay between OpenAI API calls
    OPENAI_MAX_REQUESTS_PER_MINUTE: int = 60  # Rate limit for OpenAI API

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Registration Control
    REQUIRE_INVITE_TOKEN: bool = True  # Require invite token for registration in production

    # SendGrid
    SENDGRID_API_KEY: str = "your_sendgrid_api_key_here"
    SENDGRID_FROM_EMAIL: str = "noreply@subscriptiontracker.app"
    SENDGRID_FROM_NAME: str = "Subscription Tracker"

    # Push Notifications (VAPID)
    VAPID_PUBLIC_KEY: str
    VAPID_PRIVATE_KEY: str
    VAPID_CLAIM_EMAIL: str = "mailto:noreply@subscriptiontracker.app"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
