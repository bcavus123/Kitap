"""generate_chapter_task — 9 adımlı bölüm üretimi (Spec Bölüm 7.1).

AŞAMA 5: LLM ve embedding STUB (services/llm, services/embedding_service). Görev akışı,
task_log, versiyonlama (trigger + regenerate), pub/sub ve hata yönetimi gerçektir.
Gerçek Anthropic/embedding çağrıları Aşama 6'da stub'ların yerine geçecek.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.db.session import get_sync_db
from app.models.models import Chapter, ProjectSettings, TaskLog
from app.services import embedding_service, llm, realtime
from app.services.versioning import snapshot_chapter
from app.tasks.celery_app import celery_app

MAX_RETRIES = 3


def _uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _get_or_create_tasklog(db, chapter_id: uuid.UUID, celery_task_id: str) -> TaskLog:
    tlog = db.execute(
        select(TaskLog).where(TaskLog.celery_task_id == celery_task_id)
    ).scalar_one_or_none()
    if tlog is None:
        tlog = TaskLog(chapter_id=chapter_id, celery_task_id=celery_task_id, status="queued")
        db.add(tlog)
    return tlog


@celery_app.task(
    bind=True,
    name="generate_chapter",
    max_retries=MAX_RETRIES,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=540,
    time_limit=600,
)
def generate_chapter_task(self, chapter_id: str):
    task_id = self.request.id or uuid.uuid4().hex
    return run_generation(chapter_id, task_id)


def run_generation(chapter_id: str, celery_task_id: str) -> dict:
    """9 adımlı akış. Senkron (psycopg2) çalışır — worker ve eager mod için."""
    cid = _uuid(chapter_id)
    started = datetime.now(timezone.utc)

    with get_sync_db() as db:
        chapter = db.get(Chapter, cid)
        if chapter is None:
            return {"status": "error", "reason": "chapter_not_found"}

        # 1) regenerate snapshot (force ile 'done' yeniden üretiliyorsa) + 'generating'
        if chapter.status == "done" and chapter.content:
            snapshot_chapter(db, chapter, "regenerate")
        chapter.status = "generating"

        # 2) task_log started
        tlog = _get_or_create_tasklog(db, chapter.id, celery_task_id)
        tlog.status = "started"
        tlog.started_at = started
        db.commit()

        try:
            settings_row = db.execute(
                select(ProjectSettings).where(ProjectSettings.project_id == chapter.project_id)
            ).scalar_one_or_none()
            llm_config = settings_row.llm_config if settings_row else {}

            # 3) bağlam (Aşama 6'da pgvector cosine similarity) — STUB: atlanır
            # 4) prompt + 5) LLM çağrısı (STUB)
            content, tokens_in, tokens_out = llm.generate_content(
                chapter.title, chapter.description, llm_config
            )

            # 6) içeriği kaydet ('done' → fn_snapshot_on_done trigger'ı ai_generation versiyonu açar)
            chapter.content = content
            chapter.word_count = len(content.split())
            chapter.status = "done"
            chapter.generated_at = datetime.now(timezone.utc)

            # 7) özet + embedding (STUB; embed None → kaydedilmez)
            chapter.content_summary = llm.generate_summary(content)
            vector = embedding_service.embed(chapter.content_summary)
            if vector is not None:
                chapter.embedding = vector

            # 8) task_log tamamla
            finished = datetime.now(timezone.utc)
            tlog.status = "success"
            tlog.tokens_input = tokens_in
            tlog.tokens_output = tokens_out
            tlog.finished_at = finished
            tlog.duration_ms = int((finished - started).total_seconds() * 1000)
            db.commit()

            # 9) WebSocket'e olay yayınla
            realtime.publish_event(
                chapter.project_id,
                {
                    "event": "chapter_update",
                    "chapter_id": str(chapter.id),
                    "project_id": str(chapter.project_id),
                    "status": "done",
                    "data": {"word_count": chapter.word_count, "duration_ms": tlog.duration_ms},
                },
            )
            return {"status": "done", "chapter_id": str(chapter.id), "word_count": chapter.word_count}

        except (Exception, SoftTimeLimitExceeded) as exc:  # noqa: BLE001
            db.rollback()
            _record_failure(db, cid, celery_task_id, str(exc))
            raise


def _record_failure(db, chapter_id: uuid.UUID, celery_task_id: str, error: str) -> None:
    """Hata yönetimi (Spec Bölüm 7.1): retry_count artır, tükenirse error + dead-letter."""
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        return
    chapter.retry_count = (chapter.retry_count or 0) + 1
    exhausted = chapter.retry_count >= MAX_RETRIES
    chapter.status = "error" if exhausted else "queued"

    tlog = _get_or_create_tasklog(db, chapter.id, celery_task_id)
    tlog.status = "failure"
    tlog.error_message = error
    tlog.finished_at = datetime.now(timezone.utc)
    db.commit()

    if exhausted:
        realtime.push_dead_letter(chapter.id, error)
        realtime.publish_event(
            chapter.project_id,
            {
                "event": "chapter_update",
                "chapter_id": str(chapter.id),
                "project_id": str(chapter.project_id),
                "status": "error",
                "data": {"error": error, "retry_count": chapter.retry_count},
            },
        )
