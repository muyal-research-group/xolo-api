from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response, status

import xoloapi.config as Cfg
from xoloapi.errors.base import ConflictError
from xoloapi.platform_users.application import PlatformUserService
from xoloapi.platform_users.dependencies import (
    get_platform_session_store,
    get_platform_user,
    get_platform_user_service,
    require_platform_permission,
)
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole
from xoloapi.platform_users.dto import (
    PlatformLoginDTO,
    PlatformOptionsDTO,
    PlatformPasswordChangeDTO,
    PlatformPasswordResetDTO,
    PlatformSessionDTO,
    PlatformUserCreateDTO,
    PlatformUserDTO,
    PlatformUserUpdateDTO,
)
from xoloapi.platform_users.infrastructure.session_store import PlatformSessionStore


router = APIRouter(prefix="/platform", tags=["platform"])


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    common = {
        "max_age": Cfg.XOLO_PLATFORM_SESSION_MAX_AGE,
        "secure": Cfg.XOLO_PLATFORM_SESSION_SECURE,
        "samesite": "strict",
        "path": "/",
    }
    response.set_cookie(Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME, session_token, httponly=True, **common)
    response.set_cookie(Cfg.XOLO_PLATFORM_CSRF_COOKIE_NAME, csrf_token, httponly=False, **common)


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(Cfg.XOLO_PLATFORM_CSRF_COOKIE_NAME, path="/")


@router.post("/session", response_model=PlatformSessionDTO)
async def login(
    dto: PlatformLoginDTO,
    response: Response,
    service: PlatformUserService = Depends(get_platform_user_service),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
):
    result = await service.authenticate(dto.username, dto.password)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    user = result.unwrap()
    session_token, csrf_token = await sessions.create(user.user_id)
    _set_session_cookies(response, session_token, csrf_token)
    return PlatformSessionDTO(user=PlatformUserDTO.from_domain(user), csrf_token=csrf_token)


@router.get("/session", response_model=PlatformUserDTO)
async def current_session(user: PlatformUser = Depends(get_platform_user)):
    return PlatformUserDTO.from_domain(user)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME),
    _: PlatformUser = Depends(get_platform_user),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
):
    if session_token:
        await sessions.delete(session_token)
    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.put("/password", response_model=PlatformUserDTO)
async def change_password(
    dto: PlatformPasswordChangeDTO,
    user: PlatformUser = Depends(get_platform_user),
    service: PlatformUserService = Depends(get_platform_user_service),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
):
    result = await service.change_password(user.user_id, dto.current_password, dto.new_password)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    await sessions.delete_user_sessions(user.user_id)
    return PlatformUserDTO.from_domain(result.unwrap())


@router.get("/options", response_model=PlatformOptionsDTO)
async def options(_: PlatformUser = Depends(get_platform_user)):
    return PlatformOptionsDTO(roles=list(PlatformRole), permissions=list(PlatformPermission))


@router.get("/users", response_model=list[PlatformUserDTO])
async def list_platform_users(
    _: PlatformUser = Depends(require_platform_permission(PlatformPermission.PLATFORM_USERS_READ)),
    service: PlatformUserService = Depends(get_platform_user_service),
):
    result = await service.list_users()
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return [PlatformUserDTO.from_domain(user) for user in result.unwrap()]


@router.post("/users", response_model=PlatformUserDTO, status_code=status.HTTP_201_CREATED)
async def create_platform_user(
    dto: PlatformUserCreateDTO,
    _: PlatformUser = Depends(require_platform_permission(PlatformPermission.PLATFORM_USERS_MANAGE)),
    service: PlatformUserService = Depends(get_platform_user_service),
):
    result = await service.create(
        dto.username, dto.password, dto.role, dto.permissions, dto.allowed_account_ids,
        must_change_password=dto.must_change_password,
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return PlatformUserDTO.from_domain(result.unwrap())


@router.patch("/users/{user_id}", response_model=PlatformUserDTO)
async def update_platform_user(
    user_id: str,
    dto: PlatformUserUpdateDTO,
    _: PlatformUser = Depends(require_platform_permission(PlatformPermission.PLATFORM_USERS_MANAGE)),
    service: PlatformUserService = Depends(get_platform_user_service),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
):
    result = await service.update(
        user_id, role=dto.role, permissions=dto.permissions,
        allowed_account_ids=dto.allowed_account_ids, is_active=dto.is_active,
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    await sessions.delete_user_sessions(user_id)
    return PlatformUserDTO.from_domain(result.unwrap())


@router.put("/users/{user_id}/password", response_model=PlatformUserDTO)
async def reset_platform_password(
    user_id: str,
    dto: PlatformPasswordResetDTO,
    _: PlatformUser = Depends(require_platform_permission(PlatformPermission.PLATFORM_USERS_MANAGE)),
    service: PlatformUserService = Depends(get_platform_user_service),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
):
    result = await service.reset_password(user_id, dto.password)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    await sessions.delete_user_sessions(user_id)
    return PlatformUserDTO.from_domain(result.unwrap())


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_user(
    user_id: str,
    actor: PlatformUser = Depends(require_platform_permission(PlatformPermission.PLATFORM_USERS_MANAGE)),
    service: PlatformUserService = Depends(get_platform_user_service),
    sessions: PlatformSessionStore = Depends(get_platform_session_store),
):
    if actor.user_id == user_id:
        raise ConflictError("A platform user cannot delete their own account").to_http_exception()
    result = await service.delete(user_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    await sessions.delete_user_sessions(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
