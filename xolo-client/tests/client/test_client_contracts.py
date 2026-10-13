import json
import pytest
from unittest.mock import patch

import requests

from xolo.client import errors as E
from xolo.client import models as M
from xolo.client.client import XoloClient


def _response(payload=None, status_code: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = "http://localhost/test"
    response.headers = {}
    if payload is None:
        response._content = b""
    else:
        response._content = json.dumps(payload).encode()
        response.headers["Content-Type"] = "application/json"
    return response


def test_auth_uses_account_scoped_url_and_api_key_header():
    client = XoloClient(account_id="acct-1", api_key="test-api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "key": "user-1",
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "profile_photo": "",
            "access_token": "token-1",
            "metadata": {},
            "temporal_secret": "temp-1",
        }
    )) as request:
        result = client.auth(username="alice", password="secret", scope="scope-1")

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/users/auth"
    assert kwargs["headers"] == {"X-API-Key": "test-api-key"}
    assert kwargs["json"]["scope"] == "scope-1"


def test_create_scope_uses_admin_token_and_account_scoped_url():
    client = XoloClient(
        account_id="acct-1",
        api_key="",
        api_url="http://localhost:10000/api/v4",
        admin_token="admin-1",
    )

    with patch("xolo.client.client.R.request", return_value=_response({"name": "SCOPE-1"})) as request:
        result = client.create_scope(scope="scope-1")

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/scopes"
    assert kwargs["headers"] == {"X-Admin-Token": "admin-1"}
    assert kwargs["json"] == {"name": "scope-1"}


def test_create_role_uses_bearer_temporal_secret_and_api_key():
    client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "role_id": "role-1",
            "name": "Reader",
            "description": "Read only",
            "permissions": ["documents:read"],
            "parent_role_ids": [],
        }
    )) as request:
        result = client.create_role(
            name="Reader",
            description="Read only",
            permissions=["documents:read"],
            token="bearer-1",
            temporal_secret="temp-1",
        )

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/rbac/roles"
    assert kwargs["headers"] == {
        "Authorization": "Bearer bearer-1",
        "Temporal-Secret-Key": "temp-1",
        "X-API-Key": "api-key",
    }


def test_create_role_allows_api_key_override():
    client = XoloClient(account_id="acct-1", api_key="default-api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "role_id": "role-1",
            "name": "Reader",
            "description": "Read only",
            "permissions": ["documents:read"],
            "parent_role_ids": [],
        }
    )) as request:
        result = client.create_role(
            name="Reader",
            description="Read only",
            permissions=["documents:read"],
            token="bearer-1",
            temporal_secret="temp-1",
            api_key="override-api-key",
        )

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["headers"] == {
        "Authorization": "Bearer bearer-1",
        "Temporal-Secret-Key": "temp-1",
        "X-API-Key": "override-api-key",
    }


def test_create_role_allows_admin_token_without_api_key():
    client = XoloClient(account_id="acct-1", api_key="", api_url="http://localhost:10000/api/v4", admin_token="admin-1")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "role_id": "role-1",
            "name": "Reader",
            "description": "Read only",
            "permissions": ["documents:read"],
            "parent_role_ids": [],
        }
    )) as request:
        result = client.create_role(
            name="Reader",
            description="Read only",
            permissions=["documents:read"],
            token="bearer-1",
            temporal_secret="temp-1",
        )

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["headers"] == {
        "Authorization": "Bearer bearer-1",
        "Temporal-Secret-Key": "temp-1",
        "X-Admin-Token": "admin-1",
    }


def test_create_role_requires_admin_token_or_api_key():
    client = XoloClient(account_id="acct-1", api_key="", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request") as request:
        result = client.create_role(
            name="Reader",
            description="Read only",
            permissions=["documents:read"],
            token="bearer-1",
            temporal_secret="temp-1",
        )

    assert result.is_err
    assert not request.called


def test_get_current_user_does_not_send_api_key_header():
    client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "key": "user-1",
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "profile_photo": "",
            "metadata": {},
        }
    )) as request:
        result = client.get_current_user(token="bearer-1", temporal_secret="temp-1")

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["headers"] == {
        "Authorization": "Bearer bearer-1",
        "Temporal-Secret-Key": "temp-1",
    }


def test_list_accounts_uses_global_accounts_endpoint():
    client = XoloClient(account_id="acct-1", api_key="", api_url="http://localhost:10000/api/v4", admin_token="admin-1")

    with patch("xolo.client.client.R.request", return_value=_response([{"account_id": "acct-1", "name": "Primary"}])) as request:
        result = client.list_accounts()

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts"
    assert kwargs["headers"] == {"X-Admin-Token": "admin-1"}


