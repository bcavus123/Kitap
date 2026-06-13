"""CrossRef DOI doğrulama (Spec Bölüm 9.4).

verify_doi → (status, crossref_data). status: verified | not_found | mismatch.
Doğrulanamayan atıflar SİLİNMEZ; çıktıda işaretlenir (formatter.format_citation).

NOT: Testlerde httpx.get mock'lanır; CI gerçek CrossRef çağırmaz.
"""
from __future__ import annotations

import httpx

CROSSREF_URL = "https://api.crossref.org/works/"


def _norm(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum() or ch.isspace()).strip()


def verify_doi(doi: str, expected_title: str | None = None) -> tuple[str, dict | None]:
    """DOI'yi CrossRef'te doğrular.

    - verified : DOI bulundu ve (varsa) başlık eşleşti
    - not_found: DOI/kayıt bulunamadı veya ağ hatası
    - mismatch : DOI var ama başlık tutmuyor
    """
    if not doi:
        return "not_found", None
    try:
        resp = httpx.get(
            f"{CROSSREF_URL}{doi}",
            timeout=15,
            headers={"User-Agent": "KitapYazma/1.0 (mailto:noreply@example.com)"},
        )
    except Exception:  # noqa: BLE001
        return "not_found", None

    if resp.status_code != 200:
        return "not_found", None

    data = resp.json().get("message", {})
    if expected_title:
        cr_title = _norm(" ".join(data.get("title", []) or []))
        want = _norm(expected_title)
        if want and cr_title and want[:40] not in cr_title and cr_title[:40] not in want:
            return "mismatch", data
    return "verified", data


def verify_citation(db, citation) -> str:
    """Bir Citation kaydını CrossRef ile doğrular ve günceller. Yeni status'ü döndürür."""
    status, data = verify_doi(citation.doi, citation.raw_title)
    citation.verification_status = status
    citation.doi_verified = status == "verified"
    if data is not None:
        citation.crossref_data = data
    db.add(citation)
    return status
