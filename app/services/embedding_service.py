"""Embedding sağlayıcı soyutlaması (Spec Bölüm 10).

⚠️ AŞAMA 5 STUB: None döner (embedding kaydedilmez, semantik hafıza devre dışı).
Aşama 6'da OpenAI/Voyage entegrasyonu eklenecek; EMBEDDING_PROVIDER'a göre seçilecek.
"""
from __future__ import annotations

from app.core.config import settings


def embed(text: str) -> list[float] | None:
    """text → vektör (list[float]) veya None. Aşama 5: her zaman None."""
    if not settings.SEMANTIC_MEMORY_ENABLED:
        return None
    # TODO Aşama 6: settings.EMBEDDING_PROVIDER -> OpenAI/Voyage çağrısı
    return None
