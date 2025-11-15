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

    # Email Processing
    DEFAULT_BATCH_SIZE: int = 100
    DEFAULT_CONFIDENCE_AUTO_ACCEPT: float = 85.0
    DEFAULT_CONFIDENCE_REVIEW_MIN: float = 50.0

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
