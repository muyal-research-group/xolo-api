import pytest

from xoloapi.db.constants import CollectionNames
from tests.support import app_client

DB_NAME = "xolo_test_accounts"
COLLECTIONS = [CollectionNames.ACCOUNTS_COLLECTION_NAME]


@pytest.mark.asyncio
async def test_accounts_controller_crud_flow():
    async with app_client(DB_NAME, COLLECTIONS, admin_token="admin-token") as client:
        create_res = await client.post(
            "/api/v4/accounts",
            json={"account_id": "acc-primary", "name": "Primary account"},
        )
        assert create_res.status_code == 201
        assert create_res.json()["account_id"] == "acc-primary"
        assert create_res.json()["name"] == "Primary account"

        list_res = await client.get("/api/v4/accounts")
        assert list_res.status_code == 200
        assert [account["account_id"] for account in list_res.json()] == ["acc-primary"]

        delete_res = await client.request("DELETE", "/api/v4/accounts/acc-primary")
        assert delete_res.status_code == 204

        list_res = await client.get("/api/v4/accounts")
        assert list_res.status_code == 200
        assert list_res.json() == []
