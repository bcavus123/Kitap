"""WebSocket endpoint — /api/v1/ws/projects/{project_id} (Spec Bölüm 6.5, 11).

Kimlik: token query parametresi (tarayıcılar WS handshake'inde header gönderemez).
Geçersiz token → 4401, proje sahibi değilse → 4403. Sonra Redis pub/sub dinleyici +
30 sn heartbeat paralel çalışır.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket
from jose import JWTError

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.models import Project
from app.services.realtime import project_channel

router = APIRouter(tags=["ws"])

WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403
HEARTBEAT_SECONDS = 30


def _user_id_from_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload.get("sub")


@router.websocket("/ws/projects/{project_id}")
async def ws_project(websocket: WebSocket, project_id: uuid.UUID) -> None:
    await websocket.accept()

    user_id = _user_id_from_token(websocket.query_params.get("token"))
    if user_id is None:
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, project_id)
    if project is None or str(project.user_id) != str(user_id):
        await websocket.close(code=WS_FORBIDDEN)
        return

    await _stream(websocket, project_id)


async def _stream(websocket: WebSocket, project_id: uuid.UUID) -> None:
    """Redis pub/sub dinleyici + heartbeat'i paralel çalıştırır (Spec Bölüm 11)."""
    client = aioredis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(project_channel(project_id))

    async def forward() -> None:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                data = message["data"]
                await websocket.send_text(data.decode() if isinstance(data, bytes) else data)

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await websocket.send_text(json.dumps({"event": "ping"}))

    forward_task = asyncio.create_task(forward())
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        await websocket.receive_text()  # istemci kapanışını bekle
    except Exception:  # noqa: BLE001
        pass
    finally:
        forward_task.cancel()
        heartbeat_task.cancel()
        try:
            await pubsub.unsubscribe(project_channel(project_id))
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
