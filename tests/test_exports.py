"""Exports endpoint testleri (Spec Bölüm 15, Aşama 7).

Eager Celery + mock LLM (conftest) → bölüm üretilir, sonra gerçek DOCX/PDF/EPUB derlenir.
PDF, CI'da WeasyPrint sistem kütüphaneleri ile (ci.yml apt-get) üretilir.
"""
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
PROJECTS = "/api/v1/projects"

TOC = {"chapters": [{"order_index": 1, "title": "Giriş"}]}


async def _auth(client, email: str, set_user_plan=None, plan: str | None = None) -> dict:
    await client.post(REGISTER, json={"email": email, "password": "sifre1234", "full_name": "Y"})
    if set_user_plan and plan:
        set_user_plan(email, plan)
    tok = (await client.post(LOGIN, json={"email": email, "password": "sifre1234"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def _project_with_done_chapter(client, headers: dict) -> str:
    pid = (await client.post(PROJECTS, headers=headers, json={"title": "Kitap"})).json()["id"]
    chapters = (await client.post(f"{PROJECTS}/{pid}/chapters/toc", headers=headers, json=TOC)).json()
    cid = chapters[0]["id"]
    # Eager generate → bölüm 'done' (mock içerik)
    await client.post(f"{PROJECTS}/{pid}/chapters/{cid}/generate", headers=headers, json={"force": False})
    return pid


async def _export_and_fetch(client, headers, pid, fmt):
    created = await client.post(f"{PROJECTS}/{pid}/exports", headers=headers, json={"format": fmt})
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]
    return await client.get(f"{PROJECTS}/{pid}/exports/{job_id}", headers=headers)


async def test_export_docx(client):
    h = await _auth(client, "exdocx@example.com")  # free → docx serbest
    pid = await _project_with_done_chapter(client, h)
    job = (await _export_and_fetch(client, h, pid, "docx")).json()
    assert job["status"] == "done"
    assert job["file_size_bytes"] > 0


async def test_export_requires_done_chapter(client):
    h = await _auth(client, "exnone@example.com")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "Bos"})).json()["id"]
    r = await client.post(f"{PROJECTS}/{pid}/exports", headers=h, json={"format": "docx"})
    assert r.status_code == 422


async def test_export_invalid_format(client):
    h = await _auth(client, "exinv@example.com")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "K"})).json()["id"]
    r = await client.post(f"{PROJECTS}/{pid}/exports", headers=h, json={"format": "xyz"})
    assert r.status_code == 422


async def test_export_pdf_free_plan(client):
    h = await _auth(client, "expdffree@example.com")  # free → pdf yasak
    pid = (await client.post(PROJECTS, headers=h, json={"title": "K"})).json()["id"]
    r = await client.post(f"{PROJECTS}/{pid}/exports", headers=h, json={"format": "pdf"})
    assert r.status_code == 402


async def test_export_pdf_pro(client, set_user_plan):
    h = await _auth(client, "expdfpro@example.com", set_user_plan, "pro")
    pid = await _project_with_done_chapter(client, h)
    job = (await _export_and_fetch(client, h, pid, "pdf")).json()
    assert job["status"] == "done"
    assert job["file_size_bytes"] > 0


async def test_export_epub_pro(client, set_user_plan):
    h = await _auth(client, "exepubpro@example.com", set_user_plan, "pro")
    pid = await _project_with_done_chapter(client, h)
    job = (await _export_and_fetch(client, h, pid, "epub")).json()
    assert job["status"] == "done"
    assert job["file_size_bytes"] > 0
