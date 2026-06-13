"""Veritabanı oturum yönetimi.

- FastAPI (async): asyncpg + AsyncSession + get_db
- Celery worker (sync): psycopg2 + Session + get_sync_db   (Spec Bölüm 19)
"""
from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# Async — FastAPI istek-yanıt döngüsü
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: istek başına bir AsyncSession."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Sync — Celery worker'lar (senkron çalışır)
# ---------------------------------------------------------------------------
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


@contextmanager
def get_sync_db() -> Iterator[Session]:
    """Celery görevleri için senkron oturum (psycopg2)."""
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
