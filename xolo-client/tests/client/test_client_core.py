from option import Ok

from xolo.client.client import XoloClient
from xolo.client import models as M


def test_base_url_returns_account_scoped_url():
    client = XoloClient(
        account_id="account-123",
        api_key="api-key",
        api_url="http://localhost:10000/api/v4",
    )

    assert client.base_url() == "http://localhost:10000/api/v4/accounts/account-123"


def test_execute_script_runs_create_scope_command(
    monkeypatch,
    rand_name,
    unwrap_ok,
):
    scope = rand_name("script-scope")
    client = XoloClient(
        account_id="account-123",
        api_key="api-key",
        api_url="http://localhost:10000/api/v4",
        admin_token="admin-token",
    )

    monkeypatch.setattr(
        client,
        "create_scope",
        lambda scope, secret="": Ok(M.CreatedScopeResponseDTO(name=scope.upper())),
    )

    results = client.execute_script(f"CREATE SCOPE '{scope}';")

    assert isinstance(results, list)
    assert len(results) == 1

    created_scope = unwrap_ok(results[0], M.CreatedScopeResponseDTO)
    assert created_scope.name == scope.upper()
