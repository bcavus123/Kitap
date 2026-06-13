"""Projects endpoint testleri (Spec Bölüm 15, Aşama 3)."""
import uuid

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
PROJECTS = "/api/v1/projects"


def _user(email: str, name: str = "Yazar") -> dict:
    return {"email": email, "password": "sifre1234", "full_name": name}


async def _auth(client, email: str, set_user_plan=None, plan: str | None = None) -> dict:
    await client.post(REGISTER, json=_user(email))
    if set_user_plan and plan:
        set_user_plan(email, plan)
    tok = (await client.post(LOGIN, json={"email": email, "password": "sifre1234"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_project_requires_auth(client):
    r = await client.get(PROJECTS)
    assert r.status_code == 401


async def test_create_project(client):
    h = await _auth(client, "pc@example.com")
    r = await client.post(PROJECTS, headers=h, json={"title": "Test Kitap", "target_word_count": 60000})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["title"] == "Test Kitap"
    assert body["settings"] is not None
    assert body["settings"]["tone_profile"] == "academic"


async def test_project_not_found(client):
    h = await _auth(client, "pnf@example.com")
    r = await client.get(f"{PROJECTS}/{uuid.uuid4()}", headers=h)
    assert r.status_code == 404


async def test_free_plan_project_limit(client):
    h = await _auth(client, "plim@example.com")  # free: max_active_projects = 1
    assert (await client.post(PROJECTS, headers=h, json={"title": "K1"})).status_code == 201
    r2 = await client.post(PROJECTS, headers=h, json={"title": "K2"})
    assert r2.status_code == 402


async def test_list_projects(client, set_user_plan):
    h = await _auth(client, "plist@example.com", set_user_plan, "enterprise")
    await client.post(PROJECTS, headers=h, json={"title": "K1"})
    await client.post(PROJECTS, headers=h, json={"title": "K2"})
    r = await client.get(PROJECTS, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["page"] == 1


async def test_update_project(client):
    h = await _auth(client, "pupd@example.com")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "Eski"})).json()["id"]
    r = await client.patch(f"{PROJECTS}/{pid}", headers=h, json={"title": "Yeni", "genre": "Bilim"})
    assert r.status_code == 200
    assert r.json()["title"] == "Yeni"
    assert r.json()["genre"] == "Bilim"


async def test_update_project_settings(client):
    h = await _auth(client, "pset@example.com")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "K"})).json()["id"]
    r = await client.patch(
        f"{PROJECTS}/{pid}/settings",
        headers=h,
        json={"tone_profile": "technical", "audience_level": "expert", "academic_field": "Bilgisayar"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tone_profile"] == "technical"
    assert body["audience_level"] == "expert"
    assert body["academic_field"] == "Bilgisayar"


async def test_project_progress(client):
    h = await _auth(client, "pprog@example.com")
    pid = (
        await client.post(PROJECTS, headers=h, json={"title": "K", "target_word_count": 10000})
    ).json()["id"]
    r = await client.get(f"{PROJECTS}/{pid}/progress", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "word_pct" in body
    assert "chapter_pct" in body
    assert body["chapter_count"] == 0
    assert body["chapters_done"] == 0


async def test_pause_resume(client):
    h = await _auth(client, "ppr@example.com")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "K"})).json()["id"]
    paused = await client.post(f"{PROJECTS}/{pid}/pause", headers=h)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    resumed = await client.post(f"{PROJECTS}/{pid}/resume", headers=h)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "generating"


async def test_resume_non_paused_conflict(client):
    h = await _auth(client, "prc@example.com")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "K"})).json()["id"]
    r = await client.post(f"{PROJECTS}/{pid}/resume", headers=h)  # draft → 409
    assert r.status_code == 409
