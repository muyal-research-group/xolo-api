from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time as T
from urllib.parse import quote

import jwt
from jwt import InvalidTokenError
from pydantic import ValidationError
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from xolo.log import Log

import xoloapi.abac.dto as ABACDTO
import xoloapi.accounts.dto as AccountsDTO
import xoloapi.apikeys.dto as APIKeyDTO
import xoloapi.config as Cfg
import xoloapi.licenses.dto as LicenseDTO
import xoloapi.ngac.dto as NGACDTO
import xoloapi.rbac.dto as RBACDTO
import xoloapi.scopes.dto as ScopeDTO
import xoloapi.users.dto as UserDTO
from xoloapi.abac.application.abac_service import ABACService
from xoloapi.abac.controller import get_abac_service
from xoloapi.abac.domain.value_objects import Effect as ABACEffect
from xoloapi.acl.application.acl_service import ACLService
from xoloapi.acl.application.group_service import GroupService
from xoloapi.acl.controller import get_acl_service, get_group_service
from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.accounts.controller import get_accounts_service
from xoloapi.acl.domain.value_objects import PrincipalType as ACLPrincipalType
from xoloapi.apikeys.controller import get_apikey_service
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.licenses.controller import get_licenses_service
from xoloapi.logging import build_log_payload
from xoloapi.middleware.admin import is_valid_admin_token
from xoloapi.ngac.application.ngac_service import NGACService
from xoloapi.ngac.controller import get_ngac_service
from xoloapi.ngac.domain.value_objects import NodeType
from xoloapi.rbac.application.rbac_service import RBACService
from xoloapi.rbac.controller import get_rbac_service
from xoloapi.scopes.controller import get_scopes_service
from xoloapi.users.dependencies import get_users_service

router = APIRouter(prefix="/admin", tags=["admin-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
ADMIN_UI_ACTOR_ID = "admin-ui"
log = Log(
    name="admin_ui.controller",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def _cookie_name() -> str:
    return Cfg.XOLO_ADMIN_UI_SESSION_COOKIE_NAME


def _get_cookie_path(request: Request) -> str:
    """Get cookie path respecting root_path configuration."""
    return request.scope.get("root_path") or "/"


def _cookie_secure() -> bool:
    return Cfg.XOLO_ADMIN_UI_SESSION_SECURE


def _create_admin_session_token(*, active_account_id: str = "") -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": "admin-ui",
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=Cfg.XOLO_ADMIN_UI_SESSION_MAX_AGE),
    }
    if active_account_id:
        payload["account_id"] = active_account_id
    return jwt.encode(
        payload,
        Cfg.XOLO_ADMIN_UI_SESSION_SECRET,
        algorithm=Cfg.XOLO_JWT_ALGORITHM,
    )


def _get_admin_session(request: Request) -> dict | None:
    token = request.cookies.get(_cookie_name())
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


def _redirect_to_login(request: Request, *, clear_cookie: bool = False) -> RedirectResponse:
    response = RedirectResponse(
        url=request.url_for("admin_login"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    if clear_cookie:
        response.delete_cookie(
            _cookie_name(),
            path=_get_cookie_path(request),
            secure=_cookie_secure(),
            httponly=True,
            samesite="lax",
        )
    return response


def _ensure_admin_session(request: Request) -> dict | RedirectResponse:
    session = _get_admin_session(request)
    if session is None:
        return _redirect_to_login(
            request,
            clear_cookie=bool(request.cookies.get(_cookie_name())),
        )
    return session


def _set_admin_session_cookie(response, request: Request, *, active_account_id: str = "") -> None:
    response.set_cookie(
        key=_cookie_name(),
        value=_create_admin_session_token(active_account_id=active_account_id),
        max_age=Cfg.XOLO_ADMIN_UI_SESSION_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path=_get_cookie_path(request),
    )


def _render(
    request: Request,
    template_name: str,
    *,
    status_code: int = status.HTTP_200_OK,
    **context,
) -> HTMLResponse:
    current_account_id = str(context.get("current_account_id", "")).strip()
    context.setdefault("current_account_id", current_account_id)
    context.setdefault(
        "current_account_query",
        f"?account_id={quote(current_account_id)}" if current_account_id else "",
    )
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
    )


def _parse_optional_datetime(raw_value: str) -> datetime | None:
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))


def _parse_csv_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _admin_actor(raw_value: str | None = None) -> str:
    if raw_value is None:
        return ADMIN_UI_ACTOR_ID
    normalized = raw_value.strip()
    return normalized or ADMIN_UI_ACTOR_ID


def _parse_json_object(raw_value: str) -> dict[str, str]:
    raw_value = raw_value.strip()
    if not raw_value:
        return {}
    parsed = json.loads(raw_value)
    if not isinstance(parsed, dict):
        raise ValueError("Properties must be a JSON object.")
    return {str(key): str(value) for key, value in parsed.items()}


def _build_abac_policy_dto(
    *,
    name: str,
    effect: str,
    subject: str,
    resource: str,
    location: str,
    time_start: str,
    time_end: str,
    action: str,
) -> ABACDTO.CreateABACPolicyDTO:
    return ABACDTO.CreateABACPolicyDTO(
        name=name.strip(),
        effect=ABACEffect(effect.strip().upper()),
        events=[
            ABACDTO.CreateABACEventDTO(
                subject=subject.strip(),
                resource=resource.strip(),
                location=location.strip() or "*",
                time_start=time_start.strip() or None,
                time_end=time_end.strip() or None,
                action=action.strip(),
            )
        ],
    )


async def _accounts_metadata(accounts_service: AccountsService):
    result = await accounts_service.list_accounts()
    if result.is_err:
        return [], result.unwrap_err()
    return result.unwrap(), None


async def _validate_account_selection(
    accounts_service: AccountsService,
    account_id: str,
    *,
    required: bool = False,
) -> tuple[str, str | None]:
    normalized = account_id.strip()
    if not normalized:
        if required:
            return "", "Select an account from the admin panel first."
        return "", None

    result = await accounts_service.get_account(normalized)
    if result.is_err:
        return normalized, _error_message(result.unwrap_err())
    return normalized, None


def _selected_account_id(session: dict) -> str:
    return str(session.get("account_id", "")).strip()


async def _active_account_selection(
    accounts_service: AccountsService,
    session: dict,
    *,
    required: bool = False,
) -> tuple[str, str | None]:
    return await _validate_account_selection(
        accounts_service,
        _selected_account_id(session),
        required=required,
    )


def _error_message(error) -> str:
    return getattr(getattr(error, "detail", None), "msg", str(error))


async def _apikey_metadata(service, account_id: str):
    result = await service.list_keys_for_account(account_id)
    if result.is_err:
        return [], result.unwrap_err()
    return result.unwrap(), None


async def _scope_metadata(scopes_service, account_id: str):
    scopes_result = await scopes_service.list_scopes(account_id=account_id)
    assignments_result = await scopes_service.list_assignments(account_id=account_id)
    if scopes_result.is_err:
        return [], [], scopes_result.unwrap_err()
    if assignments_result.is_err:
        return [], [], assignments_result.unwrap_err()
    return scopes_result.unwrap(), assignments_result.unwrap(), None


async def _users_metadata(users_service, account_id: str):
    result = await users_service.list_users(account_id=account_id)
    if result.is_err:
        return [], result.unwrap_err()
    return result.unwrap(), None


async def _licenses_metadata(licenses_service, account_id: str):
    result = await licenses_service.list_licenses(account_id=account_id)
    if result.is_err:
        return [], result.unwrap_err()
    return result.unwrap(), None


