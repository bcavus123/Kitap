"""Uygulama yapılandırması — .env'den pydantic-settings ile okunur (Spec Bölüm 4)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ---- Veritabanı ----
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/kitap_db"
    ASYNC_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/kitap_db"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/kitap_test"

    # ---- Redis / Celery ----
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # test/CI'da True → task'lar broker'sız senkron koşar

    # ---- JWT ----
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- Üretim LLM (Anthropic) — global varsayılan; llm_config bunları ezer (Bölüm 8.4) ----
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 8000
    ANTHROPIC_TEMPERATURE: float = 0.5

    # ---- Embedding (semantik hafıza) — Bölüm 10 ----
    SEMANTIC_MEMORY_ENABLED: bool = True
    EMBEDDING_PROVIDER: str = "openai"  # openai | voyage
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536  # DB VECTOR(...) boyutuyla EŞLEŞMELİ
    OPENAI_API_KEY: str = ""
    VOYAGE_API_KEY: str = ""

    # ---- MinIO / S3 ----
    S3_ENDPOINT: str = "http://minio:9000"
    S3_BUCKET: str = "kitap-yazilimi"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    PRESIGNED_URL_EXPIRE_HOURS: int = 24

    # ---- App ----
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000"
    SENTRY_DSN: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Virgülle ayrılmış CORS_ORIGINS değerini listeye çevirir."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
