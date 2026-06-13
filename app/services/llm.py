"""LLM içerik üretimi.

⚠️ AŞAMA 5 STUB: Gerçek Anthropic Claude streaming çağrısı Aşama 6'da eklenecek
(Spec Bölüm 7.1 adım 4-5, Bölüm 8). Şimdilik deterministik taslak metin üretir ki
görev akışı (task_log, versiyonlama, pub/sub) uçtan uca test edilebilsin.
"""
from __future__ import annotations


def generate_content(
    title: str, description: str | None = None, llm_config: dict | None = None
) -> tuple[str, int, int]:
    """(markdown_içerik, tokens_input, tokens_output) döndürür. STUB."""
    intro = f"Bu bölüm '{title}' başlığını akademik bir çerçevede ele alır."
    if description:
        intro += f" {description}"
    paragraph = (
        f"{intro} Konu, ilgili literatür ışığında tartışılır ve temel kavramlar "
        "sistematik biçimde sunulur. Bulgular eleştirel bir bakışla değerlendirilir."
    )
    content = "\n\n".join(f"## Alt Başlık {i + 1}\n\n{paragraph}" for i in range(4))
    # Token sayıları da stub (Aşama 6'da gerçek usage'dan okunacak)
    return content, 150, max(1, len(content.split()))


def generate_summary(content: str) -> str:
    """Bağlam hafızası için ~200 kelimelik özet — STUB (ilk 40 kelime)."""
    words = content.replace("#", "").split()
    return " ".join(words[:40])
