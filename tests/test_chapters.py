"""Chapters endpoint testleri (Spec Bölüm 15, Aşama 4)."""
import uuid

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
PROJECTS = "/api/v1/projects"

TOC = {
    "chapters": [
        {"order_index": 1, "title": "Giriş", "description": "Kapsam ve amaç"},
        {"order_index": 2, "title": "Temel Kavramlar", "target_word_count": 8000},
        {"order_index": 3, "title": "Sonuç"},
    ]
}


def _user(email: str) -> dict:
    return {"email": email, "password": "sifre1234", "full_name": "Yazar"}


async def _auth(client, email: str) -> dict:
    await client.post(REGISTER, json=_user(email))
    tok = (await client.post(LOGIN, json={"email": email, "password": "sifre1234"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def _project(client, headers: dict, title: str = "Kitap") -> str:
    return (await client.post(PROJECTS, headers=headers, json={"title": title})).json()["id"]


def _ch(pid: str, suffix: str = "") -> str:
    return f"{PROJECTS}/{pid}/chapters{suffix}"


async def test_import_toc(client):
    h = await _auth(client, "toc@example.com")
    pid = await _project(client, h)
    r = await client.post(_ch(pid, "/toc"), headers=h, json=TOC)
    assert r.status_code == 201
    body = r.json()
    assert len(body) == 3
    assert all(c["status"] == "pending" for c in body)
    assert [c["order_index"] for c in body] == [1, 2, 3]


async def test_toc_duplicate_order_index(client):
    h = await _auth(client, "tocdup@example.com")
    pid = await _project(client, h)
    bad = {"chapters": [{"order_index": 1, "title": "A"}, {"order_index": 1, "title": "B"}]}
    r = await client.post(_ch(pid, "/toc"), headers=h, json=bad)
    assert r.status_code == 422


async def test_list_chapters(client):
    h = await _auth(client, "chlist@example.com")
    pid = await _project(client, h)
    await client.post(_ch(pid, "/toc"), headers=h, json=TOC)
    r = await client.get(_ch(pid), headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 3


async def test_chapter_not_found(client):
    h = await _auth(client, "chnf@example.com")
    pid = await _project(client, h)
    r = await client.get(_ch(pid, f"/{uuid.uuid4()}"), headers=h)
    assert r.status_code == 404


async def test_patch_content_creates_version(client, sql_scalar):
    h = await _auth(client, "chpatch@example.com")
    pid = await _project(client, h)
    chapters = (await client.post(_ch(pid, "/toc"), headers=h, json=TOC)).json()
    cid = chapters[0]["id"]

    # İlk içerik: önceki içerik yok → versiyon OLUŞMAZ
    r1 = await client.patch(_ch(pid, f"/{cid}"), headers=h, json={"content": "İlk sürüm metni."})
    assert r1.status_code == 200
    assert r1.json()["word_count"] == 3

    # İkinci içerik: önceki içerik var → user_edit versiyonu OLUŞUR
    r2 = await client.patch(_ch(pid, f"/{cid}"), headers=h, json={"content": "İkinci sürüm güncellenmiş metin."})
    assert r2.status_code == 200

    count = sql_scalar(
        "SELECT COUNT(*) FROM chapter_versions "
        "WHERE chapter_id = CAST(:cid AS uuid) AND change_reason = 'user_edit'",
        cid=cid,
    )
    assert count == 1


async def test_generate_done_without_force(client, sql_scalar):
    h = await _auth(client, "chgen@example.com")
    pid = await _project(client, h)
    chapters = (await client.post(_ch(pid, "/toc"), headers=h, json=TOC)).json()
    cid = chapters[0]["id"]
    # Bölümü doğrudan 'done' yap
    sql_scalar(
        "UPDATE chapters SET status='done', content='x' WHERE id = CAST(:cid AS uuid) RETURNING 1",
        cid=cid,
    )
    r = await client.post(_ch(pid, f"/{cid}/generate"), headers=h, json={"force": False})
    assert r.status_code == 409


async def test_generate_queues_chapter(client):
    h = await _auth(client, "chgenq@example.com")
    pid = await _project(client, h)
    chapters = (await client.post(_ch(pid, "/toc"), headers=h, json=TOC)).json()
    cid = chapters[0]["id"]
    r = await client.post(_ch(pid, f"/{cid}/generate"), headers=h, json={"force": False})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert body["celery_task_id"]

    tasks = await client.get(_ch(pid, f"/{cid}/tasks"), headers=h)
    assert tasks.status_code == 200
    assert len(tasks.json()) == 1


async def test_generate_all_queues_pending(client):
    h = await _auth(client, "genall@example.com")
    pid = await _project(client, h)
    await client.post(_ch(pid, "/toc"), headers=h, json=TOC)
    r = await client.post(_ch(pid, "/generate-all"), headers=h)
    assert r.status_code == 202
    assert r.json()["queued"] == 3


async def test_pause_blocks_generate(client):
    h = await _auth(client, "chpause@example.com")
    pid = await _project(client, h)
    chapters = (await client.post(_ch(pid, "/toc"), headers=h, json=TOC)).json()
    cid = chapters[0]["id"]
    await client.post(f"{PROJECTS}/{pid}/pause", headers=h)
    r = await client.post(_ch(pid, f"/{cid}/generate"), headers=h, json={"force": False})
    assert r.status_code == 409
