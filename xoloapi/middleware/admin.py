import hmac
from fastapi import Header, HTTPException, status, Request
from xoloapi.log import Log
from jwt import InvalidTokenError
import jwt

import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload

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


def _get_admin_ui_session(request: Request) -> dict | None:
    """Extract admin UI session from cookie."""
    cookie_name = Cfg.XOLO_ADMIN_UI_SESSION_COOKIE_NAME
    token = request.cookies.get(cookie_name)
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            Cfg.XOLO_ADMIN_UI_SESSION_SECRET,
            algorithms=[Cfg.XOLO_JWT_ALGORITHM],
        )
    except InvalidTokenError:
        return None
    if payload.get("sub") != "admin-ui":
        return None
    return payload


async def require_admin_session_or_token(
    request: Request,
    x_admin_token: str = Header(None, alias="X-Admin-Token"),
) -> None:
    """Allow either admin UI session cookie OR X-Admin-Token header."""
    # Try admin token first
    if x_admin_token and is_valid_admin_token(x_admin_token):
        log.debug(build_log_payload("middleware.admin_auth.token_valid"))
        return
    
    # Try session cookie
    session = _get_admin_ui_session(request)
    if session is not None:
        log.debug(build_log_payload("middleware.admin_auth.session_valid"))
        return
    
    # Both failed
    log.warning(build_log_payload("middleware.admin_auth.failed"))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing admin token/session",
        headers={"WWW-Authenticate": "AdminToken"},
    )

