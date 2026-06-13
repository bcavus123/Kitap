"""Güvenlik yardımcıları: parola hashleme, JWT, API anahtarı (Spec Bölüm 6.1)."""
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import settings

API_KEY_PREFIX = "kp_"


# ---------------------------------------------------------------------------
# Parola — bcrypt + 72-byte sınırı için SHA-256 ön-özet (Bölüm 6.1)
# ---------------------------------------------------------------------------
def _prehash(password: str) -> bytes:
    """Parolayı sabit 44 byte'a indirir; bcrypt'in 72-byte sınırını güvenle aşar."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str) -> str:
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(subject), "type": "access", "exp": expire, "iat": _now()}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """(token, jti, expires_at) döndürür. jti refresh_tokens tablosunda saklanır."""
    jti = uuid.uuid4().hex
    expire = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "type": "refresh", "jti": jti, "exp": expire, "iat": _now()}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti, expire


def decode_token(token: str) -> dict:
    """Token'ı çözer ve doğrular. Geçersizse jose.JWTError fırlatır."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ---------------------------------------------------------------------------
# API anahtarı — yüksek entropili olduğundan SHA-256 ile hashlenir (hızlı arama)
# ---------------------------------------------------------------------------
def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """(full_key, prefix, hash) döndürür. full_key yalnızca üretimde gösterilir."""
    full = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    prefix = full[:12]
    return full, prefix, hash_api_key(full)
