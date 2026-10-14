import pytest
import pytest_asyncio

import commonx.dto.xolo as DTO
import xoloapi.db as DbX
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


@pytest.mark.asyncio
async def test_update_grant_permissions_by_stable_grant_id(acl_client):
    await DbX.get_database()[CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME].insert_one({
        "account_id": ACCOUNT_ID,
        "resource_id": "document-1",
        "grants": [
            {
                "grant_id": "grant-owner",
                "principal_type": "USER",
                "principal_id": "u-acl-http",
                "permissions": ["read", "write", "update", "delete", "sys:manage"],
                "is_owner": True,
            },
            {
                "grant_id": "grant-reader",
                "principal_type": "USER",
                "principal_id": "u-reader",
                "permissions": ["read"],
                "is_owner": False,
            },
        ],
    })

    response = await acl_client.patch(
        _path("/resources/document-1/grants/grant-reader"),
        json={"permissions": ["write", "update"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["grant_id"] == "grant-reader"
    assert set(response.json()["permissions"]) == {"write", "update"}
    stored = await DbX.get_database()[CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME].find_one(
        {"account_id": ACCOUNT_ID, "resource_id": "document-1"}
    )
    grant = next(item for item in stored["grants"] if item["grant_id"] == "grant-reader")
    assert set(grant["permissions"]) == {"write", "update"}


@pytest.mark.asyncio
async def test_update_grant_rejects_owner_and_empty_permissions(acl_client):
    await DbX.get_database()[CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME].insert_one({
        "account_id": ACCOUNT_ID,
        "resource_id": "document-2",
        "grants": [{
            "grant_id": "grant-owner",
            "principal_type": "USER",
            "principal_id": "u-acl-http",
            "permissions": ["read", "write", "update", "delete", "sys:manage"],
            "is_owner": True,
        }],
    })

    owner_response = await acl_client.patch(
        _path("/resources/document-2/grants/grant-owner"),
        json={"permissions": ["read"]},
    )
    empty_response = await acl_client.patch(
        _path("/resources/document-2/grants/grant-owner"),
        json={"permissions": []},
    )

    assert owner_response.status_code == 409
    assert empty_response.status_code == 422
