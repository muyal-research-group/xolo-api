import time as T

from fastapi import Depends, Response, status
from fastapi.routing import APIRouter
from xolo.log import Log

import xoloapi.config as Cfg
from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.accounts.dependencies import get_accounts_service
from xoloapi.accounts.dto import CreateAccountDTO
from xoloapi.logging import build_log_payload
from xoloapi.middleware.admin import require_admin_token

router = APIRouter(prefix="/accounts", tags=["accounts"])
log = Log(
    name="accounts.controller",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)

@router.get("")
async def list_accounts(
    _: object = Depends(require_admin_token),
    service: AccountsService = Depends(get_accounts_service),
):
    t1 = T.time()
    result = await service.list_accounts()
    if result.is_err:
        error = result.unwrap_err()
        log.error(build_log_payload("accounts.list.error", started_at=t1, error=error))
        raise error.to_http_exception()
    accounts = result.unwrap()
    log.info(build_log_payload("accounts.list", started_at=t1, account_count=len(accounts)))
    return accounts


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(
    dto: CreateAccountDTO,
    _: object = Depends(require_admin_token),
    service: AccountsService = Depends(get_accounts_service),
):
    t1 = T.time()
    result = await service.create_account(dto)
    if result.is_err:
        error = result.unwrap_err()
        log.error(build_log_payload("accounts.create.error", started_at=t1, error=error, account_id=dto.account_id))
        raise error.to_http_exception()
    log.info(build_log_payload("accounts.create", started_at=t1, account_id=dto.account_id))
    return result.unwrap()


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: str,
    _: object = Depends(require_admin_token),
    service: AccountsService = Depends(get_accounts_service),
):
    t1 = T.time()
    result = await service.delete_account(account_id)
    if result.is_err:
        error = result.unwrap_err()
        log.error(build_log_payload("accounts.delete.error", started_at=t1, error=error, account_id=account_id))
        raise error.to_http_exception()
    log.info(build_log_payload("accounts.delete", started_at=t1, account_id=account_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
