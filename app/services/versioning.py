"""Bölüm versiyonlama (Spec Bölüm 5.3).

- `ai_generation` versiyonları DB trigger'ı (fn_snapshot_on_done) ile OTOMATİK oluşur.
- `user_edit` (manuel PATCH) ve `regenerate` (force=true) versiyonları trigger ile
  yakalanamadığından UYGULAMA tarafında bu fonksiyonla alınır.

`version_number`, fn_auto_version_number trigger'ı (BEFORE INSERT) ile atanır; burada 0
gönderilir ve trigger gerçek sıradaki numarayı yazar.
"""
from app.models.models import Chapter, ChapterVersion


def snapshot_chapter(db, chapter: Chapter, change_reason: str, token_cost: int = 0) -> bool:
    """Bölümün MEVCUT içeriğinin snapshot'ını ekler. İçerik yoksa no-op (False döner).

    `db.add` senkron olduğundan hem AsyncSession hem Session ile çalışır;
    commit/flush sorumluluğu çağırana aittir.
    """
    if not chapter.content:
        return False
    db.add(
        ChapterVersion(
            chapter_id=chapter.id,
            content=chapter.content,
            change_reason=change_reason,
            token_cost=token_cost,
            version_number=0,  # fn_auto_version_number gerçek numarayı atar
        )
    )
    return True
