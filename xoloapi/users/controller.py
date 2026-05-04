import time as T
from typing import Annotated

from fastapi import Depends, Response, status
from fastapi.routing import APIRouter
from xolo.log import Log

import commonx.errors as EX

import xoloapi.config as Cfg
import xoloapi.middleware as MX
from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.logging import build_log_payload
from xoloapi.middleware.admin import require_admin_token
from xoloapi.middleware.apikey import require_api_key
from xoloapi.users.application.users_service import UsersService
from xoloapi.users.dependencies import get_users_service
import xoloapi.users.dto as DTO

router = APIRouter(
    prefix="/accounts/{account_id}/users",
    dependencies=[Depends(require_existing_account)],
)
log = Log(
    name="users.controller",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    account_id: str,
    user_dto: DTO.CreateUserDTO,
    _: object = Depends(require_admin_token),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.create_user(account_id=account_id, dto=user_dto)
    if response.is_ok:
        log.info(build_log_payload("users.create", started_at=t1, username=user_dto.username))
        return response.unwrap()
    error = response.unwrap_err()
    log.error(build_log_payload("users.create.error", started_at=t1, error=error, username=user_dto.username))
    raise error.to_http_exception()


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    account_id: str,
    user_dto: DTO.SignUpDTO,
    _: object = Depends(require_api_key("users")),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.signup(account_id=account_id, dto=user_dto)
    if response.is_ok:
        log.info(build_log_payload("users.signup", started_at=t1, username=user_dto.username))
        return response.unwrap()
    error = response.unwrap_err()
    log.error(build_log_payload("users.signup.error", started_at=t1, error=error, username=user_dto.username))
    raise error.to_http_exception()


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify(
    account_id: str,
    verify_dto: DTO.VerifyDTO,
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.verify(account_id=account_id, dto=verify_dto)
    if response.is_ok:
        log.info(build_log_payload("users.verify", started_at=t1, username=verify_dto.username))
        return Response(status_code=204)
    error = response.unwrap_err()
    log.error(build_log_payload("users.verify.error", started_at=t1, error=error, username=verify_dto.username))
    raise error.to_http_exception()


@router.post("/password-recovery", status_code=status.HTTP_204_NO_CONTENT)
async def request_password_recovery(
    account_id: str,
    dto: DTO.PasswordRecoveryRequestDTO,
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.request_password_recovery(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(build_log_payload("users.password_recovery.request", started_at=t1, identifier=dto.identifier))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    error = response.unwrap_err()
    log.error(build_log_payload("users.password_recovery.request.error", started_at=t1, error=error, identifier=dto.identifier))
    raise error.to_http_exception()


@router.post("/password-recovery/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_recovery(
    account_id: str,
    dto: DTO.PasswordRecoveryConfirmDTO,
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.confirm_password_recovery(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(build_log_payload("users.password_recovery.confirm", started_at=t1))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    error = response.unwrap_err()
    log.error(build_log_payload("users.password_recovery.confirm.error", started_at=t1, error=error))
    raise error.to_http_exception()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    account_id: str,
    dto: DTO.LogoutDTO,
    me: DTO.UserDTO = Depends(MX.get_current_user),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    if dto.username != me.username:
        log.error(
            build_log_payload(
                "users.logout.forbidden",
                started_at=t1,
                username=dto.username,
                actor_username=me.username,
            )
        )
        raise EX.AccessDenied(raw_detail="You can only logout from your own account.").to_http_exception()

    response = await users_service.logout(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(build_log_payload("users.logout", started_at=t1, username=dto.username, actor_username=me.username))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    error = response.unwrap_err()
    log.error(build_log_payload("users.logout.error", started_at=t1, error=error, username=dto.username, actor_username=me.username))
    raise error.to_http_exception()


@router.post("/auth")
async def auth(
    account_id: str,
    auth_dto: DTO.AuthDTO,
    _: object = Depends(require_api_key("users")),
    users_service: UsersService = Depends(get_users_service),
) -> DTO.AuthenticatedDTO:
    t1 = T.time()
    response = await users_service.auth(account_id=account_id, dto=auth_dto)
    if response.is_ok:
        log.info(build_log_payload("users.auth", started_at=t1, username=auth_dto.username, scope=auth_dto.scope))
        return response.unwrap()

    error = response.unwrap_err()
    log.error(build_log_payload("users.auth.error", started_at=t1, error=error, username=auth_dto.username, scope=auth_dto.scope))
    raise error.to_http_exception()


@router.get("")
async def me(account_id: str, current_user: Annotated[DTO.UserDTO, Depends(MX.get_current_user)]):
    t1 = T.time()
    log.info(build_log_payload("users.me", started_at=t1, user_id=current_user.key, username=current_user.username))
    return current_user


@router.get("/all")
async def list_users(
    account_id: str,
    _: object = Depends(require_admin_token),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.list_users(account_id=account_id)
    if response.is_ok:
        log.info(build_log_payload("users.list", started_at=t1, user_count=len(response.unwrap())))
        return response.unwrap()
    error = response.unwrap_err()
    log.error(build_log_payload("users.list.error", started_at=t1, error=error))
    raise error.to_http_exception()


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    account_id: str,
    username: str,
    _: object = Depends(require_admin_token),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.delete_user(account_id=account_id, username=username)
    if response.is_ok:
        log.info(build_log_payload("users.delete", started_at=t1, username=username))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    error = response.unwrap_err()
    log.error(build_log_payload("users.delete.error", started_at=t1, error=error, username=username))
    raise error.to_http_exception()


@router.post("/{username}/block", status_code=status.HTTP_204_NO_CONTENT)
async def block_user(
    account_id: str,
    username: str,
    _: object = Depends(require_admin_token),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.block_user(account_id=account_id, username=username)
    if response.is_ok:
        log.info(build_log_payload("users.block", started_at=t1, username=username))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    error = response.unwrap_err()
    log.error(build_log_payload("users.block.error", started_at=t1, error=error, username=username))
    raise error.to_http_exception()


@router.post("/{username}/unblock", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    account_id: str,
    username: str,
    _: object = Depends(require_admin_token),
    users_service: UsersService = Depends(get_users_service),
):
    t1 = T.time()
    response = await users_service.unblock_user(account_id=account_id, username=username)
    if response.is_ok:
        log.info(build_log_payload("users.unblock", started_at=t1, username=username))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    error = response.unwrap_err()
    log.error(build_log_payload("users.unblock.error", started_at=t1, error=error, username=username))
    raise error.to_http_exception()


@router.post("/{username}/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable_user(
    account_id: str,
    username: str,
    dto: DTO.EnableOrDisableUserDTO,
    users_service: UsersService = Depends(get_users_service),
    me: DTO.UserDTO = Depends(MX.__get_current_user),
):
    t1 = T.time()
    if me.username != dto.username:
        log.error(
            build_log_payload(
                "users.enable.forbidden",
                started_at=t1,
                actor_username=me.username,
                path_username=username,
                dto_username=dto.username,
            )
        )
        raise EX.AccessDenied(raw_detail="You can only enable your own user account.").to_http_exception()

    response = await users_service.enable_user(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(
            build_log_payload(
                "users.enable",
                started_at=t1,
                actor_username=me.username,
                path_username=username,
                dto_username=dto.username,
            )
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    error = response.unwrap_err()
    log.error(
        build_log_payload(
            "users.enable.error",
            started_at=t1,
            error=error,
            actor_username=me.username,
            path_username=username,
            dto_username=dto.username,
        )
    )
    raise error.to_http_exception()


@router.post("/{username}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    account_id: str,
    username: str,
    dto: DTO.EnableOrDisableUserDTO,
    users_service: UsersService = Depends(get_users_service),
    me: DTO.UserDTO = Depends(MX.get_current_user),
):
    t1 = T.time()
    if me.username != dto.username:
        log.error(
            build_log_payload(
                "users.disable.forbidden",
                started_at=t1,
                actor_username=me.username,
                path_username=username,
                dto_username=dto.username,
            )
        )
        raise EX.AccessDenied(raw_detail="You can only disable your own user account.").to_http_exception()

    response = await users_service.disable_user(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(
            build_log_payload(
                "users.disable",
                started_at=t1,
                actor_username=me.username,
                path_username=username,
                dto_username=dto.username,
            )
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    error = response.unwrap_err()
    log.error(
        build_log_payload(
            "users.disable.error",
            started_at=t1,
            error=error,
            actor_username=me.username,
            path_username=username,
            dto_username=dto.username,
        )
    )
    raise error.to_http_exception()
from xoloapi.middleware.apikey import require_api_key
