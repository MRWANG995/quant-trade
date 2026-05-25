from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.config import get_settings
from app.database import get_db
from app.models.entities import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None
    user_id = int(payload["sub"])
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="未登录或令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


_PUBLIC_API_PREFIXES = (
    "/api/auth",
    "/api/health",
    "/api/data/status",
)


async def require_auth_if_enabled(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
) -> None:
    settings = get_settings()
    if not settings.require_auth:
        return
    path = request.url.path.rstrip("/") or "/"
    for prefix in _PUBLIC_API_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="需要登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
