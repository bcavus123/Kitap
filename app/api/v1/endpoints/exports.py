"""Exports endpoint'leri: oluştur / listele / durum (Spec Bölüm 6.4)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_project
from app.core.limits import plan_limits
from app.db.session import get_db
from app.models.models import Chapter, ExportJob, Project, User
from app.schemas.schemas import ExportJobOut, ExportRequest
from app.tasks.export import export_project_task

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["exports"])

_PLAN_FEATURE = {"pdf": "pdf_export", "epub": "epub_export"}


@router.post("", response_model=ExportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    payload: ExportRequest,
    project: Project = Depends(get_owned_project),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportJob:
    # Plan kapısı: pdf/epub yalnızca pro/enterprise (Spec Bölüm 20)
    feature = _PLAN_FEATURE.get(payload.format)
    if feature and not plan_limits(user.plan).get(feature):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"'{payload.format}' export '{user.plan}' planında kullanılamaz.",
        )

    done = await db.scalar(
        select(func.count())
        .select_from(Chapter)
        .where(Chapter.project_id == project.id, Chapter.status == "done")
    )
    if not done:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Export için en az bir tamamlanmış bölüm gerekli.",
        )

    job = ExportJob(project_id=project.id, format=payload.format, status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    export_project_task.apply_async(args=[str(job.id)], queue="export")
    return job


@router.get("", response_model=list[ExportJobOut])
async def list_exports(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> list[ExportJob]:
    rows = (
        await db.execute(
            select(ExportJob)
            .where(ExportJob.project_id == project.id)
            .order_by(ExportJob.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


@router.get("/{job_id}", response_model=ExportJobOut)
async def get_export(
    job_id: uuid.UUID,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> ExportJob:
    job = await db.get(ExportJob, job_id)
    if job is None or job.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export işi bulunamadı.")
    return job
