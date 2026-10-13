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
async def test_service_key_can_manage_team_groups_and_resource_access():
    async with app_client(
        "xolo_test_acl_service",
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.SERVICE, APIKeyScope.ACL],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID],
    ) as client:
        group_ids = {}
        for role, owner in (("owners", "team-owner"), ("admins", "team-owner"), ("members", "team-owner")):
            response = await client.post(
                _path("/groups"),
                json={"name": f"team:1:{role}", "owner_id": owner},
            )
            assert response.status_code == 201
            group_ids[role] = response.json()["group_id"]

        assert (await client.post(
            _path(f"/groups/{group_ids['admins']}/members"),
            json={"members": ["team-admin"]},
        )).status_code == 204
        assert (await client.post(
            _path(f"/groups/{group_ids['members']}/members"),
            json={"members": ["team-owner", "team-admin", "team-member"]},
        )).status_code == 204

        assert (await client.post(
            _path("/claim"),
            json={"resource_id": "ve:1", "owner_id": group_ids["owners"], "owner_type": "GROUP"},
        )).status_code == 204
        assert (await client.post(
            _path("/grant"),
            json={
                "resource_id": "ve:1",
                "principal_id": group_ids["admins"],
                "principal_type": "GROUP",
                "permissions": ["read", "write", "update", "delete"],
            },
        )).status_code == 204
        assert (await client.post(
            _path("/grant"),
            json={
                "resource_id": "ve:1",
                "principal_id": group_ids["members"],
                "principal_type": "GROUP",
                "permissions": ["read"],
            },
        )).status_code == 204

        owner_access = await client.get(_path("/resources/ve:1/users/team-owner/access"))
        assert owner_access.status_code == 200
        assert owner_access.json()["is_owner"] is True
        assert set(owner_access.json()["permissions"]) == {"read", "write", "update", "delete", "sys:manage"}

        admin_access = await client.get(_path("/resources/ve:1/users/team-admin/access"))
        assert admin_access.status_code == 200
        assert admin_access.json()["is_owner"] is False
        assert set(admin_access.json()["permissions"]) == {"read", "write", "update", "delete"}

        member_access = await client.get(_path("/resources/ve:1/users/team-member/access"))
        assert member_access.status_code == 200
        assert member_access.json()["permissions"] == ["read"]

        resources = await client.get(_path("/users/team-admin/resources"))
        assert resources.status_code == 200
        visible = resources.json()["shared_resources"]["items"]
        assert [item["resource_id"] for item in visible] == ["ve:1"]

        grants = await client.get(_path("/resources/ve:1/grants"))
        assert grants.status_code == 200
        assert len(grants.json()["grants"]) == 3

        members = await client.get(_path(f"/groups/{group_ids['members']}/members"))
        assert members.status_code == 200
        assert {member["user_id"] for member in members.json()} == {"team-owner", "team-admin", "team-member"}

        removed = await client.request(
            "DELETE",
            _path(f"/groups/{group_ids['members']}/members"),
            json={"members": ["team-member"]},
        )
        assert removed.status_code == 204
        removed_access = await client.get(_path("/resources/ve:1/users/team-member/access"))
        assert removed_access.status_code == 200
        assert removed_access.json()["permissions"] == []

        transfer_group = await client.post(
            _path(f"/groups/{group_ids['admins']}/owner"),
            json={"user_id": "team-admin", "keep_previous_as_member": True},
        )
        assert transfer_group.status_code == 204

        transfer_resource = await client.post(
            _path("/resources/ve:1/owner"),
            json={
                "principal_id": "team-owner",
                "principal_type": "USER",
                "keep_previous_permissions": ["read"],
            },
        )
        assert transfer_resource.status_code == 204
        direct_owner_access = await client.get(_path("/resources/ve:1/users/team-owner/access"))
        assert direct_owner_access.status_code == 200
        assert direct_owner_access.json()["is_owner"] is True

        revoked = await client.request(
            "DELETE",
            _path("/revoke"),
            json={
                "resource_id": "ve:1",
                "principal_id": group_ids["admins"],
                "principal_type": "GROUP",
                "permissions": ["write"],
            },
        )
        assert revoked.status_code == 204
        admin_after_revoke = await client.get(_path("/resources/ve:1/users/team-admin/access"))
        assert set(admin_after_revoke.json()["permissions"]) == {"read", "update", "delete"}

        invalid = await client.post(
            _path("/grant"),
            json={
                "resource_id": "ve:1",
                "principal_id": "someone",
                "principal_type": "ROBOT",
                "permissions": ["fly"],
            },
        )
        assert invalid.status_code == 422

        assert (await client.delete(_path("/resources/ve:1"))).status_code == 204
        assert (await client.delete(_path(f"/groups/{group_ids['members']}"))).status_code == 204


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
