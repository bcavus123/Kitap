"""Plan limitleri ve kota enforcement'ı (Spec Bölüm 20).

Kullanım:
  - require_plan("api_key")  → boolean özellik kapısı; izin yoksa 402
  - get_limit(plan, "max_active_projects") → sayısal limit (None = sınırsız)

Sayısal kotaların (proje/bölüm sayısı, eşzamanlı generate-all) uçlarda
zorlanması Aşama 3-4'te eklenir.
"""
from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.models import User

UNLIMITED = None

PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "max_active_projects": 1,
        "max_chapters_per_project": 10,
        "monthly_chapter_quota": 20,
        "concurrent_generate_all": 1,
        "pdf_export": False,
        "epub_export": False,
        "api_key": False,
    },
    "pro": {
        "max_active_projects": 10,
        "max_chapters_per_project": 100,
        "monthly_chapter_quota": 500,
        "concurrent_generate_all": 3,
        "pdf_export": True,
        "epub_export": True,
        "api_key": True,
    },
    "enterprise": {
        "max_active_projects": UNLIMITED,
        "max_chapters_per_project": UNLIMITED,
        "monthly_chapter_quota": UNLIMITED,
        "concurrent_generate_all": 10,
        "pdf_export": True,
        "epub_export": True,
        "api_key": True,
    },
}


def plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


def get_limit(plan: str, key: str):
    """Sayısal/boolean limit değeri. Tanımsızsa free planın değeri."""
    return plan_limits(plan).get(key, PLAN_LIMITS["free"].get(key))


def require_plan(feature: str):
    """Boolean özellik kapısı dependency'si. İzin yoksa 402 Payment Required."""

    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if not plan_limits(current_user.plan).get(feature, False):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"'{feature}' özelliği '{current_user.plan}' planında kullanılamaz.",
            )
        return current_user

    return _dep
