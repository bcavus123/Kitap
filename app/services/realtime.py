"""Redis pub/sub yayını ve dead-letter (Spec Bölüm 11, 12).

Mimari: Celery worker → Redis pub/sub → FastAPI WS → istemci.
Tüm Redis erişimleri korumalıdır (Redis erişilemezse görev DÜŞMEZ).
"""
from __future__ import annotations

import json

import redis

from app.core.config import settings

DEAD_LETTER_KEY = "dead_letter:generation"


def project_channel(project_id) -> str:
    return f"project:{project_id}"


def _client() -> redis.Redis:
    # Kısa timeout: Redis yoksa hızlı başarısız ol (test/CI'da askıda kalmasın)
    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)


def publish_event(project_id, event: dict) -> None:
    """Olayı projenin Redis kanalına yayınlar. Hata sessizce yutulur."""
    try:
        client = _client()
        client.publish(project_channel(project_id), json.dumps(event))
        client.close()
    except Exception:  # noqa: BLE001
        pass


def push_dead_letter(chapter_id, error: str) -> None:
    """Başarısız görevi dead-letter listesine ekler (admin panelinden requeue — Aşama 8)."""
    try:
        client = _client()
        client.rpush(DEAD_LETTER_KEY, json.dumps({"chapter_id": str(chapter_id), "error": error}))
        client.close()
    except Exception:  # noqa: BLE001
        pass
