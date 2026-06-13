"""SQLAlchemy ORM modelleri (10 tablo) — Spec Bölüm 5.1.

NOT: Şemanın tek doğruluk kaynağı Alembic migration'dır (Bölüm 5.5). Bu modeller
ORM erişimi içindir; gerçek DDL (trigger, view, HNSW index) migration'da ham SQL ile
oluşturulur. Modeller ile migration uyumlu tutulmalıdır.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Embedding boyutu — settings.EMBEDDING_DIMENSIONS ile aynı olmalı (Bölüm 4 / 10).
EMBEDDING_DIM = 1536


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), server_default="user")  # user | admin
    plan: Mapped[str] = mapped_column(String(20), server_default="free")  # free | pro | enterprise
    api_key_hash: Mapped[str | None] = mapped_column(String(255), unique=True)
    api_key_prefix: Mapped[str | None] = mapped_column(String(12))
    api_key_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    projects: Mapped[list["Project"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    genre: Mapped[str | None] = mapped_column(String(100))
    kdp_format: Mapped[str] = mapped_column(String(20), server_default="6x9")
    citation_style: Mapped[str] = mapped_column(String(20), server_default="APA")
    language: Mapped[str] = mapped_column(String(10), server_default="tr")
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    target_word_count: Mapped[int] = mapped_column(Integer, server_default=text("50000"))
    total_word_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    chapter_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="projects")
    settings: Mapped["ProjectSettings"] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    export_jobs: Mapped[list["ExportJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class ProjectSettings(Base):
    __tablename__ = "project_settings"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    tone_profile: Mapped[str] = mapped_column(String(50), server_default="academic")
    audience_level: Mapped[str] = mapped_column(String(50), server_default="graduate")
    academic_field: Mapped[str | None] = mapped_column(String(100))
    human_writing_mode: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    style_overrides: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    llm_config: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text(
            "'{\"model\":\"claude-sonnet-4-6\",\"temperature\":0.5,\"max_tokens\":8000}'::jsonb"
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="settings")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("project_id", "order_index", name="uq_chapters_project_order"),)

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    content_summary: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    word_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    target_word_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    retry_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="chapters")
    versions: Mapped[list["ChapterVersion"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", passive_deletes=True
    )
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", passive_deletes=True
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", passive_deletes=True
    )


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"
    __table_args__ = (
        UniqueConstraint("chapter_id", "version_number", name="uq_chversions_chapter_version"),
    )

    id: Mapped[uuid.UUID] = _pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(50), server_default="ai_generation")
    token_cost: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter: Mapped["Chapter"] = relationship(back_populates="versions")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = _pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    marker: Mapped[str] = mapped_column(String(20), nullable=False)
    doi: Mapped[str | None] = mapped_column(String(200))
    raw_title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[str | None] = mapped_column(Text)
    journal: Mapped[str | None] = mapped_column(String(300))
    pub_year: Mapped[int | None] = mapped_column(SmallInteger)
    publisher: Mapped[str | None] = mapped_column(String(300))
    citation_format: Mapped[str] = mapped_column(String(20), server_default="APA")
    formatted_text: Mapped[str | None] = mapped_column(Text)
    doi_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    verification_status: Mapped[str] = mapped_column(String(20), server_default="unverified")
    crossref_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter: Mapped["Chapter"] = relationship(back_populates="citations")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = _pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    s3_path: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    position_index: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    width_px: Mapped[int | None] = mapped_column(SmallInteger)
    height_px: Mapped[int | None] = mapped_column(SmallInteger)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    dpi: Mapped[int] = mapped_column(SmallInteger, server_default=text("300"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter: Mapped["Chapter"] = relationship(back_populates="media_assets")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[uuid.UUID] = _pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    celery_task_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    worker_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), server_default="queued")
    tokens_input: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tokens_output: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # docx | pdf | epub
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    s3_path: Mapped[str | None] = mapped_column(Text)
    presigned_url: Mapped[str | None] = mapped_column(Text)
    url_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="export_jobs")
