"""Auth endpoint'leri: register, login, refresh, logout, me, api-keys (Spec Bölüm 6.1)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limits import require_plan
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.models import RefreshToken, User
from app.schemas.schemas import (
    AccessTokenResponse,
    ApiKeyInfo,
    ApiKeyOut,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _access_expires_in() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def _issue_token_pair(
    db: AsyncSession, user: User, user_agent: str | None = None
) -> TokenResponse:
    access = create_access_token(str(user.id))
    refresh, jti, expires_at = create_refresh_token(str(user.id))
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at, user_agent=user_agent))
    await db.commit()
    return TokenResponse(
        access_token=access, refresh_token=refresh, expires_in=_access_expires_in()
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kayıtlı.")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya parola hatalı."
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hesap pasif.")
    user.last_login_at = datetime.now(timezone.utc)
    return await _issue_token_pair(db, user)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> AccessTokenResponse:
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz refresh token.")
    try:
        data = decode_token(payload.refresh_token)
    except JWTError:
        raise invalid
    if data.get("type") != "refresh":
        raise invalid

    res = await db.execute(select(RefreshToken).where(RefreshToken.jti == data.get("jti")))
    token_row = res.scalar_one_or_none()
    if token_row is None or token_row.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token iptal edilmiş."
        )

    access = create_access_token(str(data["sub"]))
    return AccessTokenResponse(access_token=access, expires_in=_access_expires_in())


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    now = datetime.now(timezone.utc)
    if payload.all_sessions:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked.is_(False))
            .values(revoked=True, revoked_at=now)
        )
    elif payload.refresh_token:
        try:
            jti = decode_token(payload.refresh_token).get("jti")
        except JWTError:
            jti = None
        if jti:
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.jti == jti)
                .values(revoked=True, revoked_at=now)
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token veya all_sessions gerekli.",
        )
    await db.commit()
    return {"detail": "Çıkış yapıldı."}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/api-keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    current_user: User = Depends(require_plan("api_key")),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyOut:
    full, prefix, key_hash = generate_api_key()
    current_user.api_key_hash = key_hash
    current_user.api_key_prefix = prefix
    current_user.api_key_created_at = datetime.now(timezone.utc)
    await db.commit()
    return ApiKeyOut(api_key=full, api_key_prefix=prefix, created_at=current_user.api_key_created_at)


@router.get("/api-keys", response_model=ApiKeyInfo)
async def get_api_key_info(current_user: User = Depends(get_current_user)) -> ApiKeyInfo:
    return ApiKeyInfo(
        has_api_key=current_user.api_key_hash is not None,
        api_key_prefix=current_user.api_key_prefix,
        created_at=current_user.api_key_created_at,
    )


@router.delete("/api-keys", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    current_user.api_key_hash = None
    current_user.api_key_prefix = None
    current_user.api_key_created_at = None
    await db.commit()
