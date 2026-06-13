"""FastAPI bağımlılıkları: kimlik doğrulama (Bearer JWT veya X-API-Key).

Güvenlik şemaları (HTTPBearer + APIKeyHeader) OpenAPI'ye yansır → Swagger UI'da
"Authorize" düğmesi görünür ve token'lı uçlar "Try it out" ile test edilebilir.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, hash_api_key
from app.db.session import get_db
from app.models.models import Project, User

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    api_key: str | None = Depends(_api_key_scheme),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulanamadı.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user: User | None = None

    if credentials and credentials.scheme.lower() == "bearer":
        try:
            payload = decode_token(credentials.credentials)
        except JWTError:
            raise credentials_exc
        if payload.get("type") != "access":
            raise credentials_exc
        sub = payload.get("sub")
        if not sub:
            raise credentials_exc
        try:
            user_id = uuid.UUID(str(sub))
        except (ValueError, TypeError):
            raise credentials_exc
        user = await db.get(User, user_id)
    elif api_key:
        res = await db.execute(select(User).where(User.api_key_hash == hash_api_key(api_key)))
        user = res.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exc
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Yönetici yetkisi gerekli."
        )
    return current_user


async def get_owned_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Path'teki project_id'yi getirir ve kullanıcının sahipliğini doğrular (404 IDOR koruması)."""
    project = await db.get(Project, project_id)
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proje bulunamadı.")
    return project