async def _scope_assignments_metadata(scopes_service, account_id: str):
    result = await scopes_service.list_assignments(account_id=account_id)
    if result.is_err:
        return [], result.unwrap_err()
    return result.unwrap(), None


async def _acl_metadata(acl_service: ACLService, group_service: GroupService, account_id: str):
    policies_result = await acl_service.list_policies(account_id)
    groups_result = await group_service.list_groups(account_id)
    if policies_result.is_err:
        return [], [], policies_result.unwrap_err()
    if groups_result.is_err:
        return [], [], groups_result.unwrap_err()

    group_rows = []
    for group in groups_result.unwrap():
        members_result = await group_service.list_members(account_id, group.group_id)
        if members_result.is_err:
            return [], [], members_result.unwrap_err()
        group_rows.append({"group": group, "members": members_result.unwrap()})

    return policies_result.unwrap(), group_rows, None


async def _rbac_metadata(rbac_service: RBACService, account_id: str):
    roles_result = await rbac_service.list_roles(account_id)
    assignments_result = await rbac_service.list_assignments(account_id)
    if roles_result.is_err:
        return [], [], roles_result.unwrap_err()
    if assignments_result.is_err:
        return [], [], assignments_result.unwrap_err()
    return roles_result.unwrap(), assignments_result.unwrap(), None


async def _abac_metadata(abac_service: ABACService, account_id: str):
    result = await abac_service.list_policies(account_id)
    if result.is_err:
        return [], result.unwrap_err()
    return result.unwrap(), None


async def _ngac_metadata(ngac_service: NGACService, account_id: str):
    nodes_result = await ngac_service.list_nodes(account_id)
    assignments_result = await ngac_service.list_assignments(account_id)
    associations_result = await ngac_service.list_associations(account_id)
    if nodes_result.is_err:
        return [], [], [], nodes_result.unwrap_err()
    if assignments_result.is_err:
        return [], [], [], assignments_result.unwrap_err()
    if associations_result.is_err:
        return [], [], [], associations_result.unwrap_err()
    return nodes_result.unwrap(), assignments_result.unwrap(), associations_result.unwrap(), None


