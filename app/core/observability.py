"""Loglama (structlog) ve hata izleme (Sentry) — Spec Bölüm 16 adım 43.

Lifespan başlangıcında bir kez çağrılır. Sentry yalnızca SENTRY_DSN doluysa etkinleşir.
"""
from __future__ import annotations

from app.core.config import settings


def setup_observability() -> None:
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )

    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=0.1,
        )
