"""Chapters endpoint'leri: TOC import, listeleme, PATCH (versiyonlama), generate (Spec Bölüm 6.3).

NOT: Celery dispatch'i Aşama 4'te MOCK'lanır (sahte task_id + task_log). Gerçek görev
çağrısı ve regenerate snapshot'ı Aşama 5'te (Celery) eklenecek.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.db.session import get_db
from app.models.models import Chapter, Project, TaskLog
from app.schemas.schemas import (
    ChapterOut,
    ChapterUpdate,
    GenerateAllResponse,
    GenerateRequest,
    GenerateResponse,
    TaskLogOut,
    TocImport,
)
from app.services.versioning import snapshot_chapter
from app.tasks.generation import generate_chapter_task

router = APIRouter(prefix="/projects/{project_id}/chapters", tags=["chapters"])


async def _get_chapter(db: AsyncSession, project: Project, chapter_id: uuid.UUID) -> Chapter:
    stmt = select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project.id)
    chapter = (await db.execute(stmt)).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bölüm bulunamadı.")
    return chapter


@router.post("/toc", response_model=list[ChapterOut], status_code=status.HTTP_201_CREATED)
async def import_toc(
    payload: TocImport,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> list[Chapter]:
    # Mevcut 'pending' bölümleri temizle (Spec Bölüm 6.3)
    await db.execute(
        delete(Chapter).where(Chapter.project_id == project.id, Chapter.status == "pending")
    )
    created: list[Chapter] = []
    for item in payload.chapters:
        chapter = Chapter(
            project_id=project.id,
            order_index=item.order_index,
            title=item.title,
            description=item.description,
            target_word_count=item.target_word_count,
            status="pending",
        )
        db.add(chapter)
        created.append(chapter)
    await db.commit()
    for chapter in created:
        await db.refresh(chapter)
    created.sort(key=lambda c: c.order_index)
    return created


@router.post("/generate-all", response_model=GenerateAllResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_all(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> GenerateAllResponse:
    if project.status == "paused":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proje duraklatılmış.")
    rows = (
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.project_id == project.id, Chapter.status == "pending")
                .order_by(Chapter.order_index)
            )
        )
        .scalars()
        .all()
    )
    for chapter in rows:
        chapter.status = "queued"
    if rows:
        project.status = "generating"
    await db.commit()  # eager modda task'lar bundan SONRA çalışmalı (queued state'i görsün)
    for chapter in rows:
        generate_chapter_task.apply_async(
            args=[str(chapter.id)], queue="generation", countdown=chapter.order_index * 2
        )
    return GenerateAllResponse(queued=len(rows), message=f"{len(rows)} bölüm kuyruğa eklendi.")


@router.get("", response_model=list[ChapterOut])
async def list_chapters(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[Chapter]:
    stmt = select(Chapter).where(Chapter.project_id == project.id)
    if status_filter:
        stmt = stmt.where(Chapter.status == status_filter)
    rows = (await db.execute(stmt.order_by(Chapter.order_index))).scalars().all()
    return list(rows)


@router.get("/{chapter_id}", response_model=ChapterOut)
async def get_chapter(
    chapter_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> Chapter:
    return await _get_chapter(db, project, chapter_id)


@router.patch("/{chapter_id}", response_model=ChapterOut)
async def update_chapter(
    chapter_id: uuid.UUID,
    payload: ChapterUpdate,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> Chapter:
    chapter = await _get_chapter(db, project, chapter_id)
    data = payload.model_dump(exclude_unset=True)
    # İçerik değişiyorsa ESKİ içeriği user_edit olarak snapshot'la (Spec Bölüm 5.3)
    if "content" in data and chapter.content:
        snapshot_chapter(db, chapter, "user_edit")
    for key, value in data.items():
        setattr(chapter, key, value)
    if "content" in data:
        chapter.word_count = len((data["content"] or "").split())
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.post("/{chapter_id}/generate", response_model=GenerateResponse)
async def generate_chapter(
    chapter_id: uuid.UUID,
    payload: GenerateRequest,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    if project.status == "paused":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proje duraklatılmış.")
    chapter = await _get_chapter(db, project, chapter_id)
    if chapter.status == "generating":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bölüm zaten üretiliyor.")
    if chapter.status == "done" and not payload.force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bölüm zaten tamamlanmış; yeniden üretmek için force=true gönderin.",
        )
    # force=true ile 'done' yeniden üretiminde regenerate snapshot'ı Celery görevinde alınır.
    chapter.status = "queued"
    await db.commit()  # eager modda task bundan SONRA çalışmalı
    result = generate_chapter_task.apply_async(args=[str(chapter.id)], queue="generation")
    return GenerateResponse(
        chapter_id=chapter.id,
        celery_task_id=result.id,
        status="queued",
        message="Bölüm kuyruğa eklendi.",
    )


@router.get("/{chapter_id}/tasks", response_model=list[TaskLogOut])
async def chapter_tasks(
    chapter_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> list[TaskLog]:
    chapter = await _get_chapter(db, project, chapter_id)
    rows = (
        (await db.execute(select(TaskLog).where(TaskLog.chapter_id == chapter.id).order_by(TaskLog.id)))
        .scalars()
        .all()
    )
    return list(rows)
