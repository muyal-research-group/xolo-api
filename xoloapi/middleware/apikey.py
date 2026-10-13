from fastapi import Depends, Header, Request, HTTPException, status
from xoloapi.log import Log

import xoloapi.db as DbX
import xoloapi.config as Cfg
from xoloapi.apikeys.application.apikey_service import APIKeyService
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.infrastructure.mongo_repository import MongoAPIKeyRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.errors.base import AccessDeniedError
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def _platform_permission_suffix(request: Request) -> str:
    """Classify non-mutating queries that use POST bodies as read operations."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return "READ"
    if request.method == "POST" and request.url.path.rsplit("/", 1)[-1] in {
        "check", "evaluate", "has-role",
    }:
        return "READ"
    return "MANAGE"


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
        x_api_key: str | None    = Header(None, alias="X-API-Key"),
        service:   APIKeyService = Depends(_get_apikey_service),
    ) -> APIKey | None:
        if request.cookies.get(Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME):
            from xoloapi.platform_users.dependencies import authorize_platform_request
            from xoloapi.platform_users.domain.value_objects import PlatformPermission

            area = scope.upper()
            suffix = _platform_permission_suffix(request)
            try:
                permission = PlatformPermission[f"{area}_{suffix}"]
            except KeyError:
                raise HTTPException(status_code=403, detail="Platform session cannot access this API scope")
            user = await authorize_platform_request(request)
            if user.must_change_password:
                raise HTTPException(status_code=403, detail="Password change required")
            account_id = request.path_params.get("account_id")
            if not user.can(permission, account_id):
                raise HTTPException(status_code=403, detail=f"Missing platform permission: {permission.value}")
            return None
        if not x_api_key:
            raise HTTPException(status_code=401, detail="X-API-Key or platform session required")
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


def require_service_api_key(scope: str):
    """Require an explicitly service-enabled account API key.

    SERVICE is checked separately from the route scope so legacy ALL keys do
    not gain service authority. The key must also belong to the account in the
    request path.
    """
    async def _dependency(
        request: Request,
        x_api_key: str = Header(..., alias="X-API-Key"),
        service: APIKeyService = Depends(_get_apikey_service),
    ) -> APIKey:
        result = await service.validate(raw_key=x_api_key, required_scope="service")
        if result.is_err:
            error = result.unwrap_err()
            level = log.error if getattr(error, "status_code", 500) >= 500 else log.warning
            level(build_log_payload("middleware.apikey.service_validate.error", error=error, required_scope=scope))
            raise error.to_http_exception()

        api_key = result.unwrap()
        if not api_key.allows(scope):
            error = AccessDeniedError(
                f"API key does not have required scope '{scope}'",
                metadata={"required_scope": scope, "key_id": api_key.key_id},
            )
            log.warning(build_log_payload("middleware.apikey.service_scope.error", error=error, required_scope=scope, key_id=api_key.key_id))
            raise error.to_http_exception()

        account_id = request.path_params.get("account_id")
        if account_id is not None and api_key.account_id != account_id:
            error = AccessDeniedError(
                "API key does not belong to the requested account",
                metadata={"account_id": account_id, "key_account_id": api_key.account_id},
            )
            log.warning(build_log_payload("middleware.apikey.service_account_mismatch", error=error, required_scope=scope, key_id=api_key.key_id, account_id=account_id))
            raise error.to_http_exception()

        log.info(build_log_payload("middleware.apikey.service_validate", required_scope=scope, key_id=api_key.key_id, account_id=account_id))
        return api_key

    return _dependency


def require_admin_or_api_key(scope: str):
    """Accept an emergency admin token, scoped API key, or platform session.
    
    Tries in order:
    1. Admin token (X-Admin-Token header)
    2. API key (X-API-Key header)
    3. Permissioned platform session cookie
    
    At least one must be valid.
    
    The API key is validated for the specified scope and account.
    
    Returns the API key if provided, otherwise ``None``.
    """
    async def _dependency(
        request: Request,
        x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
        x_api_key: str | None = Header(None, alias="X-API-Key"),
        service: APIKeyService = Depends(_get_apikey_service),
    ) -> APIKey | None:
        from xoloapi.middleware.admin import is_valid_admin_token
        
        # Try admin token first
        if x_admin_token and is_valid_admin_token(x_admin_token):
            log.debug(build_log_payload("middleware.admin_or_apikey.authorize_admin", required_scope=scope))
            return None  # Admin doesn't need API key info

        # Browser console sessions use explicit, account-scoped permissions.
        if request.cookies.get(Cfg.XOLO_PLATFORM_SESSION_COOKIE_NAME):
            from xoloapi.platform_users.dependencies import authorize_platform_request
            from xoloapi.platform_users.domain.value_objects import PlatformPermission

            area = {
                "scopes": "SCOPES",
                "licenses": "LICENSES",
                "users": "USERS",
                "acl": "ACL",
                "rbac": "RBAC",
                "abac": "ABAC",
                "ngac": "NGAC",
            }.get(scope)
            if area is None:
                raise HTTPException(status_code=403, detail="Platform session cannot access this API scope")
            suffix = _platform_permission_suffix(request)
            permission = PlatformPermission[f"{area}_{suffix}"]
            user = await authorize_platform_request(request)
            if user.must_change_password:
                raise HTTPException(status_code=403, detail="Password change required")
            account_id = request.path_params.get("account_id")
            if not user.can(permission, account_id):
                raise HTTPException(status_code=403, detail=f"Missing platform permission: {permission.value}")
            return None
        
        # Fall back to API key
        if x_api_key:
            account_id = request.path_params.get("account_id")
            result = await service.validate(raw_key=x_api_key, required_scope=scope)
            if result.is_err:
                error = result.unwrap_err()
                level = log.error if getattr(error, "status_code", 500) >= 500 else log.warning
                level(build_log_payload("middleware.admin_or_apikey.apikey_validate.error", error=error, required_scope=scope))
                raise error.to_http_exception()
            
            api_key = result.unwrap()
            if account_id is not None and api_key.account_id != account_id:
                error = AccessDeniedError(
                    "API key does not belong to the requested account",
                    metadata={"account_id": account_id, "key_account_id": api_key.account_id},
                )
                log.warning(build_log_payload("middleware.admin_or_apikey.account_mismatch", error=error, required_scope=scope, key_id=api_key.key_id, account_id=account_id))
                raise error.to_http_exception()
            
            log.debug(
                build_log_payload(
                    "middleware.admin_or_apikey.authorize_apikey",
                    required_scope=scope,
                    key_id=api_key.key_id,
                    key_name=api_key.name,
                )
            )
            return api_key
        
        # Neither provided
        log.warning(build_log_payload("middleware.admin_or_apikey.no_auth", required_scope=scope))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication (X-Admin-Token, X-API-Key header, or admin session required)",
            headers={"WWW-Authenticate": 'Bearer, AdminToken'},
        )
    
    return _dependency
