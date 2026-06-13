"""Canlı duman testi — GERÇEK Anthropic API ile bir bölüm üretir.

Standalone'dur (pytest conftest mock'larından BAĞIMSIZ): doğrudan run_generation çağırır,
böylece gerçek Claude çağrısı yapılır. GitHub Actions 'Live Test' (workflow_dispatch) tarafından
çalıştırılır; ANTHROPIC_API_KEY ortamda GERÇEK olmalıdır.

Akış: bir kullanıcı+proje+bölüm tohumlar → run_generation (9 adım, gerçek LLM) → sonucu yazdırır.
"""
import os
import sys
import uuid

from sqlalchemy import select

from app.db.session import get_sync_db
from app.models.models import Chapter, Citation, Project, ProjectSettings, User
from app.tasks.generation import run_generation


def _seed_chapter() -> str:
    with get_sync_db() as db:
        user = User(
            email=f"live-{uuid.uuid4().hex[:8]}@test.local",
            password_hash="x",
            full_name="Live Test",
        )
        db.add(user)
        db.flush()
        project = Project(
            user_id=user.id,
            title="Canlı Test Kitabı",
            citation_style="APA",
            language="tr",
            target_word_count=2000,
        )
        db.add(project)
        db.flush()
        db.add(ProjectSettings(project_id=project.id))
        chapter = Chapter(
            project_id=project.id,
            order_index=1,
            title="Yapay Zekânın Kısa Tarihçesi",
            description="Giriş niteliğinde bir bölüm.",
            status="queued",
        )
        db.add(chapter)
        db.flush()
        chapter_id = str(chapter.id)
        db.commit()
    return chapter_id


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY") or "REPLACE" in os.environ.get("ANTHROPIC_API_KEY", ""):
        print("HATA: Gerçek ANTHROPIC_API_KEY ortamda yok.")
        return 2

    chapter_id = _seed_chapter()
    print(f"Bölüm tohumlandı: {chapter_id}\nGerçek Claude çağrısı yapılıyor (bu birkaç saniye sürer)...\n")

    result = run_generation(chapter_id, "live-smoke")
    print("Görev sonucu:", result)

    with get_sync_db() as db:
        chapter = db.get(Chapter, uuid.UUID(chapter_id))
        citations = db.execute(
            select(Citation).where(Citation.chapter_id == chapter.id)
        ).scalars().all()

        print(f"\n=== DURUM === status={chapter.status}  word_count={chapter.word_count}")
        print(f"\n=== ÖZET ===\n{chapter.content_summary}")
        print(f"\n=== İÇERİK (ilk 2500 karakter) ===\n{(chapter.content or '')[:2500]}")
        print(f"\n=== ATIFLAR ({len(citations)}) ===")
        for citation in citations:
            print(f"  {citation.marker} [{citation.verification_status}] {citation.raw_title[:90]}")

        # Public API'den okunabilen kısa özet (annotation)
        preview = (chapter.content or "")[:150].replace("%", "%25").replace("\r", " ").replace("\n", " ")
        print(
            f"::notice title=live-result::status={chapter.status} "
            f"words={chapter.word_count} citations={len(citations)} | {preview}"
        )
        return 0 if chapter.status == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
