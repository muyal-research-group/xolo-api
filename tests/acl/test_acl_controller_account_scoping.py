import pytest
import pytest_asyncio

import commonx.dto.xolo as DTO
import xoloapi.middleware as MX
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames
from tests.support import app, app_client

ACCOUNT_ID = "acc-acl-http"


def _path(path: str, account_id: str = ACCOUNT_ID) -> str:
    return f"/api/v4/accounts/{account_id}/acl{path}"


@pytest.fixture
def fake_user():
    return DTO.UserDTO(
        key="u-acl-http",
        username="acluser",
        first_name="ACL",
        last_name="User",
        email="acl@test.com",
        profile_photo="",
    )


@pytest_asyncio.fixture
async def acl_client(fake_user):
    app.dependency_overrides[MX.get_current_user] = lambda: fake_user
    async with app_client(
        "xolo_test_acl_http",
        [
            CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
            CollectionNames.ACL_GROUPS_COLLECTION_NAME,
            CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
        ],
        api_key_scopes=[APIKeyScope.ALL, APIKeyScope.ACL],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID, "acc-other"],
    ) as client:
        yield client
    app.dependency_overrides.pop(MX.get_current_user, None)


@pytest.mark.asyncio
async def test_claim_and_list_resources_are_account_scoped(acl_client):
    claim = await acl_client.post(_path("/claim"), json={"resource_id": "bucket-1"})
    assert claim.status_code == 204

    resources = await acl_client.get(_path("/resources"))
    assert resources.status_code == 200
    assert [item["resource_id"] for item in resources.json()["owned_resources"]["items"]] == ["bucket-1"]


@pytest.mark.asyncio
async def test_account_mismatch_returns_403(acl_client):
    res = await acl_client.get(_path("/resources", account_id="acc-other"))
    assert res.status_code == 403
