"""LLM içerik üretimi — Anthropic Claude (Spec Bölüm 7.1, 8).

Senkron `anthropic` SDK kullanır (Celery worker senkron çalışır). Model/temperature/
max_tokens önceliği: project_settings.llm_config > .env ANTHROPIC_* (Spec Bölüm 8.4).

NOT: Testlerde bu modülün fonksiyonları mock'lanır (conftest); CI gerçek API çağırmaz.
"""
from __future__ import annotations

from dataclasses import dataclass

import anthropic

from app.core.config import settings


@dataclass
class ChapterPrompt:
    title: str
    description: str | None
    context: str
    tone_profile: str
    audience_level: str
    citation_style: str
    target_word_count: int
    human_writing_mode: bool
    language: str = "tr"


def _resolve(llm_config: dict | None, key: str, default):
    if llm_config and llm_config.get(key) is not None:
        return llm_config[key]
    return default


def build_prompt(p: ChapterPrompt) -> tuple[str, str]:
    """(system_prompt, user_prompt) üretir (Spec Bölüm 8.1 / 8.2)."""
    human_rules = ""
    if p.human_writing_mode:
        human_rules = (
            "\nİNSAN YAZISI KURALLARI:\n"
            "- Cümle uzunluklarını çeşitlendir (kısa ve uzun cümleler dönüşümlü).\n"
            "- Her paragrafı benzer uzunlukta bitirme; yapı kalıplarını tekrarlama.\n"
            "- Akademisyenlerin kullandığı bağlaçları kullan, zaman zaman birinci çoğul kişi.\n"
            "- Yerinde soru formları ve düşünce yönlendirmeleri ekle.\n"
        )

    system_prompt = (
        "Sen deneyimli bir akademik yazarsın.\n"
        f"Yazı tonu: {p.tone_profile} | Hedef kitle: {p.audience_level} | "
        f"Atıf formatı: {p.citation_style} | Dil: {p.language}\n"
        f"Hedef kelime sayısı: {p.target_word_count} kelime (±%15 sapma kabul edilir).\n"
        f"{human_rules}\n"
        "KESİNLİKLE UYULACAK KURALLAR:\n"
        "- Her iddiayı kaynakla destekle, atıf işaretçisi [1], [2]... kullan.\n"
        "- Uydurma DOI/atıf ÜRETME; emin değilsen atıfı işaretçisiz bırak.\n"
        "- Tablolar için Markdown tablo söz dizimi kullan.\n"
        "- Görsel önerilerini <!-- GÖRSEL: açıklama --> olarak işaretle.\n"
        "- Başlığı tekrar etme, doğrudan içeriğe gir."
    )

    context_block = f"Önceki ilgili bölümlerin özeti:\n{p.context}\n\n" if p.context else ""
    user_prompt = (
        f"{context_block}"
        f"Bölüm: {p.title}\n"
        f"Açıklama: {p.description or '-'}\n\n"
        "Yukarıdaki başlık için akademik bir bölüm yaz."
    )
    return system_prompt, user_prompt


def _client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY or "REPLACE" in settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY ayarlı değil (gerçek üretim için gerekli).")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def generate_content(prompt: ChapterPrompt, llm_config: dict | None = None) -> tuple[str, int, int]:
    """(markdown_içerik, tokens_input, tokens_output). Anthropic streaming çağrısı."""
    system_prompt, user_prompt = build_prompt(prompt)
    model = _resolve(llm_config, "model", settings.ANTHROPIC_MODEL)
    max_tokens = int(_resolve(llm_config, "max_tokens", settings.ANTHROPIC_MAX_TOKENS))
    temperature = float(_resolve(llm_config, "temperature", settings.ANTHROPIC_TEMPERATURE))

    client = _client()
    parts: list[str] = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            parts.append(chunk)
        final = stream.get_final_message()

    content = "".join(parts) or (final.content[0].text if final.content else "")
    return content, final.usage.input_tokens, final.usage.output_tokens


def generate_summary(content: str, llm_config: dict | None = None) -> str:
    """Bağlam hafızası için ~200 kelimelik özet (Spec Bölüm 10 adım 1)."""
    model = _resolve(llm_config, "model", settings.ANTHROPIC_MODEL)
    client = _client()
    message = client.messages.create(
        model=model,
        max_tokens=400,
        temperature=0.3,
        system="Akademik metinleri özetleyen bir asistansın. Yalnızca özet döndür.",
        messages=[
            {
                "role": "user",
                "content": (
                    "Aşağıdaki bölümü, sonraki bölümlerle terminoloji/argüman tutarlılığı "
                    "için ~200 kelimede özetle:\n\n" + content[:8000]
                ),
            }
        ],
    )
    return message.content[0].text if message.content else ""
