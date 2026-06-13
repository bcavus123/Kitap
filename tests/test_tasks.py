"""Aşama 5: Celery görevi (eager) + WebSocket auth testleri.

CELERY_TASK_ALWAYS_EAGER=true (conftest) → generate_chapter_task broker/worker olmadan
senkron inline çalışır; böylece 9 adımlı akış CI'da uçtan uca doğrulanır.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
PROJECTS = "/api/v1/projects"

TOC = {"chapters": [{"order_index": 1, "title": "Giriş"}, {"order_index": 2, "title": "Sonuç"}]}


async def _auth(client, email: str) -> dict:
    await client.post(REGISTER, json={"email": email, "password": "sifre1234", "full_name": "Y"})
    tok = (await client.post(LOGIN, json={"email": email, "password": "sifre1234"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def _project_with_toc(client, headers: dict):
    pid = (await client.post(PROJECTS, headers=headers, json={"title": "K"})).json()["id"]
    chapters = (await client.post(f"{PROJECTS}/{pid}/chapters/toc", headers=headers, json=TOC)).json()
    return pid, chapters


async def test_generate_completes_chapter_eager(client):
    h = await _auth(client, "gentask@example.com")
    pid, chapters = await _project_with_toc(client, h)
    cid = chapters[0]["id"]

    r = await client.post(f"{PROJECTS}/{pid}/chapters/{cid}/generate", headers=h, json={"force": False})
    assert r.status_code == 200
    assert r.json()["celery_task_id"]

    # Eager task inline koştu → bölüm 'done', içerik dolu
    ch = (await client.get(f"{PROJECTS}/{pid}/chapters/{cid}", headers=h)).json()
    assert ch["status"] == "done"
    assert ch["content"]
    assert ch["word_count"] > 0

    # task_log 'success'
    tasks = (await client.get(f"{PROJECTS}/{pid}/chapters/{cid}/tasks", headers=h)).json()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "success"
    assert tasks[0]["tokens_output"] > 0


async def test_generate_all_completes_eager(client):
    h = await _auth(client, "genalltask@example.com")
    pid, _ = await _project_with_toc(client, h)

    r = await client.post(f"{PROJECTS}/{pid}/chapters/generate-all", headers=h)
    assert r.status_code == 202
    assert r.json()["queued"] == 2

    chapters = (await client.get(f"{PROJECTS}/{pid}/chapters", headers=h)).json()
    assert all(c["status"] == "done" for c in chapters)


async def test_generate_creates_ai_version(client, sql_scalar):
    h = await _auth(client, "genver@example.com")
    pid, chapters = await _project_with_toc(client, h)
    cid = chapters[0]["id"]

    await client.post(f"{PROJECTS}/{pid}/chapters/{cid}/generate", headers=h, json={"force": False})

    # 'done' geçişinde fn_snapshot_on_done trigger'ı ai_generation versiyonu oluşturmalı
    count = sql_scalar(
        "SELECT COUNT(*) FROM chapter_versions "
        "WHERE chapter_id = CAST(:cid AS uuid) AND change_reason = 'ai_generation'",
        cid=cid,
    )
    assert count == 1


async def test_generate_extracts_citations(client, sql_scalar):
    """Eager generate, içerikteki kaynakçadan Citation kaydı oluşturup doğrulamalı (Bölüm 9.4)."""
    h = await _auth(client, "cite@example.com")
    pid, chapters = await _project_with_toc(client, h)
    cid = chapters[0]["id"]
    await client.post(f"{PROJECTS}/{pid}/chapters/{cid}/generate", headers=h, json={"force": False})

    count = sql_scalar(
        "SELECT COUNT(*) FROM citations WHERE chapter_id = CAST(:cid AS uuid)", cid=cid
    )
    assert count == 1
    status = sql_scalar(
        "SELECT verification_status FROM citations WHERE chapter_id = CAST(:cid AS uuid) LIMIT 1",
        cid=cid,
    )
    assert status == "verified"


def test_ws_requires_token():
    """Token olmadan WS bağlantısı 4401 ile kapatılmalı (Spec Bölüm 6.5)."""
    test_client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with test_client.websocket_connect(f"/api/v1/ws/projects/{uuid.uuid4()}") as websocket:
            websocket.receive_text()
    assert exc_info.value.code == 4401
