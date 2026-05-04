import pytest

from tests.scopes.conftest import ACCOUNT_ID

OTHER_ACCOUNT_ID = "acc-other"


@pytest.mark.asyncio
async def test_scopes_controller_create_and_assign(scopes_client):
    create_res = await scopes_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    assert create_res.status_code == 200
    assert create_res.json()["name"] == "OPS"

    assign_res = await scopes_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/scopes/assign",
        json={"name": "ops", "username": "alice"},
    )
    assert assign_res.status_code == 200
    body = assign_res.json()
    assert body["name"] == "OPS"
    assert body["username"] == "alice"
    assert body["ok"] is True

    assignments_res = await scopes_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/scopes/assignments")
    assert assignments_res.status_code == 200
    assert assignments_res.json()[0]["name"] == "OPS"

    other_assignments_res = await scopes_client.get(f"/api/v4/accounts/{OTHER_ACCOUNT_ID}/scopes/assignments")
    assert other_assignments_res.status_code == 404

    delete_res = await scopes_client.request("DELETE", f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    assert delete_res.status_code == 409

    unassign_res = await scopes_client.request(
        "DELETE",
        f"/api/v4/accounts/{ACCOUNT_ID}/scopes/assign",
        json={"name": "ops", "username": "alice"},
    )
    assert unassign_res.status_code == 204

    delete_res = await scopes_client.request("DELETE", f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    assert delete_res.status_code == 204

    list_res = await scopes_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/scopes")
    assert list_res.status_code == 200
    assert list_res.json() == []


@pytest.mark.asyncio
async def test_scopes_controller_rejects_unknown_account(scopes_client):
    res = await scopes_client.get(f"/api/v4/accounts/{OTHER_ACCOUNT_ID}/scopes")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_scopes_controller_duplicate_scope_returns_conflict(scopes_client):
    await scopes_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    duplicate = await scopes_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    assert duplicate.status_code == 409
