"""Celery uygulaması ve konfigürasyonu (Spec Bölüm 7, 7.3).

Task modülleri `include` ile worker başlangıcında yüklenir; bu sayede
celery_app ↔ generation/export arasında döngüsel import oluşmaz.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "kitap",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.generation", "app.tasks.export"],
)

celery_app.conf.update(
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,  # test/CI: broker'sız senkron
    task_eager_propagates=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue="generation",
    task_routes={
        "generate_chapter": {"queue": "generation"},
        "export_project": {"queue": "export"},
    },
    timezone="UTC",
)
