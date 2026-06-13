"""Test altyapısı (Spec Bölüm 15).

- Şema GERÇEK Alembic migration'ı ile kurulur (view/trigger/HNSW dahil) → production ile birebir.
- Uygulama async test engine (NullPool) üzerinden get_db override ile çalışır.
- Her test sonunda tüm tablolar TRUNCATE edilir (uygulama commit ettiği için rollback yetmez).

NOT: Gerçek bir PostgreSQL (pgvector) gerektirir; kitap_test veritabanına bağlanır.
"""
import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.session import get_db
from app.main import app

ASYNC_TEST_URL = settings.TEST_DATABASE_URL
SYNC_TEST_URL = ASYNC_TEST_URL.replace("+asyncpg", "+psycopg2")

# Uygulama (async) — NullPool: bağlantı testler/loop'lar arasında paylaşılmaz
test_engine = create_async_engine(ASYNC_TEST_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# Şema kurulumu/temizliği (sync)
sync_engine = create_engine(SYNC_TEST_URL)

ALL_TABLES = (
    "users, refresh_tokens, projects, project_settings, chapters, "
    "chapter_versions, citations, media_assets, task_logs, export_jobs"
)


@pytest.fixture(scope="session", autouse=True)
def _setup_schema():
    # env.py bu ortam değişkenini settings.DATABASE_URL'e tercih eder
    os.environ["ALEMBIC_URL"] = SYNC_TEST_URL
    # Temiz başlangıç: şemayı sıfırla, sonra migration'ı uygula
    with sync_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")
    yield
    sync_engine.dispose()


@pytest.fixture(autouse=True)
def _truncate_after_test():
    yield
    with sync_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {ALL_TABLES} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client():
    async def _override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def set_user_plan():
    """Test yardımcı: bir kullanıcının planını doğrudan DB'de günceller."""

    def _set(email: str, plan: str) -> None:
        with sync_engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET plan = :plan WHERE email = :email"),
                {"plan": plan, "email": email},
            )

    return _set


@pytest.fixture
def sql_scalar():
    """Test yardımcı: ham SQL çalıştırıp tek bir değer döndürür (doğrudan DB doğrulaması)."""

    def _q(sql: str, **params):
        with sync_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    return _q
