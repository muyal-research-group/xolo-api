import pytest

from xoloapi.db.constants import CollectionNames
from tests.support import app_client

DB_NAME = "xolo_test_apikeys"
COLLECTIONS = [CollectionNames.API_KEYS_COLLECTION_NAME]


@pytest.mark.asyncio
async def test_apikeys_controller_is_account_scoped():
    async with app_client(DB_NAME, COLLECTIONS, admin_token="admin-token", account_ids=["acc-a", "acc-b"]) as client:
        create_res = await client.post(
            "/api/v4/accounts/acc-a/apikeys",
            json={"name": "ops-admin", "scopes": ["users", "licenses"]},
        )
        assert create_res.status_code == 201
        body = create_res.json()
        assert body["account_id"] == "acc-a"
        assert body["key"].startswith("XOLO_")
        key_id = body["key_id"]

        list_res = await client.get("/api/v4/accounts/acc-a/apikeys")
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1
        assert list_res.json()[0]["account_id"] == "acc-a"
        assert "key" not in list_res.json()[0]

        other_list_res = await client.get("/api/v4/accounts/acc-b/apikeys")
        assert other_list_res.status_code == 200
        assert other_list_res.json() == []

        other_get_res = await client.get(f"/api/v4/accounts/acc-b/apikeys/{key_id}")
        assert other_get_res.status_code == 404

        other_delete_res = await client.request("DELETE", f"/api/v4/accounts/acc-b/apikeys/{key_id}")
        assert other_delete_res.status_code == 404

        delete_res = await client.request("DELETE", f"/api/v4/accounts/acc-a/apikeys/{key_id}")
        assert delete_res.status_code == 204

        final_list_res = await client.get("/api/v4/accounts/acc-a/apikeys")
        assert final_list_res.status_code == 200
        assert len(final_list_res.json()) == 1
        assert final_list_res.json()[0]["is_active"] is False
