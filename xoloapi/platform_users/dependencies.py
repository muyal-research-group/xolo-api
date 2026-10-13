from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

import xoloapi.config as Cfg
from xoloapi.db import get_collection
from xoloapi.db.cache import get_redis_client
from xoloapi.db.constants import CollectionNames
from xoloapi.platform_users.application import PlatformUserService
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.value_objects import PlatformPermission
from xoloapi.platform_users.infrastructure.mongo_repository import MongoPlatformUserRepository
from xoloapi.platform_users.infrastructure.session_store import PlatformSessionStore


def get_platform_user_service() -> PlatformUserService:
    collection = get_collection(CollectionNames.PLATFORM_USERS_COLLECTION_NAME)
    if collection is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return PlatformUserService(MongoPlatformUserRepository(collection))


def get_platform_session_store() -> PlatformSessionStore:
    redis = get_redis_client()
    if redis is None:
        raise HTTPException(status_code=503, detail="Session store is unavailable")
    return PlatformSessionStore(redis, Cfg.XOLO_PLATFORM_SESSION_MAX_AGE)


async def get_platform_user(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias=Cfg.XOLO_PLATFORM_CSRF_COOKIE_NAME),
    service: PlatformUserService = Depends(get_platform_user_service),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
) -> PlatformUser:
    return await authorize_platform_request(
        request,
        session_token=session_token,
        csrf_token=csrf_token,
        csrf_cookie=csrf_cookie,
        service=service,
        sessions=sessions,
    )


async def authorize_platform_request(
    request: Request,
    *,
    session_token: str | None = None,
    csrf_token: str | None = None,
    csrf_cookie: str | None = None,
    service: PlatformUserService | None = None,
    sessions: PlatformSessionStore | None = None,
) -> PlatformUser:
    session_token = session_token or request.cookies.get(Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME)
    csrf_token = csrf_token or request.headers.get("X-CSRF-Token")
    csrf_cookie = csrf_cookie or request.cookies.get(Cfg.XOLO_PLATFORM_CSRF_COOKIE_NAME)
    service = service or get_platform_user_service()
    sessions = sessions or get_platform_session_store()
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Platform session required")
    session = await sessions.get(session_token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Platform session expired")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        expected = session["csrf_token"]
        if not csrf_token or not csrf_cookie:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token required")
        if not secrets.compare_digest(expected, csrf_token) or not secrets.compare_digest(expected, csrf_cookie):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    result = await service.get(session["user_id"])
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    user = result.unwrap()
    if not user.is_active:
        await sessions.delete(session_token)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform user is disabled")
    request.state.platform_user = user
    request.state.platform_session = session
    return user


def require_platform_permission(permission: PlatformPermission) -> Callable:
    async def dependency(request: Request, user: PlatformUser = Depends(get_platform_user)) -> PlatformUser:
        if user.must_change_password:
            raise HTTPException(status_code=403, detail="Password change required")
        account_id = request.path_params.get("account_id")
        if not user.can(permission, account_id):
            raise HTTPException(status_code=403, detail=f"Missing platform permission: {permission.value}")
        return user

    return dependency
