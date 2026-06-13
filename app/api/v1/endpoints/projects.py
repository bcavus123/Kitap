"""Projects endpoint'leri: CRUD + settings + progress + pause/resume (Spec Bölüm 6.2)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.limits import get_limit
from app.db.session import get_db
from app.models.models import Project, ProjectSettings, User
from app.schemas.schemas import (
    PaginatedResponse,
    ProjectCreate,
    ProjectOut,
    ProjectProgress,
    ProjectSettingsOut,
    ProjectSettingsUpdate,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_owned_project(
    db: AsyncSession, project_id: uuid.UUID, user: User, *, with_settings: bool = False
) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    if with_settings:
        stmt = stmt.options(selectinload(Project.settings))
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proje bulunamadı.")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    # Plan kotası: aktif (done olmayan) proje sayısı
    limit = get_limit(user.plan, "max_active_projects")
    if limit is not None:
        active = await db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.user_id == user.id, Project.status != "done")
        )
        if active >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"'{user.plan}' planı aktif proje limitine ({limit}) ulaştı.",
            )

    project = Project(user_id=user.id, **payload.model_dump())
    db.add(project)
    await db.flush()
    db.add(ProjectSettings(project_id=project.id))  # 1-1 ayar kaydı (varsayılanlarla)
    await db.commit()
    return await _get_owned_project(db, project.id, user, with_settings=True)


@router.get("", response_model=PaginatedResponse[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> PaginatedResponse[ProjectOut]:
    base = select(Project).where(Project.user_id == user.id)
    if status_filter:
        base = base.where(Project.status == status_filter)

    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = (
        (
            await db.execute(
                base.options(selectinload(Project.settings))
                .order_by(Project.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse[ProjectOut](
        items=[ProjectOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    return await _get_owned_project(db, project_id, user, with_settings=True)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_owned_project(db, project_id, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await db.commit()
    return await _get_owned_project(db, project_id, user, with_settings=True)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _get_owned_project(db, project_id, user)
    await db.delete(project)
    await db.commit()


@router.get("/{project_id}/progress", response_model=ProjectProgress)
async def project_progress(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectProgress:
    await _get_owned_project(db, project_id, user)  # sahiplik + 404
    row = (
        await db.execute(
            text("SELECT * FROM v_project_progress WHERE project_id = :pid"),
            {"pid": project_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proje bulunamadı.")
    return ProjectProgress(**row)


@router.get("/{project_id}/settings", response_model=ProjectSettingsOut)
async def get_project_settings(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectSettings:
    project = await _get_owned_project(db, project_id, user, with_settings=True)
    if project.settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ayarlar bulunamadı.")
    return project.settings


@router.patch("/{project_id}/settings", response_model=ProjectSettingsOut)
async def update_project_settings(
    project_id: uuid.UUID,
    payload: ProjectSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectSettings:
    project = await _get_owned_project(db, project_id, user, with_settings=True)
    settings_row = project.settings
    if settings_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ayarlar bulunamadı.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings_row, key, value)
    await db.commit()
    await db.refresh(settings_row)
    return settings_row


@router.post("/{project_id}/pause", response_model=ProjectOut)
async def pause_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_owned_project(db, project_id, user)
    project.status = "paused"  # yeni bölüm kuyruğa alınmaz (Spec Bölüm 6.2)
    await db.commit()
    return await _get_owned_project(db, project_id, user, with_settings=True)


@router.post("/{project_id}/resume", response_model=ProjectOut)
async def resume_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_owned_project(db, project_id, user)
    if project.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Yalnızca duraklatılmış proje sürdürülebilir.",
        )
    # pending bölümlerin yeniden kuyruğa alınması Aşama 5'te (Celery) eklenecek.
    project.status = "generating"
    await db.commit()
    return await _get_owned_project(db, project_id, user, with_settings=True)
