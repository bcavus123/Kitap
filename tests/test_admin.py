"""Aşama 8: admin dead-letter uçları (role=admin) testleri."""
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
PROJECTS = "/api/v1/projects"
DEAD_LETTER = "/api/v1/admin/dead-letter"


async def _auth(client, email: str, set_user_role=None, role: str | None = None) -> dict:
    await client.post(REGISTER, json={"email": email, "password": "sifre1234", "full_name": "Y"})
    if set_user_role and role:
        set_user_role(email, role)
    tok = (await client.post(LOGIN, json={"email": email, "password": "sifre1234"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_dead_letter_requires_admin(client):
    h = await _auth(client, "normal@example.com")  # role=user
    r = await client.get(DEAD_LETTER, headers=h)
    assert r.status_code == 403


async def test_dead_letter_list_admin(client, set_user_role):
    h = await _auth(client, "admin1@example.com", set_user_role, "admin")
    r = await client.get(DEAD_LETTER, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0  # CI'da Redis yok → guarded boş liste
    assert body["items"] == []


async def test_requeue_admin(client, set_user_role):
    h = await _auth(client, "admin2@example.com", set_user_role, "admin")
    pid = (await client.post(PROJECTS, headers=h, json={"title": "K"})).json()["id"]
    chapters = (
        await client.post(
            f"{PROJECTS}/{pid}/chapters/toc",
            headers=h,
            json={"chapters": [{"order_index": 1, "title": "Giriş"}]},
        )
    ).json()
    cid = chapters[0]["id"]

    r = await client.post(f"{DEAD_LETTER}/{cid}/requeue", headers=h)
    assert r.status_code == 202
    assert r.json()["chapter_id"] == cid
    assert r.json()["celery_task_id"]
