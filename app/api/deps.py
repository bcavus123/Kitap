"""FastAPI bağımlılıkları: kimlik doğrulama (Bearer JWT veya X-API-Key)."""
import uuid

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, hash_api_key
from app.db.session import get_db
from app.models.models import Project, User


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulanamadı.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user: User | None = None

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            payload = decode_token(token)
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
    elif x_api_key:
        res = await db.execute(select(User).where(User.api_key_hash == hash_api_key(x_api_key)))
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
