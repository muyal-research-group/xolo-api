import pytest

from tests.support import app_client
import xoloapi.db as DbX
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames


ACCOUNT_ID = "acc-acl-service"
COLLECTIONS = [
    CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    CollectionNames.SECURITY_GROUPS_COLLECTION_NAME,
    CollectionNames.GROUP_MEMBERS_COLLECTION_NAME,
    CollectionNames.USERS_COLLECTION_NAME,
]


def _path(path: str, account_id: str = ACCOUNT_ID) -> str:
    return f"/api/v4/accounts/{account_id}/acl/service{path}"


@pytest.mark.asyncio
async def test_service_group_lifecycle_requires_no_owner_session():
    async with app_client(
        "xolo_test_acl_service",
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.SERVICE, APIKeyScope.GROUPS],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID],
    ) as client:
        await DbX.get_database()[CollectionNames.USERS_COLLECTION_NAME].insert_many([
            {"account_id": ACCOUNT_ID, "key": "owner-1", "username": "owner", "normalized_username": "owner", "first_name": "Owner", "last_name": "One", "email": "owner@example.com", "hash_password": "unused"},
            {"account_id": ACCOUNT_ID, "key": "member-1", "username": "member", "normalized_username": "member", "first_name": "Member", "last_name": "One", "email": "member@example.com", "hash_password": "unused"},
        ])
        response = await client.post(
            _path("/groups"),
            json={"name": "team:1:members", "owner_id": "owner"},
        )
        assert response.status_code == 201
        group_id = response.json()["group_id"]

        added = await client.post(_path(f"/groups/{group_id}/members"), json={"members": ["member"]})
        assert added.status_code == 204
        repeated_add = await client.post(_path(f"/groups/{group_id}/members"), json={"members": ["member-1"]})
        assert repeated_add.status_code == 204
        listed = await client.get(_path(f"/groups/{group_id}/members"))
        assert listed.status_code == 200
        assert [row["user_id"] for row in listed.json()] == ["member-1"]

        transferred = await client.post(_path(f"/groups/{group_id}/owner"), json={"user_id": "member-1"})
        assert transferred.status_code == 204
        group = await DbX.get_database()[CollectionNames.SECURITY_GROUPS_COLLECTION_NAME].find_one({"account_id": ACCOUNT_ID, "group_id": group_id})
        assert group["owner_id"] == "member-1"
        assert {row["user_id"] for row in (await client.get(_path(f"/groups/{group_id}/members"))).json()} == {"member-1", "owner-1"}
        repeated_transfer = await client.post(_path(f"/groups/{group_id}/owner"), json={"user_id": "member-1"})
        assert repeated_transfer.status_code == 204

        removed = await client.request("DELETE", _path(f"/groups/{group_id}/members"), json={"members": ["member-1"]})
        assert removed.status_code == 204
        repeated_remove = await client.request("DELETE", _path(f"/groups/{group_id}/members"), json={"members": ["member-1"]})
        assert repeated_remove.status_code == 204
        assert [row["user_id"] for row in (await client.get(_path(f"/groups/{group_id}/members"))).json()] == ["owner-1"]
        assert (await client.request("DELETE", _path(f"/groups/{group_id}/members"), json={"members": ["owner-1"]})).status_code == 204
        assert (await client.get(_path(f"/groups/{group_id}/members"))).json() == []

        deleted = await client.delete(_path(f"/groups/{group_id}"))
        assert deleted.status_code == 204
        assert (await client.delete(_path(f"/groups/{group_id}"))).status_code == 404

        no_keep = await client.post(_path("/groups"), json={"name": "team:2", "owner_id": "owner-1"})
        assert no_keep.status_code == 201
        second_group_id = no_keep.json()["group_id"]
        transferred_without_membership = await client.post(
            _path(f"/groups/{second_group_id}/owner"),
            json={"user_id": "member-1", "keep_previous_as_member": False},
        )
        assert transferred_without_membership.status_code == 204
        assert (await client.get(_path(f"/groups/{second_group_id}/members"))).json() == []
        assert (await client.post(_path(f"/groups/{second_group_id}/owner"), json={"user_id": "member-1"})).status_code == 204
        assert (await client.get(_path(f"/groups/{second_group_id}/members"))).json() == []


@pytest.mark.asyncio
async def test_service_groups_require_service_and_groups_scopes_and_matching_account():
    for scopes in ([APIKeyScope.ALL, APIKeyScope.GROUPS], [APIKeyScope.SERVICE, APIKeyScope.ACL]):
        async with app_client(
            "xolo_test_acl_service_scopes",
            COLLECTIONS,
            api_key_scopes=scopes,
            api_key_account_id=ACCOUNT_ID,
            account_ids=[ACCOUNT_ID],
        ) as client:
            response = await client.post(_path("/groups"), json={"name": "team:1", "owner_id": "owner-1"})
            assert response.status_code == 403

    async with app_client(
        "xolo_test_acl_service_account",
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.SERVICE, APIKeyScope.GROUPS],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID, "other-account"],
    ) as client:
        response = await client.post(_path("/groups", "other-account"), json={"name": "team:1", "owner_id": "owner-1"})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_service_group_identifiers_cannot_resolve_other_account_users():
    async with app_client(
        "xolo_test_acl_service_user_isolation",
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.SERVICE, APIKeyScope.GROUPS],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID, "other-account"],
    ) as client:
        await DbX.get_database()[CollectionNames.USERS_COLLECTION_NAME].insert_many([
            {"account_id": ACCOUNT_ID, "key": "owner-1", "username": "owner", "first_name": "Owner", "last_name": "One", "email": "owner@example.com", "hash_password": "unused"},
            {"account_id": "other-account", "key": "outsider-1", "username": "outsider", "first_name": "Out", "last_name": "Sider", "email": "out@example.com", "hash_password": "unused"},
        ])
        denied_owner = await client.post(_path("/groups"), json={"name": "bad", "owner_id": "outsider-1"})
        assert denied_owner.status_code == 404

        created = await client.post(_path("/groups"), json={"name": "good", "owner_id": "owner-1"})
        assert created.status_code == 201
        group_id = created.json()["group_id"]
        denied_member = await client.post(_path(f"/groups/{group_id}/members"), json={"members": ["outsider-1"]})
        assert denied_member.status_code == 404
        denied_transfer = await client.post(_path(f"/groups/{group_id}/owner"), json={"user_id": "outsider"})
        assert denied_transfer.status_code == 404


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
