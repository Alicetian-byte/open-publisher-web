"""FastAPI 认证依赖：Bearer Header、HttpOnly Cookie 与 SSE access_token。

令牌由 fastapi-users JWTStrategy 签发（标准 JWT）；迁移期兼容旧版自研
HMAC 令牌，便于存量登录态平滑过渡。
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.users import SyncUserDatabase, get_jwt_strategy, get_user_db, get_user_manager, UserManager
from app.db.session import get_db
from app.models.user import AppUser

COOKIE_NAME = "opw_access_token"


def _read_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    query_token = request.query_params.get("access_token")
    if query_token:
        return query_token.strip()
    return request.cookies.get(COOKIE_NAME)


async def _resolve_user(
    token: str,
    user_manager: UserManager,
    user_db: SyncUserDatabase,
) -> AppUser | None:
    """优先按 fastapi-users JWT 解析；失败时回退旧版自研令牌（迁移期）。"""
    strategy = get_jwt_strategy()
    user = await strategy.read_token(token, user_manager)
    if user is not None:
        return user
    try:
        payload = decode_access_token(token)
    except ValueError:
        return None
    return await user_db.get(str(payload.get("sub", "")))


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    user_manager: UserManager = Depends(get_user_manager),
    user_db: SyncUserDatabase = Depends(get_user_db),
) -> AppUser:
    token = _read_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    user = await _resolve_user(token, user_manager, user_db)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="登录状态已过期")
    return user


def require_user(user: AppUser = Depends(get_current_user)) -> AppUser:
    return user


def require_admin(user: AppUser = Depends(get_current_user)) -> AppUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user

