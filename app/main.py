"""FastAPI uygulaması: lifespan, CORS, router kayıtları, sağlık uçları (Spec Bölüm 6.7)."""
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1.endpoints import admin, auth, chapters, exports, projects, ws
from app.core.config import settings
from app.core.observability import setup_observability
from app.db.session import async_engine

API_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_observability()
    yield
    await async_engine.dispose()


app = FastAPI(
    title="Kitap Yazma API",
    version="2.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Router kayıtları ----
app.include_router(auth.router, prefix=API_V1)
app.include_router(projects.router, prefix=API_V1)
app.include_router(chapters.router, prefix=API_V1)
app.include_router(exports.router, prefix=API_V1)
app.include_router(admin.router, prefix=API_V1)
app.include_router(ws.router, prefix=API_V1)

# Görsel test arayüzü (statik tek-dosya panel): /app/  (kök / oraya yönlenir)
app.mount("/app", StaticFiles(directory="app/web", html=True), name="web")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/app/")


# ---- Sağlık uçları ----
@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db", tags=["system"])
async def health_db() -> dict:
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"db down: {exc}"
        )
    return {"status": "ok", "db": "up"}


@app.get("/health/redis", tags=["system"])
async def health_redis() -> dict:
    try:
        async with aioredis.from_url(settings.REDIS_URL) as client:
            await client.ping()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"redis down: {exc}"
        )
    return {"status": "ok", "redis": "up"}
