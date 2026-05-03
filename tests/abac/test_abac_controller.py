"""
Controller-level (HTTP) tests for the ABAC module.

Uses FastAPI's TestClient with dependency overrides so no real auth token is
needed.  MongoDB must be reachable at localhost:27018; Redis must be up for
the app lifespan.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from tests.abac.conftest import ACCOUNT_ID
from xoloapi.accounts.dependencies import get_accounts_service


def _account_path(path: str, account_id: str = ACCOUNT_ID) -> str:
    return f"/api/v4/accounts/{account_id}/abac{path}"


_ALLOW_PAYLOAD = {
    "name":   "Teachers can read grades",
    "effect": "ALLOW",
    "events": [
        {
            "subject":  "Teacher",
            "resource": "Grades",
            "location": "*",
            "action":   "read",
        }
    ],
}

_DENY_PAYLOAD = {
    "name":   "Nobody can delete",
    "effect": "DENY",
    "events": [
        {
            "subject":  "*",
            "resource": "*",
            "action":   "delete",
        }
    ],
}


# ── POST /abac/policies ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_policy_returns_201(abac_client: AsyncClient):
    res = await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)
    assert res.status_code == 201
    body = res.json()
    assert "policy_id" in body
    assert body["policy_id"].startswith("ap-")


@pytest.mark.asyncio
async def test_create_policy_deny_effect(abac_client: AsyncClient):
    res = await abac_client.post(_account_path("/policies"), json=_DENY_PAYLOAD)
    assert res.status_code == 201


# ── GET /abac/policies ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_policies_empty(abac_client: AsyncClient):
    res = await abac_client.get(_account_path("/policies"))
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_policies_shows_created(abac_client: AsyncClient):
    await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)
    await abac_client.post(_account_path("/policies"), json=_DENY_PAYLOAD)

    res = await abac_client.get(_account_path("/policies"))
    assert res.status_code == 200
    assert len(res.json()) == 2


# ── GET /abac/policies/{id} ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_policy_200(abac_client: AsyncClient):
    create_res  = await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)
    policy_id   = create_res.json()["policy_id"]

    res = await abac_client.get(_account_path(f"/policies/{policy_id}"))
    assert res.status_code == 200
    body = res.json()
    assert body["policy_id"] == policy_id
    assert body["effect"] == "ALLOW"
    assert len(body["events"]) == 1


@pytest.mark.asyncio
async def test_get_policy_404(abac_client: AsyncClient):
    res = await abac_client.get(_account_path("/policies/does-not-exist"))
    assert res.status_code == 404


# ── DELETE /abac/policies/{id} ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_policy_204(abac_client: AsyncClient):
    policy_id = (await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)).json()["policy_id"]

    res = await abac_client.delete(_account_path(f"/policies/{policy_id}"))
    assert res.status_code == 204

    # Confirm gone
    assert (await abac_client.get(_account_path(f"/policies/{policy_id}"))).status_code == 404


@pytest.mark.asyncio
async def test_delete_policy_404(abac_client: AsyncClient):
    res = await abac_client.delete(_account_path("/policies/ghost-id"))
    assert res.status_code == 404


# ── POST /abac/evaluate ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_allow(abac_client: AsyncClient):
    await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)

    res = await abac_client.post(_account_path("/evaluate"), json={
        "subject":  "Teacher",
        "resource": "Grades",
        "location": "Campus",
        "action":   "read",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True
    assert body["matched_policy"] is not None


@pytest.mark.asyncio
async def test_evaluate_deny_by_deny_policy(abac_client: AsyncClient):
    await abac_client.post(_account_path("/policies"), json=_DENY_PAYLOAD)

    res = await abac_client.post(_account_path("/evaluate"), json={
        "subject":  "anyone",
        "resource": "anything",
        "action":   "delete",
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False


@pytest.mark.asyncio
async def test_evaluate_default_deny_with_no_policies(abac_client: AsyncClient):
    res = await abac_client.post(_account_path("/evaluate"), json={
        "subject":  "Teacher",
        "resource": "Grades",
        "action":   "read",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is False
    assert body["matched_policy"] is None


@pytest.mark.asyncio
async def test_evaluate_deny_overrides_allow(abac_client: AsyncClient):
    await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)
    await abac_client.post(_account_path("/policies"), json={
        "name":   "Emergency deny",
        "effect": "DENY",
        "events": [{"subject": "Teacher", "resource": "Grades", "action": "read"}],
    })

    res = await abac_client.post(_account_path("/evaluate"), json={
        "subject":  "Teacher",
        "resource": "Grades",
        "action":   "read",
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False


@pytest.mark.asyncio
async def test_evaluate_with_time_window(abac_client: AsyncClient):
    await abac_client.post(_account_path("/policies"), json={
        "name":   "Business hours only",
        "effect": "ALLOW",
        "events": [{
            "subject":    "Doctor",
            "resource":   "Chart",
            "action":     "read",
            "time_start": "09:00",
            "time_end":   "17:00",
        }],
    })

    inside = await abac_client.post(_account_path("/evaluate"), json={
        "subject": "Doctor", "resource": "Chart", "action": "read", "time": "12:00"
    })
    outside = await abac_client.post(_account_path("/evaluate"), json={
        "subject": "Doctor", "resource": "Chart", "action": "read", "time": "20:00"
    })

    assert inside.json()["allowed"] is True
    assert outside.json()["allowed"] is False


# ── Auth guard ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(abac_accounts_service):
    from xoloapi.server import app
    from xoloapi.middleware.apikey import _get_apikey_service
    from tests.abac.conftest import _FakeAPIKeyService

    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()
    app.dependency_overrides[get_accounts_service] = lambda: abac_accounts_service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as client:
        for method, path in [
            ("GET",    "/api/v4/accounts/acc-abac/abac/policies"),
            ("POST",   "/api/v4/accounts/acc-abac/abac/policies"),
            ("POST",   "/api/v4/accounts/acc-abac/abac/evaluate"),
        ]:
            res = await getattr(client, method.lower())(path)
            assert res.status_code == 401, f"{method} {path} should require auth"
    app.dependency_overrides.pop(_get_apikey_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)


@pytest.mark.asyncio
async def test_account_scoping_isolated(abac_client: AsyncClient):
    await abac_client.post(_account_path("/policies"), json=_ALLOW_PAYLOAD)

    other_list = await abac_client.get(_account_path("/policies", account_id="acc-other"))
    assert other_list.status_code == 403
