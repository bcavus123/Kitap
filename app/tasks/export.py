"""export_project_task — iskelet (Spec Bölüm 7.2).

AŞAMA 5: yalnızca durum geçişlerini ve pub/sub'ı kurar. Gerçek DOCX/PDF/EPUB üretimi
ve MinIO yükleme + presigned URL Aşama 7'de eklenecek.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.session import get_sync_db
from app.models.models import ExportJob
from app.services import realtime
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="export_project", max_retries=2, default_retry_delay=60)
def export_project_task(self, export_job_id: str):
    job_id = export_job_id if isinstance(export_job_id, uuid.UUID) else uuid.UUID(str(export_job_id))
    with get_sync_db() as db:
        job = db.get(ExportJob, job_id)
        if job is None:
            return {"status": "error", "reason": "export_job_not_found"}

        job.status = "processing"
        db.commit()

        # TODO Aşama 7: done bölümleri al → generate_docx/pdf/epub → MinIO upload → presigned_url
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
        return {"status": "done", "export_job_id": str(job.id)}
