"""Admin uçları: dead-letter yönetimi (Spec Bölüm 6.6). role=admin gerektirir."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.models import Chapter, User
from app.services import realtime
from app.tasks.generation import generate_chapter_task

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dead-letter")
async def list_dead_letter(_: User = Depends(get_current_admin)) -> dict:
    items = realtime.list_dead_letter()
    return {"count": len(items), "items": items}


@router.post("/dead-letter/{chapter_id}/requeue", status_code=status.HTTP_202_ACCEPTED)
async def requeue_chapter(
    chapter_id: uuid.UUID,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chapter = await db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bölüm bulunamadı.")
    chapter.status = "pending"
    chapter.retry_count = 0
    await db.commit()
    result = generate_chapter_task.apply_async(args=[str(chapter.id)], queue="generation")
    realtime.remove_dead_letter(chapter.id)
    return {"detail": "requeued", "chapter_id": str(chapter.id), "celery_task_id": result.id}


@router.delete("/dead-letter/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def drop_dead_letter(
    chapter_id: uuid.UUID, _: User = Depends(get_current_admin)
) -> None:
    realtime.remove_dead_letter(chapter_id)
