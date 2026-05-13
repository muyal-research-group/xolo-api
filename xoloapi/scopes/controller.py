import time as T

from fastapi import Depends, Response, status
from fastapi.routing import APIRouter
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.accounts.dependencies import require_existing_account
import xoloapi.scopes.dto as DTO
from xoloapi.middleware.apikey import require_admin_or_api_key
from xoloapi.log.format import build_log_payload
from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.scopes.application.scopes_service import ScopesService
from xoloapi.scopes.infrastructure.mongo_repository import MongoScopesRepository

router = APIRouter(
    prefix="/accounts/{account_id}/scopes",
    dependencies=[Depends(require_existing_account)],
)
log = Log(
    name="scopes.controller",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def get_scopes_service() -> ScopesService:
    repository = MongoScopesRepository(
        collection=get_collection(CollectionNames.SCOPES_COLLECTION_NAME),
        scope_user_collection=get_collection(CollectionNames.SCOPE_USER_COLLECTION_NAME),
    )
    return ScopesService(
        repository=repository,
        licenses_repository=MongoLicensesRepository(
            collection=get_collection(CollectionNames.LICENSES_COLLECTION_NAME),
        ),
    )


@router.get("")
async def list_scopes(
    account_id: str,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    t1 = T.time()
    response = await scopes_service.list_scopes(account_id=account_id)
    if response.is_ok:
        log.info(build_log_payload("scopes.list", started_at=t1, scope_count=len(response.unwrap())))
        return response.unwrap()
    err = response.unwrap_err()
    log.error(build_log_payload("scopes.list.error", started_at=t1, error=err))
    raise err.to_http_exception()


@router.get("/assignments")
async def list_scope_assignments(
    account_id: str,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    t1 = T.time()
    response = await scopes_service.list_assignments(account_id=account_id)
    if response.is_ok:
        log.info(build_log_payload("scopes.assignments.list", started_at=t1, assignment_count=len(response.unwrap())))
        return response.unwrap()
    err = response.unwrap_err()
    log.error(build_log_payload("scopes.assignments.list.error", started_at=t1, error=err))
    raise err.to_http_exception()


@router.get("/list")
async def list_scopes_discovery(
    account_id: str,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    """List all scopes for data discovery (dropdowns/autocomplete). Same as GET / but clear intent."""
    t1 = T.time()
    response = await scopes_service.list_scopes(account_id=account_id)
    if response.is_ok:
        scopes = response.unwrap()
        log.info(build_log_payload("scopes.discovery.list", started_at=t1, scope_count=len(scopes)))
        return scopes
    err = response.unwrap_err()
    log.error(build_log_payload("scopes.discovery.list.error", started_at=t1, error=err))
    raise err.to_http_exception()


@router.post("")
async def create_scope(
    account_id: str,
    dto: DTO.CreateScopeDTO,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    t1 = T.time()
    response = await scopes_service.create(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(build_log_payload("scopes.create", started_at=t1, scope_name=dto.name))
        return response.unwrap()
    err = response.unwrap_err()
    log.error(build_log_payload("scopes.create.error", started_at=t1, error=err, scope_name=dto.name))
    raise err.to_http_exception()


@router.post("/assign")
async def assign_scope(
    account_id: str,
    dto: DTO.AssignScopeDTO,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    t1 = T.time()
    response = await scopes_service.assign(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(
            build_log_payload(
                "scopes.assign",
                started_at=t1,
                scope_name=dto.name,
                username=dto.username,
            )
        )
        return response.unwrap()
    err = response.unwrap_err()
    log.error(
        build_log_payload(
            "scopes.assign.error",
            started_at=t1,
            error=err,
            scope_name=dto.name,
            username=dto.username,
        )
    )
    raise err.to_http_exception()


@router.delete("/assign", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_scope(
    account_id: str,
    dto: DTO.AssignScopeDTO,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    t1 = T.time()
    response = await scopes_service.unassign(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(build_log_payload("scopes.unassign", started_at=t1, scope_name=dto.name, username=dto.username))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    err = response.unwrap_err()
    log.error(build_log_payload("scopes.unassign.error", started_at=t1, error=err, scope_name=dto.name, username=dto.username))
    raise err.to_http_exception()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scope(
    account_id: str,
    dto: DTO.CreateScopeDTO,
    _: object = Depends(require_admin_or_api_key("scopes")),
    scopes_service: ScopesService = Depends(get_scopes_service),
):
    t1 = T.time()
    response = await scopes_service.delete(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(build_log_payload("scopes.delete", started_at=t1, scope_name=dto.name))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    err = response.unwrap_err()
    log.error(build_log_payload("scopes.delete.error", started_at=t1, error=err, scope_name=dto.name))
    raise err.to_http_exception()