@router.get("/login", response_class=HTMLResponse, name="admin_login")
async def login_page(request: Request):
    if _get_admin_session(request) is not None:
        return RedirectResponse(
            url=request.url_for("admin_dashboard"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _render(
        request,
        "login.html",
        page_title="Admin login",
        authenticated=False,
        error_message=None,
        success_message=None,
    )


@router.post("/login", response_class=HTMLResponse, name="admin_login_submit")
async def login(
    request: Request,
    admin_token: str = Form(...),
):
    t1 = T.time()
    if not is_valid_admin_token(admin_token):
        log.warning(build_log_payload("admin_ui.login.error", started_at=t1))
        return _render(
            request,
            "login.html",
            page_title="Admin login",
            authenticated=False,
            error_message="Invalid admin token.",
            success_message=None,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(
        url=request.url_for("admin_dashboard"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_admin_session_cookie(response, request)
    log.info(build_log_payload("admin_ui.login", started_at=t1))
    return response


@router.post("/logout", name="admin_logout")
async def logout(request: Request):
    t1 = T.time()
    response = _redirect_to_login(request, clear_cookie=True)
    log.info(build_log_payload("admin_ui.logout", started_at=t1))
    return response


@router.get("", response_class=HTMLResponse, name="admin_dashboard")
async def dashboard(
    request: Request,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, account_error = await _active_account_selection(accounts_service, session)
    log.info(build_log_payload("admin_ui.dashboard", started_at=t1))
    return _render(
        request,
        "dashboard.html",
        page_title="Admin panel",
        authenticated=True,
        error_message=account_error,
        success_message=None,
        current_account_id=current_account_id,
    )


@router.post("/account", response_class=HTMLResponse, name="admin_select_account")
async def select_account(
    request: Request,
    account_id: str = Form(...),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _validate_account_selection(
        accounts_service,
        account_id,
        required=True,
    )
    success_message = None
    response = _render(
        request,
        "dashboard.html",
        page_title="Admin panel",
        authenticated=True,
        error_message=error_message,
        success_message=None,
        current_account_id=current_account_id if error_message is None else _selected_account_id(session),
    )
    if error_message is None:
        _set_admin_session_cookie(response, request, active_account_id=current_account_id)
        success_message = f"Active account set to '{current_account_id}'."
        response = _render(
            request,
            "dashboard.html",
            page_title="Admin panel",
            authenticated=True,
            error_message=None,
            success_message=success_message,
            current_account_id=current_account_id,
        )
        _set_admin_session_cookie(response, request, active_account_id=current_account_id)
        log.info(build_log_payload("admin_ui.account.select", started_at=t1, account_id=current_account_id))
        return response

    log.warning(build_log_payload("admin_ui.account.select.error", started_at=t1, account_id=current_account_id))
    return response


@router.post("/account/clear", response_class=HTMLResponse, name="admin_clear_account")
async def clear_account(
    request: Request,
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    response = _render(
        request,
        "dashboard.html",
        page_title="Admin panel",
        authenticated=True,
        error_message=None,
        success_message="Active account cleared.",
        current_account_id="",
    )
    _set_admin_session_cookie(response, request)
    log.info(build_log_payload("admin_ui.account.clear", started_at=t1, previous_account_id=_selected_account_id(session) or None))
    return response


@router.get("/accounts", response_class=HTMLResponse, name="admin_accounts_page")
async def accounts_page(
    request: Request,
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id = _selected_account_id(session)
    accounts, load_error = await _accounts_metadata(accounts_service)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.accounts.view.error", started_at=t1, error=load_error))
    else:
        log.info(build_log_payload("admin_ui.accounts.view", started_at=t1, account_count=len(accounts)))
    return _render(
        request,
        "accounts.html",
        page_title="Accounts",
        authenticated=True,
        error_message=None if load_error is None else _error_message(load_error),
        success_message=None,
        accounts=accounts,
        current_account_id=current_account_id,
    )


@router.post("/accounts", response_class=HTMLResponse, name="admin_create_account")
async def create_account(
    request: Request,
    account_id: str = Form(...),
    name: str = Form(...),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id = _selected_account_id(session)
    error_message = None
    success_message = None
    try:
        dto = AccountsDTO.CreateAccountDTO(account_id=account_id.strip(), name=name.strip())
        result = await accounts_service.create_account(dto)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.accounts.create.error", started_at=t1, error=error, account_id=dto.account_id))
        else:
            success_message = f"Account '{dto.account_id}' created."
            log.info(build_log_payload("admin_ui.accounts.create", started_at=t1, account_id=dto.account_id))
    except ValidationError as error:
        error_message = str(error)
        log.warning(build_log_payload("admin_ui.accounts.create.error", started_at=t1, error=error, account_id=account_id.strip()))

    accounts, load_error = await _accounts_metadata(accounts_service)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "accounts.html",
        page_title="Accounts",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        accounts=accounts,
        current_account_id=current_account_id,
    )


@router.post("/accounts/delete", response_class=HTMLResponse, name="admin_delete_account")
async def delete_account(
    request: Request,
    account_id: str = Form(...),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    selected_account_id = _selected_account_id(session)
    result = await accounts_service.delete_account(account_id.strip())
    error_message = None
    success_message = None
    if result.is_err:
        error = result.unwrap_err()
        error_message = _error_message(error)
        log.error(build_log_payload("admin_ui.accounts.delete.error", started_at=t1, error=error, account_id=account_id.strip()))
    else:
        success_message = f"Account '{account_id.strip()}' deleted."
        log.info(build_log_payload("admin_ui.accounts.delete", started_at=t1, account_id=account_id.strip()))

    accounts, load_error = await _accounts_metadata(accounts_service)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    response = _render(
        request,
        "accounts.html",
        page_title="Accounts",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        accounts=accounts,
        current_account_id="" if account_id.strip() == selected_account_id and result.is_ok else selected_account_id,
    )
    if account_id.strip() == selected_account_id and result.is_ok:
        _set_admin_session_cookie(response, request)
    return response


@router.get("/apikeys", response_class=HTMLResponse, name="admin_apikeys_page")
async def apikeys_page(
    request: Request,
    service=Depends(get_apikey_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    keys = []
    load_error = None
    if current_account_id and error_message is None:
        keys, load_error = await _apikey_metadata(service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.apikeys.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.apikeys.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.apikeys.view", started_at=t1, account_id=current_account_id or None, key_count=len(keys)))
    return _render(
        request,
        "apikeys.html",
        page_title="API Keys",
        authenticated=True,
        available_scopes=list(APIKeyScope),
        keys=keys,
        error_message=error_message if error_message is not None else (None if load_error is None else "Unable to load API key metadata."),
        success_message=None,
        created_key=None,
        current_account_id=current_account_id,
    )


@router.post("/apikeys/delete", response_class=HTMLResponse, name="admin_delete_apikey")
async def delete_apikey(
    request: Request,
    key_id: str = Form(...),
    service=Depends(get_apikey_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None

    if error_message is None:
        get_result = await service.get(key_id.strip())
        if get_result.is_err:
            error = get_result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.apikeys.delete.error", started_at=t1, error=error, key_id=key_id.strip(), account_id=current_account_id))
        else:
            maybe_key = get_result.unwrap()
            if maybe_key.is_none or maybe_key.unwrap().account_id != current_account_id:
                error_message = f"API key '{key_id.strip()}' was not found in account '{current_account_id}'."
                log.warning(build_log_payload("admin_ui.apikeys.delete.error", started_at=t1, key_id=key_id.strip(), account_id=current_account_id))
            else:
                result = await service.delete(key_id.strip())
                if result.is_err:
                    error = result.unwrap_err()
                    error_message = _error_message(error)
                    log.error(build_log_payload("admin_ui.apikeys.delete.error", started_at=t1, error=error, key_id=key_id.strip(), account_id=current_account_id))
                else:
                    success_message = f"API key '{key_id.strip()}' deleted."
                    log.info(build_log_payload("admin_ui.apikeys.delete", started_at=t1, key_id=key_id.strip(), account_id=current_account_id))

    keys = []
    load_error = None
    if current_account_id and error_message is None:
        keys, load_error = await _apikey_metadata(service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = "Unable to load API key metadata."
    return _render(
        request,
        "apikeys.html",
        page_title="API Keys",
        authenticated=True,
        available_scopes=list(APIKeyScope),
        keys=keys,
        error_message=error_message,
        success_message=success_message,
        created_key=None,
        current_account_id=current_account_id,
    )


@router.post("/apikeys", response_class=HTMLResponse, name="admin_create_apikey")
async def create_apikey(
    request: Request,
    name: str = Form(...),
    scopes: list[str] = Form(...),
    expires_at: str = Form(""),
    service=Depends(get_apikey_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    created_key = None
    success_message = None

    if error_message is None:
        try:
            parsed_scopes = [APIKeyScope(scope) for scope in scopes]
            dto = APIKeyDTO.CreateAPIKeyDTO(
                name=name.strip(),
                scopes=parsed_scopes,
                expires_at=_parse_optional_datetime(expires_at),
            )
            result = await service.create(
                account_id=current_account_id,
                name=dto.name,
                scopes=dto.scopes,
                expires_at=dto.expires_at,
            )
            if result.is_err:
                error = result.unwrap_err()
                error_message = getattr(getattr(error, "detail", None), "msg", str(error))
                log.error(build_log_payload("admin_ui.apikeys.create.error", started_at=t1, error=error, account_id=current_account_id, key_name=dto.name, scopes=scopes))
            else:
                api_key, raw_key = result.unwrap()
                created_key = {
                    "account_id": api_key.account_id,
                    "key_id": api_key.key_id,
                    "name": api_key.name,
                    "key": raw_key,
                    "key_prefix": api_key.key_prefix,
                    "scopes": [scope.value for scope in api_key.scopes],
                    "expires_at": api_key.expires_at,
                }
                success_message = "API key created. Store the raw key now; it will not be shown again."
                log.info(build_log_payload("admin_ui.apikeys.create", started_at=t1, account_id=current_account_id, key_id=api_key.key_id, key_name=api_key.name, scopes=[scope.value for scope in api_key.scopes]))
        except (ValueError, ValidationError) as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.apikeys.create.error", started_at=t1, error=error, account_id=current_account_id, key_name=name.strip()))

    keys = []
    load_error = None
    if current_account_id and error_message is None:
        keys, load_error = await _apikey_metadata(service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = "Unable to load API key metadata."
    return _render(
        request,
        "apikeys.html",
        page_title="API Keys",
        authenticated=True,
        available_scopes=list(APIKeyScope),
        keys=keys,
        error_message=error_message,
        success_message=success_message,
        created_key=created_key,
        current_account_id=current_account_id,
    )


@router.get("/scopes", response_class=HTMLResponse, name="admin_scopes_page")
async def scopes_page(
    request: Request,
    scopes_service=Depends(get_scopes_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    scopes = []
    load_error = None
    if current_account_id and error_message is None:
        scopes, _, load_error = await _scope_metadata(scopes_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.scopes.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.scopes.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.scopes.view", started_at=t1, account_id=current_account_id or None, scope_count=len(scopes)))
    return _render(
        request,
        "scopes.html",
        page_title="Scopes",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        scopes=scopes,
        current_account_id=current_account_id,
    )


@router.post("/scopes", response_class=HTMLResponse, name="admin_create_scope")
async def create_scope(
    request: Request,
    name: str = Form(...),
    scopes_service=Depends(get_scopes_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    scopes = []
    if error_message is None:
        try:
            dto = ScopeDTO.CreateScopeDTO(name=name.strip())
            result = await scopes_service.create(account_id=current_account_id, dto=dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.scopes.create.error", started_at=t1, error=error, account_id=current_account_id, scope_name=dto.name))
            else:
                success_message = f"Scope '{dto.name}' created."
                log.info(build_log_payload("admin_ui.scopes.create", started_at=t1, account_id=current_account_id, scope_name=dto.name))
        except ValidationError as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.scopes.create.error", started_at=t1, error=error, account_id=current_account_id, scope_name=name.strip()))
    load_error = None
    if current_account_id and error_message is None:
        scopes, _, load_error = await _scope_metadata(scopes_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "scopes.html",
        page_title="Scopes",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        scopes=scopes,
        current_account_id=current_account_id,
    )

@router.get("/scopes/assignments", response_class=HTMLResponse, name="admin_scope_assignments_page")
async def scope_assignments_page(
    request: Request,
    scopes_service=Depends(get_scopes_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        assignments, load_error = await _scope_assignments_metadata(scopes_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.scope_assignments.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.scope_assignments.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.scope_assignments.view", started_at=t1, account_id=current_account_id or None, assignment_count=len(assignments)))
    return _render(
        request,
        "scope_assignments.html",
        page_title="Scope assignments",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/scopes/assign", response_class=HTMLResponse, name="admin_assign_scope")
async def assign_scope(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    scopes_service=Depends(get_scopes_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    assignments = []
    if error_message is None:
        try:
            dto = ScopeDTO.AssignScopeDTO(name=name.strip(), username=username.strip())
            result = await scopes_service.assign(account_id=current_account_id, dto=dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.scopes.assign.error", started_at=t1, error=error, account_id=current_account_id, scope_name=dto.name, username=dto.username))
            else:
                success_message = f"Scope '{dto.name}' assigned to '{dto.username}'."
                log.info(build_log_payload("admin_ui.scopes.assign", started_at=t1, account_id=current_account_id, scope_name=dto.name, username=dto.username))
        except ValidationError as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.scopes.assign.error", started_at=t1, error=error, account_id=current_account_id, scope_name=name.strip(), username=username.strip()))
    load_error = None
    if current_account_id and error_message is None:
        assignments, load_error = await _scope_assignments_metadata(scopes_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "scope_assignments.html",
        page_title="Scope assignments",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/scopes/delete", response_class=HTMLResponse, name="admin_delete_scope")
async def delete_scope(
    request: Request,
    name: str = Form(...),
    scopes_service=Depends(get_scopes_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    dto = ScopeDTO.CreateScopeDTO(name=name.strip())
    if error_message is None:
        result = await scopes_service.delete(account_id=current_account_id, dto=dto)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.scopes.delete.error", started_at=t1, error=error, account_id=current_account_id, scope_name=dto.name))
        else:
            success_message = f"Scope '{dto.name}' deleted."
            log.info(build_log_payload("admin_ui.scopes.delete", started_at=t1, account_id=current_account_id, scope_name=dto.name))
    scopes = []
    load_error = None
    if current_account_id and error_message is None:
        scopes, _, load_error = await _scope_metadata(scopes_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "scopes.html",
        page_title="Scopes",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        scopes=scopes,
        current_account_id=current_account_id,
    )


@router.post("/scopes/unassign", response_class=HTMLResponse, name="admin_unassign_scope")
async def unassign_scope(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    scopes_service=Depends(get_scopes_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    dto = ScopeDTO.AssignScopeDTO(name=name.strip(), username=username.strip())
    if error_message is None:
        result = await scopes_service.unassign(account_id=current_account_id, dto=dto)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.scopes.unassign.error", started_at=t1, error=error, account_id=current_account_id, scope_name=dto.name, username=dto.username))
        else:
            success_message = f"Scope '{dto.name}' unassigned from '{dto.username}'."
            log.info(build_log_payload("admin_ui.scopes.unassign", started_at=t1, account_id=current_account_id, scope_name=dto.name, username=dto.username))
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        assignments, load_error = await _scope_assignments_metadata(scopes_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "scope_assignments.html",
        page_title="Scope assignments",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.get("/users", response_class=HTMLResponse, name="admin_users_page")
async def users_page(
    request: Request,
    users_service=Depends(get_users_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    users = []
    load_error = None
    if current_account_id and error_message is None:
        users, load_error = await _users_metadata(users_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.users.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.users.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.users.view", started_at=t1, account_id=current_account_id or None, user_count=len(users)))
    return _render(
        request,
        "users.html",
        page_title="Users",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        created_user_key=None,
        users=users,
        current_account_id=current_account_id,
    )


@router.post("/users", response_class=HTMLResponse, name="admin_create_user")
async def create_user(
    request: Request,
    username: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    users_service=Depends(get_users_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    created_user_key = None
    users = []
    if error_message is None:
        try:
            dto = UserDTO.CreateUserDTO(
                username=username.strip(),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email.strip(),
                password=password,
                profile_photo="",
            )
            result = await users_service.create_user(account_id=current_account_id, dto=dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.users.create.error", started_at=t1, error=error, account_id=current_account_id, username=dto.username, email=dto.email))
            else:
                created_user_key = result.unwrap().key
                success_message = f"User '{dto.username}' created."
                log.info(build_log_payload("admin_ui.users.create", started_at=t1, account_id=current_account_id, username=dto.username, email=dto.email, user_id=created_user_key))
        except ValidationError as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.users.create.error", started_at=t1, error=error, account_id=current_account_id, username=username.strip(), email=email.strip()))
    load_error = None
    if current_account_id and error_message is None:
        users, load_error = await _users_metadata(users_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "users.html",
        page_title="Users",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        created_user_key=created_user_key,
        users=users,
        current_account_id=current_account_id,
    )


@router.post("/users/delete", response_class=HTMLResponse, name="admin_delete_user")
async def delete_user(
    request: Request,
    username: str = Form(...),
    users_service=Depends(get_users_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await users_service.delete_user(account_id=current_account_id, username=username.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.users.delete.error", started_at=t1, error=error, account_id=current_account_id, username=username.strip()))
        else:
            success_message = f"User '{username.strip()}' deleted."
            log.info(build_log_payload("admin_ui.users.delete", started_at=t1, account_id=current_account_id, username=username.strip()))
    users = []
    load_error = None
    if current_account_id and error_message is None:
        users, load_error = await _users_metadata(users_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "users.html",
        page_title="Users",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        created_user_key=None,
        users=users,
        current_account_id=current_account_id,
    )


@router.post("/users/block", response_class=HTMLResponse, name="admin_block_user")
async def block_user(
    request: Request,
    username: str = Form(...),
    users_service=Depends(get_users_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await users_service.block_user(account_id=current_account_id, username=username.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.users.block.error", started_at=t1, error=error, account_id=current_account_id, username=username.strip()))
        else:
            success_message = f"User '{username.strip()}' blocked."
            log.info(build_log_payload("admin_ui.users.block", started_at=t1, account_id=current_account_id, username=username.strip()))
    users = []
    load_error = None
    if current_account_id and error_message is None:
        users, load_error = await _users_metadata(users_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "users.html",
        page_title="Users",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        created_user_key=None,
        users=users,
        current_account_id=current_account_id,
    )


@router.post("/users/unblock", response_class=HTMLResponse, name="admin_unblock_user")
async def unblock_user(
    request: Request,
    username: str = Form(...),
    users_service=Depends(get_users_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await users_service.unblock_user(account_id=current_account_id, username=username.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.users.unblock.error", started_at=t1, error=error, account_id=current_account_id, username=username.strip()))
        else:
            success_message = f"User '{username.strip()}' unblocked."
            log.info(build_log_payload("admin_ui.users.unblock", started_at=t1, account_id=current_account_id, username=username.strip()))
    users = []
    load_error = None
    if current_account_id and error_message is None:
        users, load_error = await _users_metadata(users_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "users.html",
        page_title="Users",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        created_user_key=None,
        users=users,
        current_account_id=current_account_id,
    )


@router.get("/licenses", response_class=HTMLResponse, name="admin_licenses_page")
async def licenses_page(
    request: Request,
    licenses_service=Depends(get_licenses_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    licenses = []
    load_error = None
    if current_account_id and error_message is None:
        licenses, load_error = await _licenses_metadata(licenses_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.licenses.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.licenses.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.licenses.view", started_at=t1, account_id=current_account_id or None, license_count=len(licenses)))
    return _render(
        request,
        "licenses.html",
        page_title="Licenses",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        license_result=None,
        licenses=licenses,
        current_account_id=current_account_id,
    )


@router.post("/licenses", response_class=HTMLResponse, name="admin_create_license")
async def create_license(
    request: Request,
    username: str = Form(...),
    scope: str = Form(...),
    expires_in: str = Form(...),
    force: str | None = Form(None),
    licenses_service=Depends(get_licenses_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    license_result = None
    licenses = []
    if error_message is None:
        try:
            dto = LicenseDTO.AssignLicenseDTO(
                username=username.strip(),
                scope=scope.strip(),
                expires_in=expires_in.strip(),
                force=force is not None,
            )
            result = await licenses_service.assign_license(account_id=current_account_id, dto=dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.licenses.create.error", started_at=t1, error=error, account_id=current_account_id, username=dto.username, scope_name=dto.scope))
            else:
                created = result.unwrap()
                license_result = created
                success_message = f"License assigned to '{dto.username}' for '{dto.scope.upper()}'."
                log.info(build_log_payload("admin_ui.licenses.create", started_at=t1, account_id=current_account_id, username=dto.username, scope_name=dto.scope.upper()))
        except ValidationError as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.licenses.create.error", started_at=t1, error=error, account_id=current_account_id, username=username.strip(), scope_name=scope.strip()))
    load_error = None
    if current_account_id and error_message is None:
        licenses, load_error = await _licenses_metadata(licenses_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "licenses.html",
        page_title="Licenses",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        license_result=license_result,
        licenses=licenses,
        current_account_id=current_account_id,
    )


@router.post("/licenses/delete", response_class=HTMLResponse, name="admin_delete_license")
async def delete_license(
    request: Request,
    username: str = Form(...),
    scope: str = Form(...),
    licenses_service=Depends(get_licenses_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    dto = LicenseDTO.DeleteLicenseDTO(username=username.strip(), scope=scope.strip())
    if error_message is None:
        result = await licenses_service.delete_license(account_id=current_account_id, dto=dto)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.licenses.delete.error", started_at=t1, error=error, account_id=current_account_id, username=dto.username, scope_name=dto.scope))
        else:
            success_message = f"License removed for '{dto.username}' on '{dto.scope.upper()}'."
            log.info(build_log_payload("admin_ui.licenses.delete", started_at=t1, account_id=current_account_id, username=dto.username, scope_name=dto.scope.upper()))
    licenses = []
    load_error = None
    if current_account_id and error_message is None:
        licenses, load_error = await _licenses_metadata(licenses_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "licenses.html",
        page_title="Licenses",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        license_result=None,
        licenses=licenses,
        current_account_id=current_account_id,
    )


@router.get("/acl", response_class=HTMLResponse, name="admin_acl_page")
async def acl_page(
    request: Request,
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.acl.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.acl.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.acl.view", started_at=t1, account_id=current_account_id or None, policy_count=len(policies), group_count=len(groups)))
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/groups", response_class=HTMLResponse, name="admin_create_acl_group")
async def create_acl_group(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    owner_id: str = Form(""),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await group_service.create_group(current_account_id, _admin_actor(owner_id), name.strip(), description.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.group.create.error", started_at=t1, error=error, account_id=current_account_id, group_name=name.strip()))
        else:
            success_message = f"ACL group '{name.strip()}' created."
            log.info(build_log_payload("admin_ui.acl.group.create", started_at=t1, account_id=current_account_id, group_name=name.strip(), group_id=result.unwrap()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/groups/delete", response_class=HTMLResponse, name="admin_delete_acl_group")
async def delete_acl_group(
    request: Request,
    group_id: str = Form(...),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await group_service.delete_group_admin(current_account_id, group_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.group.delete.error", started_at=t1, error=error, account_id=current_account_id, group_id=group_id.strip()))
        else:
            success_message = f"ACL group '{group_id.strip()}' deleted."
            log.info(build_log_payload("admin_ui.acl.group.delete", started_at=t1, account_id=current_account_id, group_id=group_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/groups/members/add", response_class=HTMLResponse, name="admin_add_acl_group_member")
async def add_acl_group_member(
    request: Request,
    group_id: str = Form(...),
    user_id: str = Form(...),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await group_service.add_members_admin(current_account_id, group_id.strip(), [user_id.strip()])
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.group.members.add.error", started_at=t1, error=error, account_id=current_account_id, group_id=group_id.strip(), user_id=user_id.strip()))
        else:
            success_message = f"Member '{user_id.strip()}' added to '{group_id.strip()}'."
            log.info(build_log_payload("admin_ui.acl.group.members.add", started_at=t1, account_id=current_account_id, group_id=group_id.strip(), user_id=user_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/groups/members/remove", response_class=HTMLResponse, name="admin_remove_acl_group_member")
async def remove_acl_group_member(
    request: Request,
    group_id: str = Form(...),
    user_id: str = Form(...),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await group_service.remove_members_admin(current_account_id, group_id.strip(), [user_id.strip()])
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.group.members.remove.error", started_at=t1, error=error, account_id=current_account_id, group_id=group_id.strip(), user_id=user_id.strip()))
        else:
            success_message = f"Member '{user_id.strip()}' removed from '{group_id.strip()}'."
            log.info(build_log_payload("admin_ui.acl.group.members.remove", started_at=t1, account_id=current_account_id, group_id=group_id.strip(), user_id=user_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/resources/claim", response_class=HTMLResponse, name="admin_claim_acl_resource")
async def claim_acl_resource(
    request: Request,
    resource_id: str = Form(...),
    owner_id: str = Form(""),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await acl_service.claim_resource(account_id=current_account_id, user_id=_admin_actor(owner_id), resource_id=resource_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.resource.claim.error", started_at=t1, error=error, account_id=current_account_id, resource_id=resource_id.strip()))
        else:
            success_message = f"Resource '{resource_id.strip()}' claimed."
            log.info(build_log_payload("admin_ui.acl.resource.claim", started_at=t1, account_id=current_account_id, resource_id=resource_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/grants", response_class=HTMLResponse, name="admin_grant_acl_permission")
async def grant_acl_permission(
    request: Request,
    resource_id: str = Form(...),
    principal_id: str = Form(...),
    principal_type: str = Form(...),
    permissions: str = Form(...),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        try:
            parsed_type = ACLPrincipalType(principal_type.strip().upper())
            parsed_permissions = _parse_csv_list(permissions)
            result = await acl_service.grant(
                account_id=current_account_id,
                caller_id=ADMIN_UI_ACTOR_ID,
                resource_id=resource_id.strip(),
                principal_id=principal_id.strip(),
                principal_type=parsed_type,
                permissions=parsed_permissions,
                is_admin=True,
            )
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.acl.grant.error", started_at=t1, error=error, account_id=current_account_id, resource_id=resource_id.strip(), principal_id=principal_id.strip()))
            else:
                success_message = f"ACL permissions granted on '{resource_id.strip()}'."
                log.info(build_log_payload("admin_ui.acl.grant", started_at=t1, account_id=current_account_id, resource_id=resource_id.strip(), principal_id=principal_id.strip(), principal_type=parsed_type.value))
        except (ValueError, ValidationError) as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.acl.grant.error", started_at=t1, error=error, account_id=current_account_id, resource_id=resource_id.strip(), principal_id=principal_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/revokes", response_class=HTMLResponse, name="admin_revoke_acl_permission")
async def revoke_acl_permission(
    request: Request,
    resource_id: str = Form(...),
    principal_id: str = Form(...),
    permissions: str = Form(...),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        parsed_permissions = _parse_csv_list(permissions)
        result = await acl_service.revoke(
            account_id=current_account_id,
            caller_id=ADMIN_UI_ACTOR_ID,
            resource_id=resource_id.strip(),
            principal_id=principal_id.strip(),
            permissions=parsed_permissions,
            is_admin=True,
        )
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.revoke.error", started_at=t1, error=error, account_id=current_account_id, resource_id=resource_id.strip(), principal_id=principal_id.strip()))
        else:
            success_message = f"ACL permissions revoked on '{resource_id.strip()}'."
            log.info(build_log_payload("admin_ui.acl.revoke", started_at=t1, account_id=current_account_id, resource_id=resource_id.strip(), principal_id=principal_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.post("/acl/resources/delete", response_class=HTMLResponse, name="admin_delete_acl_resource")
async def delete_acl_resource(
    request: Request,
    resource_id: str = Form(...),
    acl_service: ACLService = Depends(get_acl_service),
    group_service: GroupService = Depends(get_group_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await acl_service.delete_resource(current_account_id, resource_id.strip(), caller_id=ADMIN_UI_ACTOR_ID, is_admin=True)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.acl.resource.delete.error", started_at=t1, error=error, account_id=current_account_id, resource_id=resource_id.strip()))
        else:
            success_message = f"Resource policy '{resource_id.strip()}' deleted."
            log.info(build_log_payload("admin_ui.acl.resource.delete", started_at=t1, account_id=current_account_id, resource_id=resource_id.strip()))
    policies = []
    groups = []
    load_error = None
    if current_account_id and error_message is None:
        policies, groups, load_error = await _acl_metadata(acl_service, group_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "acl.html",
        page_title="ACL",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        acl_policies=policies,
        acl_groups=groups,
        acl_principal_types=list(ACLPrincipalType),
        current_account_id=current_account_id,
    )


@router.get("/rbac", response_class=HTMLResponse, name="admin_rbac_page")
async def rbac_page(
    request: Request,
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.rbac.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.rbac.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.rbac.view", started_at=t1, account_id=current_account_id or None, role_count=len(roles), assignment_count=len(assignments)))
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/roles", response_class=HTMLResponse, name="admin_create_rbac_role")
async def create_rbac_role(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    permissions: str = Form(""),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.create_role(
            account_id=current_account_id,
            name=name.strip(),
            description=description.strip() or None,
            permissions=_parse_csv_list(permissions),
        )
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.role.create.error", started_at=t1, error=error, account_id=current_account_id, role_name=name.strip()))
        else:
            success_message = f"RBAC role '{name.strip()}' created."
            log.info(build_log_payload("admin_ui.rbac.role.create", started_at=t1, account_id=current_account_id, role_name=name.strip(), role_id=result.unwrap().role_id))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/roles/update", response_class=HTMLResponse, name="admin_update_rbac_role")
async def update_rbac_role(
    request: Request,
    role_id: str = Form(...),
    name: str = Form(""),
    description: str = Form(""),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.update_role(
            account_id=current_account_id,
            role_id=role_id.strip(),
            name=name.strip() or None,
            description=description.strip(),
        )
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.role.update.error", started_at=t1, error=error, account_id=current_account_id, role_id=role_id.strip()))
        else:
            success_message = f"RBAC role '{role_id.strip()}' updated."
            log.info(build_log_payload("admin_ui.rbac.role.update", started_at=t1, account_id=current_account_id, role_id=role_id.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/roles/delete", response_class=HTMLResponse, name="admin_delete_rbac_role")
async def delete_rbac_role(
    request: Request,
    role_id: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.delete_role(current_account_id, role_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.role.delete.error", started_at=t1, error=error, account_id=current_account_id, role_id=role_id.strip()))
        else:
            success_message = f"RBAC role '{role_id.strip()}' deleted."
            log.info(build_log_payload("admin_ui.rbac.role.delete", started_at=t1, account_id=current_account_id, role_id=role_id.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/permissions/add", response_class=HTMLResponse, name="admin_add_rbac_permission")
async def add_rbac_permission(
    request: Request,
    role_id: str = Form(...),
    permission: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.add_permission(current_account_id, role_id.strip(), permission.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.permission.add.error", started_at=t1, error=error, account_id=current_account_id, role_id=role_id.strip(), permission=permission.strip()))
        else:
            success_message = f"Permission added to '{role_id.strip()}'."
            log.info(build_log_payload("admin_ui.rbac.permission.add", started_at=t1, account_id=current_account_id, role_id=role_id.strip(), permission=permission.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/permissions/remove", response_class=HTMLResponse, name="admin_remove_rbac_permission")
async def remove_rbac_permission(
    request: Request,
    role_id: str = Form(...),
    permission: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.remove_permission(current_account_id, role_id.strip(), permission.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.permission.remove.error", started_at=t1, error=error, account_id=current_account_id, role_id=role_id.strip(), permission=permission.strip()))
        else:
            success_message = f"Permission removed from '{role_id.strip()}'."
            log.info(build_log_payload("admin_ui.rbac.permission.remove", started_at=t1, account_id=current_account_id, role_id=role_id.strip(), permission=permission.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/parents/add", response_class=HTMLResponse, name="admin_add_rbac_parent")
async def add_rbac_parent(
    request: Request,
    role_id: str = Form(...),
    parent_role_id: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.add_parent(current_account_id, role_id.strip(), parent_role_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.parent.add.error", started_at=t1, error=error, account_id=current_account_id, role_id=role_id.strip(), parent_role_id=parent_role_id.strip()))
        else:
            success_message = f"Parent role added to '{role_id.strip()}'."
            log.info(build_log_payload("admin_ui.rbac.parent.add", started_at=t1, account_id=current_account_id, role_id=role_id.strip(), parent_role_id=parent_role_id.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/parents/remove", response_class=HTMLResponse, name="admin_remove_rbac_parent")
async def remove_rbac_parent(
    request: Request,
    role_id: str = Form(...),
    parent_role_id: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.remove_parent(current_account_id, role_id.strip(), parent_role_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.parent.remove.error", started_at=t1, error=error, account_id=current_account_id, role_id=role_id.strip(), parent_role_id=parent_role_id.strip()))
        else:
            success_message = f"Parent role removed from '{role_id.strip()}'."
            log.info(build_log_payload("admin_ui.rbac.parent.remove", started_at=t1, account_id=current_account_id, role_id=role_id.strip(), parent_role_id=parent_role_id.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/assignments/add", response_class=HTMLResponse, name="admin_assign_rbac_role")
async def assign_rbac_role(
    request: Request,
    subject_id: str = Form(...),
    role_id: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.assign_role(current_account_id, subject_id.strip(), role_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.assignment.add.error", started_at=t1, error=error, account_id=current_account_id, subject_id=subject_id.strip(), role_id=role_id.strip()))
        else:
            success_message = f"Role '{role_id.strip()}' assigned to '{subject_id.strip()}'."
            log.info(build_log_payload("admin_ui.rbac.assignment.add", started_at=t1, account_id=current_account_id, subject_id=subject_id.strip(), role_id=role_id.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.post("/rbac/assignments/remove", response_class=HTMLResponse, name="admin_unassign_rbac_role")
async def unassign_rbac_role(
    request: Request,
    subject_id: str = Form(...),
    role_id: str = Form(...),
    rbac_service: RBACService = Depends(get_rbac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    if error_message is None:
        result = await rbac_service.unassign_role(current_account_id, subject_id.strip(), role_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.rbac.assignment.remove.error", started_at=t1, error=error, account_id=current_account_id, subject_id=subject_id.strip(), role_id=role_id.strip()))
        else:
            success_message = f"Role '{role_id.strip()}' unassigned from '{subject_id.strip()}'."
            log.info(build_log_payload("admin_ui.rbac.assignment.remove", started_at=t1, account_id=current_account_id, subject_id=subject_id.strip(), role_id=role_id.strip()))
    roles = []
    assignments = []
    load_error = None
    if current_account_id and error_message is None:
        roles, assignments, load_error = await _rbac_metadata(rbac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "rbac.html",
        page_title="RBAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        roles=roles,
        assignments=assignments,
        current_account_id=current_account_id,
    )


@router.get("/abac", response_class=HTMLResponse, name="admin_abac_page")
async def abac_page(
    request: Request,
    abac_service: ABACService = Depends(get_abac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    policies = []
    load_error = None
    if current_account_id and error_message is None:
        policies, load_error = await _abac_metadata(abac_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.abac.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.abac.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.abac.view", started_at=t1, account_id=current_account_id or None, policy_count=len(policies)))
    return _render(
        request,
        "abac.html",
        page_title="ABAC",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        policies=policies,
        abac_effects=list(ABACEffect),
        evaluation_result=None,
        current_account_id=current_account_id,
    )


@router.post("/abac/policies", response_class=HTMLResponse, name="admin_create_abac_policy")
async def create_abac_policy(
    request: Request,
    name: str = Form(...),
    effect: str = Form(...),
    subject: str = Form(...),
    resource: str = Form(...),
    location: str = Form("*"),
    time_start: str = Form(""),
    time_end: str = Form(""),
    action: str = Form(...),
    abac_service: ABACService = Depends(get_abac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    evaluation_result = None
    if error_message is None:
        try:
            dto = _build_abac_policy_dto(
                name=name,
                effect=effect,
                subject=subject,
                resource=resource,
                location=location,
                time_start=time_start,
                time_end=time_end,
                action=action,
            )
            result = await abac_service.create_policy(current_account_id, dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.abac.policy.create.error", started_at=t1, error=error, account_id=current_account_id, policy_name=dto.name))
            else:
                success_message = f"ABAC policy '{dto.name}' created."
                log.info(build_log_payload("admin_ui.abac.policy.create", started_at=t1, account_id=current_account_id, policy_name=dto.name, policy_id=result.unwrap()))
        except (ValueError, ValidationError) as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.abac.policy.create.error", started_at=t1, error=error, account_id=current_account_id, policy_name=name.strip()))
    policies = []
    load_error = None
    if current_account_id and error_message is None:
        policies, load_error = await _abac_metadata(abac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "abac.html",
        page_title="ABAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        policies=policies,
        abac_effects=list(ABACEffect),
        evaluation_result=evaluation_result,
        current_account_id=current_account_id,
    )


@router.post("/abac/policies/update", response_class=HTMLResponse, name="admin_update_abac_policy")
async def update_abac_policy(
    request: Request,
    policy_id: str = Form(...),
    name: str = Form(...),
    effect: str = Form(...),
    subject: str = Form(...),
    resource: str = Form(...),
    location: str = Form("*"),
    time_start: str = Form(""),
    time_end: str = Form(""),
    action: str = Form(...),
    abac_service: ABACService = Depends(get_abac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    evaluation_result = None
    if error_message is None:
        try:
            dto = _build_abac_policy_dto(
                name=name,
                effect=effect,
                subject=subject,
                resource=resource,
                location=location,
                time_start=time_start,
                time_end=time_end,
                action=action,
            )
            result = await abac_service.update_policy(current_account_id, policy_id.strip(), dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.abac.policy.update.error", started_at=t1, error=error, account_id=current_account_id, policy_id=policy_id.strip()))
            else:
                success_message = f"ABAC policy '{policy_id.strip()}' updated."
                log.info(build_log_payload("admin_ui.abac.policy.update", started_at=t1, account_id=current_account_id, policy_id=policy_id.strip()))
        except (ValueError, ValidationError) as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.abac.policy.update.error", started_at=t1, error=error, account_id=current_account_id, policy_id=policy_id.strip()))
    policies = []
    load_error = None
    if current_account_id and error_message is None:
        policies, load_error = await _abac_metadata(abac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "abac.html",
        page_title="ABAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        policies=policies,
        abac_effects=list(ABACEffect),
        evaluation_result=evaluation_result,
        current_account_id=current_account_id,
    )


@router.post("/abac/policies/delete", response_class=HTMLResponse, name="admin_delete_abac_policy")
async def delete_abac_policy(
    request: Request,
    policy_id: str = Form(...),
    abac_service: ABACService = Depends(get_abac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    evaluation_result = None
    if error_message is None:
        result = await abac_service.delete_policy(current_account_id, policy_id.strip())
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.abac.policy.delete.error", started_at=t1, error=error, account_id=current_account_id, policy_id=policy_id.strip()))
        else:
            success_message = f"ABAC policy '{policy_id.strip()}' deleted."
            log.info(build_log_payload("admin_ui.abac.policy.delete", started_at=t1, account_id=current_account_id, policy_id=policy_id.strip()))
    policies = []
    load_error = None
    if current_account_id and error_message is None:
        policies, load_error = await _abac_metadata(abac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "abac.html",
        page_title="ABAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        policies=policies,
        abac_effects=list(ABACEffect),
        evaluation_result=evaluation_result,
        current_account_id=current_account_id,
    )


@router.post("/abac/evaluate", response_class=HTMLResponse, name="admin_evaluate_abac")
async def evaluate_abac(
    request: Request,
    subject: str = Form(...),
    resource: str = Form(...),
    location: str = Form("*"),
    time: str = Form(""),
    action: str = Form(...),
    abac_service: ABACService = Depends(get_abac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    evaluation_result = None
    if error_message is None:
        try:
            dto = ABACDTO.ABACEvaluateDTO(
                subject=subject.strip(),
                resource=resource.strip(),
                location=location.strip() or "*",
                time=time.strip() or None,
                action=action.strip(),
            )
            result = await abac_service.evaluate(current_account_id, dto)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.abac.evaluate.error", started_at=t1, error=error, account_id=current_account_id))
            else:
                evaluation_result = result.unwrap()
                success_message = "ABAC request evaluated."
                log.info(build_log_payload("admin_ui.abac.evaluate", started_at=t1, account_id=current_account_id, allowed=evaluation_result.allowed))
        except (ValueError, ValidationError) as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.abac.evaluate.error", started_at=t1, error=error, account_id=current_account_id))
    policies = []
    load_error = None
    if current_account_id and error_message is None:
        policies, load_error = await _abac_metadata(abac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "abac.html",
        page_title="ABAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        policies=policies,
        abac_effects=list(ABACEffect),
        evaluation_result=evaluation_result,
        current_account_id=current_account_id,
    )


@router.get("/ngac", response_class=HTMLResponse, name="admin_ngac_page")
async def ngac_page(
    request: Request,
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session)
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None:
        log.error(build_log_payload("admin_ui.ngac.view.error", started_at=t1, error=load_error))
    elif error_message is not None:
        log.warning(build_log_payload("admin_ui.ngac.view.error", started_at=t1, account_id=current_account_id))
    else:
        log.info(build_log_payload("admin_ui.ngac.view", started_at=t1, account_id=current_account_id or None, node_count=len(nodes), assignment_count=len(assignments), association_count=len(associations)))
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message if error_message is not None else (None if load_error is None else _error_message(load_error)),
        success_message=None,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=None,
        current_account_id=current_account_id,
    )


@router.post("/ngac/nodes", response_class=HTMLResponse, name="admin_create_ngac_node")
async def create_ngac_node(
    request: Request,
    name: str = Form(...),
    node_type: str = Form(...),
    properties_json: str = Form(""),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    if error_message is None:
        try:
            dto = NGACDTO.CreateNodeDTO(
                name=name.strip(),
                node_type=NodeType(node_type),
                properties=_parse_json_object(properties_json),
            )
            result = await ngac_service.create_node(current_account_id, dto, owner_id=ADMIN_UI_ACTOR_ID)
            if result.is_err:
                error = result.unwrap_err()
                error_message = _error_message(error)
                log.error(build_log_payload("admin_ui.ngac.node.create.error", started_at=t1, error=error, account_id=current_account_id, node_name=dto.name, node_type=dto.node_type.value))
            else:
                success_message = f"NGAC node '{dto.name}' created."
                log.info(build_log_payload("admin_ui.ngac.node.create", started_at=t1, account_id=current_account_id, node_name=dto.name, node_id=result.unwrap(), node_type=dto.node_type.value))
        except (ValueError, ValidationError, json.JSONDecodeError) as error:
            error_message = str(error)
            log.warning(build_log_payload("admin_ui.ngac.node.create.error", started_at=t1, error=error, account_id=current_account_id, node_name=name.strip(), node_type=node_type))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )


@router.post("/ngac/nodes/delete", response_class=HTMLResponse, name="admin_delete_ngac_node")
async def delete_ngac_node(
    request: Request,
    node_id: str = Form(...),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    if error_message is None:
        result = await ngac_service.delete_node(current_account_id, node_id.strip(), requester_key=ADMIN_UI_ACTOR_ID, is_admin=True)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.ngac.node.delete.error", started_at=t1, error=error, account_id=current_account_id, node_id=node_id.strip()))
        else:
            success_message = f"NGAC node '{node_id.strip()}' deleted."
            log.info(build_log_payload("admin_ui.ngac.node.delete", started_at=t1, account_id=current_account_id, node_id=node_id.strip()))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )


@router.post("/ngac/assignments/add", response_class=HTMLResponse, name="admin_add_ngac_assignment")
async def add_ngac_assignment(
    request: Request,
    from_id: str = Form(...),
    to_id: str = Form(...),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    dto = NGACDTO.AssignDTO(from_id=from_id.strip(), to_id=to_id.strip())
    if error_message is None:
        result = await ngac_service.assign(current_account_id, dto, owner_id=ADMIN_UI_ACTOR_ID, is_admin=True)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.ngac.assignment.add.error", started_at=t1, error=error, account_id=current_account_id, from_id=dto.from_id, to_id=dto.to_id))
        else:
            success_message = f"Assignment '{dto.from_id} -> {dto.to_id}' created."
            log.info(build_log_payload("admin_ui.ngac.assignment.add", started_at=t1, account_id=current_account_id, from_id=dto.from_id, to_id=dto.to_id, assignment_id=result.unwrap()))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )


@router.post("/ngac/assignments/remove", response_class=HTMLResponse, name="admin_remove_ngac_assignment")
async def remove_ngac_assignment(
    request: Request,
    from_id: str = Form(...),
    to_id: str = Form(...),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    dto = NGACDTO.RemoveAssignmentDTO(from_id=from_id.strip(), to_id=to_id.strip())
    if error_message is None:
        result = await ngac_service.remove_assignment(current_account_id, dto, requester_key=ADMIN_UI_ACTOR_ID, is_admin=True)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.ngac.assignment.remove.error", started_at=t1, error=error, account_id=current_account_id, from_id=dto.from_id, to_id=dto.to_id))
        else:
            success_message = f"Assignment '{dto.from_id} -> {dto.to_id}' removed."
            log.info(build_log_payload("admin_ui.ngac.assignment.remove", started_at=t1, account_id=current_account_id, from_id=dto.from_id, to_id=dto.to_id))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )


@router.post("/ngac/associations/add", response_class=HTMLResponse, name="admin_add_ngac_association")
async def add_ngac_association(
    request: Request,
    user_attribute_id: str = Form(...),
    object_attribute_id: str = Form(...),
    operations: str = Form(...),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    dto = NGACDTO.AssociateDTO(
        user_attribute_id=user_attribute_id.strip(),
        object_attribute_id=object_attribute_id.strip(),
        operations=_parse_csv_list(operations),
    )
    if error_message is None:
        result = await ngac_service.associate(current_account_id, dto, owner_id=ADMIN_UI_ACTOR_ID, is_admin=True)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.ngac.association.add.error", started_at=t1, error=error, account_id=current_account_id, user_attribute_id=dto.user_attribute_id, object_attribute_id=dto.object_attribute_id))
        else:
            success_message = f"Association created between '{dto.user_attribute_id}' and '{dto.object_attribute_id}'."
            log.info(build_log_payload("admin_ui.ngac.association.add", started_at=t1, account_id=current_account_id, user_attribute_id=dto.user_attribute_id, object_attribute_id=dto.object_attribute_id, association_id=result.unwrap()))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )


@router.post("/ngac/associations/remove", response_class=HTMLResponse, name="admin_remove_ngac_association")
async def remove_ngac_association(
    request: Request,
    association_id: str = Form(...),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    if error_message is None:
        result = await ngac_service.remove_association(current_account_id, association_id.strip(), requester_key=ADMIN_UI_ACTOR_ID, is_admin=True)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.ngac.association.remove.error", started_at=t1, error=error, account_id=current_account_id, association_id=association_id.strip()))
        else:
            success_message = f"Association '{association_id.strip()}' removed."
            log.info(build_log_payload("admin_ui.ngac.association.remove", started_at=t1, account_id=current_account_id, association_id=association_id.strip()))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )


@router.post("/ngac/check", response_class=HTMLResponse, name="admin_check_ngac_access")
async def check_ngac_access(
    request: Request,
    user_id: str = Form(...),
    object_id: str = Form(...),
    operation: str = Form(...),
    ngac_service: NGACService = Depends(get_ngac_service),
    accounts_service: AccountsService = Depends(get_accounts_service),
):
    session = _ensure_admin_session(request)
    if isinstance(session, RedirectResponse):
        return session
    t1 = T.time()
    current_account_id, error_message = await _active_account_selection(accounts_service, session, required=True)
    success_message = None
    access_decision = None
    if error_message is None:
        dto = NGACDTO.CheckAccessDTO(user_id=user_id.strip(), object_id=object_id.strip(), operation=operation.strip())
        result = await ngac_service.check_access(current_account_id, dto)
        if result.is_err:
            error = result.unwrap_err()
            error_message = _error_message(error)
            log.error(build_log_payload("admin_ui.ngac.check.error", started_at=t1, error=error, account_id=current_account_id, user_id=dto.user_id, object_id=dto.object_id, operation=dto.operation))
        else:
            access_decision = result.unwrap()
            success_message = "NGAC access request evaluated."
            log.info(build_log_payload("admin_ui.ngac.check", started_at=t1, account_id=current_account_id, user_id=dto.user_id, object_id=dto.object_id, operation=dto.operation, allowed=access_decision.allowed))
    nodes = []
    assignments = []
    associations = []
    load_error = None
    if current_account_id and error_message is None:
        nodes, assignments, associations, load_error = await _ngac_metadata(ngac_service, current_account_id)
    if load_error is not None and error_message is None:
        error_message = _error_message(load_error)
    return _render(
        request,
        "ngac.html",
        page_title="NGAC",
        authenticated=True,
        error_message=error_message,
        success_message=success_message,
        nodes=nodes,
        assignments=assignments,
        associations=associations,
        node_types=list(NodeType),
        access_decision=access_decision,
        current_account_id=current_account_id,
    )
