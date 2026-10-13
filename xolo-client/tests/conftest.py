from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import Callable, Generator
from uuid import uuid4

from dotenv import load_dotenv
import pytest
import requests

from xolo.client.client import XoloClient
from xolo.client import models as M


ENV_PATH = os.environ.get("ENV_PATH", "/home/nacho/Programming/Python/xolo/tests/.env")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)

XOLO_API_URL = os.environ.get("XOLO_API_URL", "http://localhost:10000/api/v4")
XOLO_HTTP_ROOT = XOLO_API_URL.rsplit("/api/v4", 1)[0]
XOLO_CONTAINER_NAME = os.environ.get("XOLO_CONTAINER_NAME", "xolo-api")
HTTP_TIMEOUT = 20


@dataclass
class LiveConfig:
    api_url: str
    account_id: str
    acl_key: str
    admin_token: str


@dataclass
class LiveUserContext:
    username: str
    password: str
    scope: str
    user_key: str
    auth: M.AuthenticatedDTO


def _docker_env(container_name: str) -> dict[str, str]:
    try:
        output = subprocess.check_output(
            [
                "docker",
                "inspect",
                container_name,
                "--format",
                "{{range .Config.Env}}{{println .}}{{end}}",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}

    env: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


def _live_secret(name: str, docker_env: dict[str, str], default: str = "") -> str:
    return os.environ.get(name) or docker_env.get(name, default)


def _first_nonempty(*values: str) -> str:
    return next((value.strip() for value in values if value and value.strip()), "")


def _rand(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _unwrap_ok(result, dto_type):
    assert result.is_ok, result.unwrap_err()
    value = result.unwrap()
    assert isinstance(value, dto_type)
    return value


def _unwrap_ok_list(result, item_type):
    assert result.is_ok, result.unwrap_err()
    values = result.unwrap()
    assert isinstance(values, list)
    assert all(isinstance(item, item_type) for item in values)
    return values


@pytest.fixture(scope="session")
def live_config() -> LiveConfig:
    try:
        response = requests.get(f"{XOLO_HTTP_ROOT}/openapi.json", timeout=HTTP_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"Live Xolo API is unavailable at {XOLO_HTTP_ROOT}: {exc}")



    docker_env = _docker_env(XOLO_CONTAINER_NAME)
    acl_key = _live_secret("XOLO_API_KEY", docker_env)
    admin_tokens = _first_nonempty(
        os.environ.get("XOLO_SUPER_ADMIN_TOKENS", ""),
        os.environ.get("XOLO_SUPER_ADMIN_KEYS", ""),
        docker_env.get("XOLO_SUPER_ADMIN_TOKENS", ""),
        docker_env.get("XOLO_SUPER_ADMIN_KEYS", ""),
    )
    admin_token = _first_nonempty(
        os.environ.get("XOLO_ADMIN_TOKEN", ""),
        *(token.strip() for token in admin_tokens.split(",")),
    )
    if not admin_token:
        pytest.skip("Live admin token is not configured.")

    account_id = _first_nonempty(
        os.environ.get("XOLO_ACCOUNT_ID", ""),
        docker_env.get("XOLO_ACCOUNT_ID", ""),
    )

    try:
        response = requests.get(
            f"{XOLO_API_URL}/accounts",
            headers={"X-Admin-Token": admin_token},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"Live admin access is unavailable for account-scoped tests: {exc}")

    accounts = response.json()
    if not account_id and isinstance(accounts, list) and accounts:
        account_id = accounts[0].get("account_id", "")

    if not account_id:
        pytest.skip("Live account_id is not configured and no admin-visible accounts were found.")

    return LiveConfig(
        api_url     = XOLO_API_URL,
        account_id  = account_id,
        acl_key     = acl_key,
        admin_token = admin_token,
    )


@pytest.fixture
def rand_name() -> Callable[[str], str]:
    return _rand


@pytest.fixture
def unwrap_ok():
    return _unwrap_ok


@pytest.fixture
def unwrap_ok_list():
    return _unwrap_ok_list


@pytest.fixture(scope="session")
def admin_client(live_config: LiveConfig) -> XoloClient:
    return XoloClient(
        account_id=live_config.account_id,
        api_key="",
        api_url=live_config.api_url,
        secret=live_config.acl_key,
        admin_token=live_config.admin_token,
    )


@pytest.fixture(scope="session")
def session_api_key(admin_client: XoloClient) -> Generator[M.CreatedAPIKeyResponseDTO, None, None]:
    created = _unwrap_ok(
        admin_client.create_api_key(
            name=_rand("session-key"),
            scopes=["all"],
            admin_token=admin_client.admin_token,
        ),
        M.CreatedAPIKeyResponseDTO,
    )
    yield created
    revoked = admin_client.revoke_api_key(key_id=created.key_id, admin_token=admin_client.admin_token)
    assert revoked.is_ok, revoked.unwrap_err()


@pytest.fixture(scope="session")
def protected_client(
    live_config: LiveConfig,
    session_api_key: M.CreatedAPIKeyResponseDTO,
) -> XoloClient:
    return XoloClient(
        account_id  = session_api_key.account_id,
        api_url     = live_config.api_url,
        secret      = live_config.acl_key,
        api_key     = session_api_key.key,
        admin_token = live_config.admin_token,
    )


@pytest.fixture
def make_signed_up_user(protected_client: XoloClient):
    def _factory(scope: str | None = None) -> LiveUserContext:
        actual_scope = scope or _rand("scope")
        if scope is None:
            created_scope = _unwrap_ok(
                protected_client.create_scope(scope=actual_scope, secret=protected_client.secret),
                M.CreatedScopeResponseDTO,
            )
            assert created_scope.name == actual_scope.upper()

        username = _rand("signup-user")
        password = "secret"
        created_user = _unwrap_ok(
            protected_client.signup(
                username=username,
                first_name="Signup",
                last_name="User",
                email=f"{username}@x.com",
                password=password,
                scope=actual_scope,
                expiration="1d",
            ),
            M.CreatedUserResponseDTO,
        )
        auth = _unwrap_ok(
            protected_client.auth(
                username=username,
                password=password,
                scope=actual_scope,
                expiration="1d",
                renew_token=True,
            ),
            M.AuthenticatedDTO,
        )
        return LiveUserContext(
            username=username,
            password=password,
            scope=actual_scope,
            user_key=created_user.key,
            auth=auth,
        )

    return _factory


@pytest.fixture
def make_provisioned_user(protected_client: XoloClient):
    def _factory(scope: str | None = None, password: str = "secret") -> LiveUserContext:
        actual_scope = scope or _rand("scope")
        if scope is None:
            created_scope = _unwrap_ok(
                protected_client.create_scope(scope=actual_scope, secret=protected_client.secret),
                M.CreatedScopeResponseDTO,
            )
            assert created_scope.name == actual_scope.upper()

        username = _rand("created-user")
        created_user = _unwrap_ok(
            protected_client.create_user(
                username=username,
                first_name="Created",
                last_name="User",
                email=f"{username}@x.com",
                password=password,
                profile_photo="",
            ),
            M.CreatedUserResponseDTO,
        )
        assigned_scope = _unwrap_ok(
            protected_client.assign_scope(
                username=username,
                scope=actual_scope,
                secret=protected_client.secret,
            ),
            M.AssignedScopeResponseDTO,
        )
        assert assigned_scope.name == actual_scope.upper()

        created_license = _unwrap_ok(
            protected_client.create_license(
                username=username,
                scope=actual_scope,
                secret=protected_client.secret,
                expires_in="1d",
            ),
            M.AssignLicenseResponseDTO,
        )
        assert created_license.expires_at

        auth = _unwrap_ok(
            protected_client.auth(
                username=username,
                password=password,
                scope=actual_scope,
                expiration="1d",
                renew_token=True,
            ),
            M.AuthenticatedDTO,
        )
        return LiveUserContext(
            username=username,
            password=password,
            scope=actual_scope,
            user_key=created_user.key,
            auth=auth,
        )

    return _factory
