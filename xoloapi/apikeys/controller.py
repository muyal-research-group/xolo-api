import time as T
from fastapi import APIRouter, Depends, Response, status
from xoloapi.log import Log
import xoloapi.config as Cfg
import xoloapi.db as DbX
from xoloapi.apikeys.application.apikey_service import APIKeyService
from xoloapi.apikeys.dto import (
    APIKeyMetadataDTO,
    CreateAPIKeyDTO,
    CreatedAPIKeyResponseDTO,
    RotatedAPIKeyResponseDTO,
)
from xoloapi.apikeys.infrastructure.mongo_repository import MongoAPIKeyRepository
from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.db.constants import CollectionNames
from xoloapi.log.format import build_log_payload
from xoloapi.middleware.admin import require_admin_token

log = Log(
    name                   = __name__,
    console_handler_filter = lambda x: True,
    interval               = Cfg.XOLO_LOG_INTERVAL,
    when                   = Cfg.XOLO_LOG_WHEN,
    path                   = Cfg.XOLO_LOG_PATH,
)

router = APIRouter(
    prefix="/accounts/{account_id}/apikeys",
    tags=["apikeys"],
    dependencies=[Depends(require_existing_account)],
)


def get_apikey_service() -> APIKeyService:
    return APIKeyService(
        repository=MongoAPIKeyRepository(
            db              = DbX.get_database(),
            collection_name = CollectionNames.API_KEYS_COLLECTION_NAME,
        )
    )


@router.post(
    "",
    status_code    = status.HTTP_201_CREATED,
    response_model = CreatedAPIKeyResponseDTO,
    summary        = "Create API key",
    description    = "Requires X-Admin-Token. The raw key is returned once and never stored.",
)
async def create_api_key(
    account_id: str,
    dto:     CreateAPIKeyDTO,
    _:       None          = Depends(require_admin_token),
    service: APIKeyService = Depends(get_apikey_service),
):
    t1     = T.time()
    result = await service.create(account_id=account_id, name=dto.name, scopes=dto.scopes, expires_at=dto.expires_at)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("apikeys.create.error", started_at=t1, error=err, key_name=dto.name, scopes=[scope.value for scope in dto.scopes]))
        raise err.to_http_exception()

    api_key, raw_key = result.unwrap()
    log.info(build_log_payload("apikeys.create", started_at=t1, key_id=api_key.key_id, key_name=api_key.name, scopes=[scope.value for scope in api_key.scopes]))
    return CreatedAPIKeyResponseDTO(
        account_id  = api_key.account_id,
        key_id     = api_key.key_id,
        key        = raw_key,
        key_prefix = api_key.key_prefix,
        name       = api_key.name,
        scopes     = api_key.scopes,
        expires_at = api_key.expires_at,
        created_at = api_key.created_at,
    )


@router.get(
    "",
    response_model = list[APIKeyMetadataDTO],
    summary        = "List API Keys",
    description    = "Requires X-Admin-Token. Never returns raw keys.",
)
async def list_api_keys(
    account_id: str,
    _:       None          = Depends(require_admin_token),
    service: APIKeyService = Depends(get_apikey_service),
):
    t1 = T.time()
    result = await service.list_keys_for_account(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("apikeys.list.error", started_at=t1, error=err))
        raise err.to_http_exception()
    keys = result.unwrap()
    log.info(build_log_payload("apikeys.list", started_at=t1, key_count=len(keys)))
    return [_to_metadata_dto(k) for k in keys]


@router.get(
    "/{key_id}",
    response_model = APIKeyMetadataDTO,
    summary        = "Get API key metadata",
)
async def get_api_key(
    account_id: str,
    key_id:  str,
    _:       None          = Depends(require_admin_token),
    service: APIKeyService = Depends(get_apikey_service),
):
    t1 = T.time()
    result = await service.get(key_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("apikeys.get.error", started_at=t1, error=err, key_id=key_id))
        raise err.to_http_exception()

    maybe = result.unwrap()
    if maybe.is_none:
        from xoloapi.errors.base import NotFoundError
        log.warning(build_log_payload("apikeys.get.error", started_at=t1, error=NotFoundError("APIKey", key_id), key_id=key_id))
        raise NotFoundError("APIKey", key_id).to_http_exception()
    if maybe.unwrap().account_id != account_id:
        from xoloapi.errors.base import NotFoundError
        raise NotFoundError("APIKey", key_id).to_http_exception()
    log.info(build_log_payload("apikeys.get", started_at=t1, key_id=key_id))
    return _to_metadata_dto(maybe.unwrap())


@router.delete(
    "/{key_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Revoke an API key",
)
async def revoke_api_key(
    account_id: str,
    key_id:  str,
    _:       None          = Depends(require_admin_token),
    service: APIKeyService = Depends(get_apikey_service),
):
    t1     = T.time()
    get_result = await service.get(key_id)
    if get_result.is_err:
        err = get_result.unwrap_err()
        log.error(build_log_payload("apikeys.revoke.error", started_at=t1, error=err, key_id=key_id, account_id=account_id))
        raise err.to_http_exception()
    maybe = get_result.unwrap()
    if maybe.is_none or maybe.unwrap().account_id != account_id:
        from xoloapi.errors.base import NotFoundError
        raise NotFoundError("APIKey", key_id).to_http_exception()
    result = await service.revoke(key_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("apikeys.revoke.error", started_at=t1, error=err, key_id=key_id))
        raise err.to_http_exception()
    log.info(build_log_payload("apikeys.revoke", started_at=t1, key_id=key_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{key_id}/rotate",
    response_model = RotatedAPIKeyResponseDTO,
    summary        = "Rotate an API key",
    description    = "Generates a new secret for the key, invalidating the old one. New key returned once.",
)
async def rotate_api_key(
    account_id: str,
    key_id:  str,
    _:       None          = Depends(require_admin_token),
    service: APIKeyService = Depends(get_apikey_service),
):
    t1     = T.time()
    get_result = await service.get(key_id)
    if get_result.is_err:
        err = get_result.unwrap_err()
        log.error(build_log_payload("apikeys.rotate.error", started_at=t1, error=err, key_id=key_id, account_id=account_id))
        raise err.to_http_exception()
    maybe = get_result.unwrap()
    if maybe.is_none or maybe.unwrap().account_id != account_id:
        from xoloapi.errors.base import NotFoundError
        raise NotFoundError("APIKey", key_id).to_http_exception()
    result = await service.rotate(key_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("apikeys.rotate.error", started_at=t1, error=err, key_id=key_id))
        raise err.to_http_exception()

    api_key, raw_key = result.unwrap()
    log.info(build_log_payload("apikeys.rotate", started_at=t1, key_id=key_id, key_prefix=api_key.key_prefix))
    return RotatedAPIKeyResponseDTO(
        account_id  = api_key.account_id,
        key_id     = api_key.key_id,
        key        = raw_key,
        key_prefix = api_key.key_prefix,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_metadata_dto(k) -> APIKeyMetadataDTO:
    return APIKeyMetadataDTO(
        account_id    = k.account_id,
        key_id       = k.key_id,
        key_prefix   = k.key_prefix,
        name         = k.name,
        scopes       = k.scopes,
        is_active    = k.is_active,
        created_at   = k.created_at,
        expires_at   = k.expires_at,
        last_used_at = k.last_used_at,
    )