def test_update_user_password_requires_recovery_token():
    client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

    result = client.update_user_password(username="alice", password="new-password")

    assert result.is_err
    error = result.unwrap_err()
    assert isinstance(error, E.ValidationError)


def test_delete_user_uses_account_scoped_url_and_api_key_header():
    client = XoloClient(account_id="acct-1", api_key="test-api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(status_code=204)) as request:
        result = client.delete_user(username="alice")

    assert result.is_ok
    value = result.unwrap()
    assert value.username == "alice"
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "DELETE"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/users/alice"
    assert kwargs["headers"] == {"X-API-Key": "test-api-key"}


def test_introspect_session_sends_both_session_parts_and_service_key():
    client = XoloClient(account_id="acct-1", api_key="service-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response({
        "key": "user-1",
        "username": "alice",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        "profile_photo": "",
        "disabled": False,
    })) as request:
        result = client.introspect_session("token-1", "secret-1")

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/users/introspect"
    assert kwargs["headers"] == {
        "Authorization": "Bearer token-1",
        "Temporal-Secret-Key": "secret-1",
        "X-API-Key": "service-key",
    }


def test_service_acl_calls_need_only_the_service_key():
    client = XoloClient(account_id="acct-1", api_key="service-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(status_code=204)) as request:
        result = client.service_claim_resource("ve:1", "team:1:owners", owner_type="GROUP")

    assert result.is_ok
    kwargs = request.call_args.kwargs
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/acl/service/claim"
    assert kwargs["headers"] == {"X-API-Key": "service-key"}
    assert kwargs["json"] == {
        "resource_id": "ve:1",
        "owner_id": "team:1:owners",
        "owner_type": "GROUP",
    }


def test_service_effective_access_parses_permissions_and_groups():
    client = XoloClient(account_id="acct-1", api_key="service-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response({
        "user_id": "user-1",
        "resource_id": "ve:1",
        "is_owner": False,
        "permissions": ["read", "write"],
        "group_ids": ["team:1", "team:1:admins"],
    })) as request:
        result = client.service_get_effective_access("ve:1", "user-1")

    assert result.is_ok
    access = result.unwrap()
    assert access.permissions == {"read", "write"}
    assert access.group_ids == ["team:1", "team:1:admins"]
    assert request.call_args.kwargs["headers"] == {"X-API-Key": "service-key"}


def test_service_group_creation_carries_the_external_owner_id():
    client = XoloClient(account_id="acct-1", api_key="service-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response({"group_id": "g-team-owner"})) as request:
        result = client.service_create_group("team:1:owners", "user-1")

    assert result.is_ok
    assert result.unwrap().group_id == "g-team-owner"
    assert request.call_args.kwargs["json"] == {
        "name": "team:1:owners",
        "owner_id": "user-1",
        "description": "",
    }


def test_refresh_token_uses_bearer_headers_and_account_scoped_url():
    client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "profile_photo": "",
            "access_token": "new-token",
            "temporal_secret": "new-secret",
            "metadata": {},
            "user_id": "user-uuid",
        }
    )) as request:
        result = client.refresh_token(token="old-token", temporal_secret="old-secret")

    assert result.is_ok
    dto = result.unwrap()
    assert dto.access_token == "new-token"
    assert dto.temporal_secret == "new-secret"
    kwargs = request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://localhost:10000/api/v4/accounts/acct-1/users/refresh"
    assert kwargs["headers"] == {
        "Authorization": "Bearer old-token",
        "Temporal-Secret-Key": "old-secret",
    }
    assert kwargs["json"] == {"expiration": "15min"}


def test_refresh_token_forwards_custom_expiration():
    client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "profile_photo": "",
            "access_token": "new-token",
            "temporal_secret": "new-secret",
            "metadata": {},
        }
    )) as request:
        client.refresh_token(token="old-token", temporal_secret="old-secret", expiration="2d")

    assert request.call_args.kwargs["json"] == {"expiration": "2d"}


def test_refresh_token_does_not_include_api_key_header():
    client = XoloClient(account_id="acct-1", api_key="api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(
        {
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "profile_photo": "",
            "access_token": "new-token",
            "temporal_secret": "new-secret",
            "metadata": {},
        }
    )) as request:
        client.refresh_token(token="old-token", temporal_secret="old-secret")

    assert "X-API-Key" not in request.call_args.kwargs["headers"]


def test_delete_user_deprecates_admin_token():
    client = XoloClient(account_id="acct-1", api_key="test-api-key", api_url="http://localhost:10000/api/v4")

    with patch("xolo.client.client.R.request", return_value=_response(status_code=204)):
        with pytest.warns(DeprecationWarning, match="admin_token is deprecated"):
            result = client.delete_user(username="alice", admin_token="ignored-admin-token")

    assert result.is_ok
    assert result.unwrap().username == "alice"
