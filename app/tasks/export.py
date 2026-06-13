"""export_project_task — done bölümleri DOCX/PDF/EPUB'a derler (Spec Bölüm 7.2).

AŞAMA 7: formatter ile belge baytları üretilir; boyut kaydedilir ve job 'done' olur.
AŞAMA 8: MinIO yükleme + presigned URL eklenecek (şimdilik s3_path placeholder, url None).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import get_sync_db
from app.models.models import Chapter, Citation, ExportJob, Project
from app.services import formatter, realtime
from app.tasks.celery_app import celery_app

_GENERATORS = {
    "docx": formatter.generate_docx,
    "pdf": formatter.generate_pdf,
    "epub": formatter.generate_epub,
}


@celery_app.task(bind=True, name="export_project", max_retries=2, default_retry_delay=60)
def export_project_task(self, export_job_id: str):
    job_id = export_job_id if isinstance(export_job_id, uuid.UUID) else uuid.UUID(str(export_job_id))
    with get_sync_db() as db:
        job = db.get(ExportJob, job_id)
        if job is None:
            return {"status": "error", "reason": "export_job_not_found"}

        job.status = "processing"
        db.commit()

        try:
            project = db.get(Project, job.project_id)
            chapters = (
                db.execute(
                    select(Chapter)
                    .where(Chapter.project_id == job.project_id, Chapter.status == "done")
                    .order_by(Chapter.order_index)
                )
                .scalars()
                .all()
            )
            citations = (
                db.execute(
                    select(Citation)
                    .join(Chapter, Chapter.id == Citation.chapter_id)
                    .where(Chapter.project_id == job.project_id, Chapter.status == "done")
                    .order_by(Citation.created_at)
                )
                .scalars()
                .all()
            )

            generator = _GENERATORS.get(job.format)
            if generator is None:
                raise ValueError(f"Bilinmeyen format: {job.format}")
            data = generator(project, chapters, citations)

            # TODO Aşama 8: MinIO'ya yükle + presigned_url üret (24 saat)
            job.s3_path = f"exports/{job.project_id}/{job.id}.{job.format}"
            job.file_size_bytes = len(data)
            job.status = "done"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()

            realtime.publish_event(
                job.project_id,
                {
                    "event": "export_done",
                    "project_id": str(job.project_id),
                    "status": "done",
                    "data": {"format": job.format, "export_job_id": str(job.id)},
                },
            )
            return {"status": "done", "export_job_id": str(job.id), "size": job.file_size_bytes}

        except Exception as exc:  # noqa: BLE001
            db.rollback()
            job = db.get(ExportJob, job_id)
            if job is not None:
                job.status = "error"
                job.error_message = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
            raise
