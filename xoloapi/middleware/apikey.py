from fastapi import Depends, Header, Request
from xolo.log import Log

import xoloapi.db as DbX
import xoloapi.config as Cfg
from xoloapi.apikeys.application.apikey_service import APIKeyService
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.infrastructure.mongo_repository import MongoAPIKeyRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.errors.base import AccessDeniedError
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def _get_apikey_service() -> APIKeyService:
    return APIKeyService(
        repository=MongoAPIKeyRepository(
            db              = DbX.get_database(),
            collection_name = CollectionNames.API_KEYS_COLLECTION_NAME,
        )
    )


def require_api_key(scope: str)->APIKey:
    """Factory that returns a FastAPI dependency for the given service scope.

    All errors are XoloException subclasses — just call .to_http_exception()
    which carries the correct HTTP status code (401 invalid key, 403 bad scope).

    Usage::

        @router.post("/foo")
        async def foo(
            api_key: APIKey  = Depends(require_api_key("acl")),
            me:      UserDTO = Depends(MX.get_current_user),
        ): ...
    """
    async def _dependency(
        request: Request,
        x_api_key: str           = Header(..., alias="X-API-Key"),
        service:   APIKeyService = Depends(_get_apikey_service),
    ) -> APIKey:
        account_id = request.path_params.get("account_id")
        result = await service.validate(raw_key=x_api_key, required_scope=scope)
        if result.is_err:
            error = result.unwrap_err()
            level = log.error if getattr(error, "status_code", 500) >= 500 else log.warning
            level(build_log_payload("middleware.apikey.validate.error", error=error, required_scope=scope))
            raise error.to_http_exception()

        api_key = result.unwrap()
        if account_id is not None and api_key.account_id != account_id:
            error = AccessDeniedError(
                "API key does not belong to the requested account",
                metadata={"account_id": account_id, "key_account_id": api_key.account_id},
            )
            log.warning(build_log_payload("middleware.apikey.account_mismatch", error=error, required_scope=scope, key_id=api_key.key_id, account_id=account_id))
            raise error.to_http_exception()
        log.debug(
            build_log_payload(
                "middleware.apikey.validate",
                required_scope=scope,
                key_id=api_key.key_id,
                key_name=api_key.name,
            )
        )
        return api_key

    return _dependency
