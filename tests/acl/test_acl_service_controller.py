import pytest

from tests.support import app_client
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames


ACCOUNT_ID = "acc-acl-service"
COLLECTIONS = [
    CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    CollectionNames.ACL_GROUPS_COLLECTION_NAME,
    CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
]


def _path(path: str, account_id: str = ACCOUNT_ID) -> str:
    return f"/api/v4/accounts/{account_id}/acl/service{path}"


@pytest.mark.asyncio
async def test_acl_service_group_routes_are_removed():
    async with app_client(
        "xolo_test_acl_service",
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.SERVICE, APIKeyScope.ACL],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID],
    ) as client:
        response = await client.post(
            _path("/groups"),
            json={"name": "team:1:members", "owner_id": "team-owner"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_all_scope_does_not_grant_service_authority():
    async with app_client(
        "xolo_test_acl_service_denied",
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.ALL, APIKeyScope.ACL],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID],
    ) as client:
        response = await client.post(
            _path("/claim"),
            json={"resource_id": "ve:1", "owner_id": "user-1", "owner_type": "USER"},
        )
        assert response.status_code == 403
