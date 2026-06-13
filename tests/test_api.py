"""Auth + system testleri (Spec Bölüm 15)."""

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
API_KEYS = "/api/v1/auth/api-keys"


def _user(email: str, password: str = "sifre1234", name: str = "Test Yazar") -> dict:
    return {"email": email, "password": password, "full_name": name}


async def _register_and_login(client, email: str) -> dict:
    await client.post(REGISTER, json=_user(email))
    res = await client.post(LOGIN, json={"email": email, "password": "sifre1234"})
    return res.json()


# --------------------------------------------------------------------------- #
# System
# --------------------------------------------------------------------------- #
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
async def test_register(client):
    r = await client.post(REGISTER, json=_user("kayit@example.com"))
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "kayit@example.com"
    assert "id" in body
    assert body["plan"] == "free"


async def test_register_duplicate_email(client):
    payload = _user("dup@example.com")
    await client.post(REGISTER, json=payload)
    r = await client.post(REGISTER, json=payload)
    assert r.status_code == 409


async def test_login(client):
    await client.post(REGISTER, json=_user("giris@example.com"))
    r = await client.post(LOGIN, json={"email": "giris@example.com", "password": "sifre1234"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == 900


async def test_login_wrong_password(client):
    await client.post(REGISTER, json=_user("yanlis@example.com"))
    r = await client.post(LOGIN, json={"email": "yanlis@example.com", "password": "hataliparola"})
    assert r.status_code == 401


async def test_refresh_token(client):
    tokens = await _register_and_login(client, "refresh@example.com")
    r = await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_refresh_after_logout(client):
    tokens = await _register_and_login(client, "logout@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    out = await client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]}, headers=headers)
    assert out.status_code == 200
    r = await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_api_key_create_and_auth(client, set_user_plan):
    await client.post(REGISTER, json=_user("apikey@example.com"))
    set_user_plan("apikey@example.com", "pro")
    tokens = (await client.post(LOGIN, json={"email": "apikey@example.com", "password": "sifre1234"})).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    created = await client.post(API_KEYS, headers=headers)
    assert created.status_code == 201
    api_key = created.json()["api_key"]
    assert api_key.startswith("kp_")

    # Üretilen anahtarla X-API-Key üzerinden kimlik doğrulama
    me = await client.get(ME, headers={"X-API-Key": api_key})
    assert me.status_code == 200
    assert me.json()["email"] == "apikey@example.com"


async def test_api_key_free_plan_forbidden(client):
    tokens = await _register_and_login(client, "freeplan@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = await client.post(API_KEYS, headers=headers)
    assert r.status_code == 402
