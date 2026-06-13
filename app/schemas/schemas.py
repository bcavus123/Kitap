"""Pydantic request/response şemaları (Spec Bölüm 14)."""
import uuid
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Enum benzeri kısıtlar
KdpFormat = Literal["5x8", "6x9", "7x10", "8.5x11"]
CitationStyle = Literal["APA", "Chicago", "MLA", "Vancouver", "Harvard"]
ToneProfile = Literal["academic", "formal", "narrative", "technical", "popular"]
AudienceLevel = Literal["undergraduate", "graduate", "expert", "general"]


# ===========================================================================
# Auth — İstek
# ===========================================================================
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    all_sessions: bool = False


# ===========================================================================
# Auth — Yanıt
# ===========================================================================
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    plan: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ApiKeyOut(BaseModel):
    api_key: str
    api_key_prefix: str
    created_at: datetime


class ApiKeyInfo(BaseModel):
    has_api_key: bool
    api_key_prefix: str | None = None
    created_at: datetime | None = None


# ===========================================================================
# Projects — İstek
# ===========================================================================
class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    genre: str | None = Field(default=None, max_length=100)
    kdp_format: KdpFormat = "6x9"
    citation_style: CitationStyle = "APA"
    language: str = Field(default="tr", max_length=10)
    target_word_count: int = Field(default=50000, ge=1)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    genre: str | None = Field(default=None, max_length=100)
    kdp_format: KdpFormat | None = None
    citation_style: CitationStyle | None = None
    language: str | None = Field(default=None, max_length=10)
    target_word_count: int | None = Field(default=None, ge=1)


class ProjectSettingsUpdate(BaseModel):
    tone_profile: ToneProfile | None = None
    audience_level: AudienceLevel | None = None
    academic_field: str | None = Field(default=None, max_length=100)
    human_writing_mode: bool | None = None
    style_overrides: dict[str, Any] | None = None
    llm_config: dict[str, Any] | None = None


# ===========================================================================
# Projects — Yanıt
# ===========================================================================
class ProjectSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    tone_profile: str
    audience_level: str
    academic_field: str | None
    human_writing_mode: bool
    style_overrides: dict[str, Any]
    llm_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    subtitle: str | None
    genre: str | None
    kdp_format: str
    citation_style: str
    language: str
    status: str
    target_word_count: int
    total_word_count: int
    chapter_count: int
    created_at: datetime
    updated_at: datetime
    settings: ProjectSettingsOut | None = None


class ProjectProgress(BaseModel):
    project_id: uuid.UUID
    title: str
    project_status: str
    chapter_count: int
    total_word_count: int
    target_word_count: int
    word_pct: float
    chapters_done: int
    chapters_generating: int
    chapters_error: int
    chapters_pending: int
    chapter_pct: float


# ===========================================================================
# Ortak
# ===========================================================================
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
