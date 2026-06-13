"""Embedding sağlayıcı soyutlaması (Spec Bölüm 10).

EMBEDDING_PROVIDER'a göre OpenAI (SDK) veya Voyage AI (httpx) çağırır.
Anahtar yoksa veya hata olursa None döner → semantik hafıza zarif şekilde devre dışı kalır
(üretim bloklanmaz; generation.py order_index fallback'ine düşer).

⚠️ Boyut, `chapters.embedding VECTOR(1536)` ile eşleşmeli: openai text-embedding-3-small=1536.
Voyage (voyage-3=1024) seçilirse migration ile sütun boyutu güncellenmelidir.

NOT: Testlerde `embed` mock'lanır (conftest); CI gerçek API çağırmaz.
"""
from __future__ import annotations

import httpx

from app.core.config import settings


def embed(text: str) -> list[float] | None:
    """text → vektör (list[float]) veya None."""
    if not settings.SEMANTIC_MEMORY_ENABLED or not text:
        return None
    provider = settings.EMBEDDING_PROVIDER.lower()
    try:
        if provider == "openai":
            return _openai_embed(text)
        if provider == "voyage":
            return _voyage_embed(text)
    except Exception:  # noqa: BLE001 — embedding hatası üretimi bloklamamalı
        return None
    return None


def _openai_embed(text: str) -> list[float] | None:
    if not settings.OPENAI_API_KEY or "REPLACE" in settings.OPENAI_API_KEY:
        return None
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=text)
    return list(resp.data[0].embedding)


def _voyage_embed(text: str) -> list[float] | None:
    if not settings.VOYAGE_API_KEY:
        return None
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.VOYAGE_API_KEY}"},
        json={"model": settings.EMBEDDING_MODEL, "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    return list(resp.json()["data"][0]["embedding"])
