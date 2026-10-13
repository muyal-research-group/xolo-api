import hmac
from fastapi import Header, HTTPException, status, Request
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def is_valid_admin_token(token: str | None) -> bool:
    if not token:
        return False
    return any(
        hmac.compare_digest(token, configured_token)
        for configured_token in Cfg.XOLO_SUPER_ADMIN_TOKENS
    )


async def require_admin_token(
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> None:
    """FastAPI dependency that validates the X-Admin-Token header.

    Uses constant-time comparison for every configured admin token to prevent
    timing-oracle attacks. Raises 401 immediately on any mismatch.
    The token itself is never logged or returned.
    """
    if not is_valid_admin_token(x_admin_token):
        log.warning(build_log_payload("middleware.admin_token.validate.error"))
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Invalid or missing admin token",
            headers     = {"WWW-Authenticate": "AdminToken"},
        )
    log.debug(build_log_payload("middleware.admin_token.validate"))


def require_admin_or_platform(permission):
    """Allow an emergency admin token or a permissioned platform session."""
    async def dependency(
        request: Request,
        x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    ):
        if x_admin_token and is_valid_admin_token(x_admin_token):
            return None
        from xoloapi.platform_users.dependencies import authorize_platform_request

        user = await authorize_platform_request(request)
        if user.must_change_password:
            raise HTTPException(status_code=403, detail="Password change required")
        account_id = request.path_params.get("account_id")
        if not user.can(permission, account_id):
            raise HTTPException(status_code=403, detail=f"Missing platform permission: {permission.value}")
        return user

    return dependency
