import pytest
import jwt

from tests.licenses.conftest import ACCOUNT_ID
OTHER_ACCOUNT_ID = "acc-other"


@pytest.mark.asyncio
async def test_licenses_controller_create_and_delete(licenses_client):
    create_res = await licenses_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/licenses",
        json={"username": "alice", "scope": "ops", "expires_in": "15m", "force": True},
    )
    assert create_res.status_code == 200
    assert create_res.json()["ok"] is True

    list_res = await licenses_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/licenses")
    assert list_res.status_code == 200
    assert list_res.json()[0]["scope"] == "OPS"

    other_list_res = await licenses_client.get(f"/api/v4/accounts/{OTHER_ACCOUNT_ID}/licenses")
    assert other_list_res.status_code == 200
    assert other_list_res.json() == []

    delete_res = await licenses_client.request(
        "DELETE",
        f"/api/v4/accounts/{ACCOUNT_ID}/licenses",
        json={"username": "alice", "scope": "ops"},
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["ok"] is True


@pytest.mark.asyncio
async def test_licenses_controller_self_delete(licenses_client):
    await licenses_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/licenses",
        json={"username": "alice", "scope": "ops", "expires_in": "15m", "force": True},
    )
    tmp_secret = "temporary-secret"
    token = jwt.encode({"iss": "OPS", "uid2": "alice", "aid": ACCOUNT_ID}, tmp_secret, algorithm="HS256")

    res = await licenses_client.request(
        "DELETE",
        f"/api/v4/accounts/{ACCOUNT_ID}/licenses/self",
        json={
            "token": token,
            "tmp_secret_key": tmp_secret,
            "username": "alice",
            "scope": "ops",
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
