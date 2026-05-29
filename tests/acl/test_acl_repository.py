import pytest

from xoloapi.acl.domain.aggregates import AccessGrant, ResourcePolicy
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType
from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
from tests.acl.conftest import ACCOUNT_ID

USER_ID = "u-alice"
OTHER_USER_ID = "u-bob"


def _grant(user_id: str, is_owner: bool = False) -> AccessGrant:
    return AccessGrant(
        grant_id=f"g-{user_id}-{'owner' if is_owner else 'grantee'}",
        principal=Principal(type=PrincipalType.USER, id=user_id),
        permissions={Permission.READ},
        is_owner=is_owner,
    )


def _policy(resource_id: str, *grants: AccessGrant) -> ResourcePolicy:
    return ResourcePolicy(account_id=ACCOUNT_ID, resource_id=resource_id, grants=list(grants))


@pytest.mark.asyncio
async def test_delete_all_by_user_removes_owned_policy(acl_policy_repo: MongoResourcePolicyRepository):
    await acl_policy_repo.save(_policy("res-owned", _grant(USER_ID, is_owner=True)))

    result = await acl_policy_repo.delete_all_by_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    assert result.unwrap() == 1
    remaining = (await acl_policy_repo.list_all(ACCOUNT_ID)).unwrap()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_all_by_user_removes_grantee_policy(acl_policy_repo: MongoResourcePolicyRepository):
    await acl_policy_repo.save(
        _policy("res-shared", _grant(OTHER_USER_ID, is_owner=True), _grant(USER_ID))
    )

    result = await acl_policy_repo.delete_all_by_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    assert result.unwrap() == 1
    remaining = (await acl_policy_repo.list_all(ACCOUNT_ID)).unwrap()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_all_by_user_does_not_remove_unrelated_policy(acl_policy_repo: MongoResourcePolicyRepository):
    await acl_policy_repo.save(_policy("res-other", _grant(OTHER_USER_ID, is_owner=True)))

    result = await acl_policy_repo.delete_all_by_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    assert result.unwrap() == 0
    remaining = (await acl_policy_repo.list_all(ACCOUNT_ID)).unwrap()
    assert len(remaining) == 1
    assert remaining[0].resource_id == "res-other"


@pytest.mark.asyncio
async def test_delete_all_by_user_removes_multiple_policies(acl_policy_repo: MongoResourcePolicyRepository):
    for i in range(3):
        await acl_policy_repo.save(_policy(f"res-{i}", _grant(USER_ID, is_owner=True)))
    await acl_policy_repo.save(_policy("res-untouched", _grant(OTHER_USER_ID, is_owner=True)))

    result = await acl_policy_repo.delete_all_by_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    assert result.unwrap() == 3
    remaining = (await acl_policy_repo.list_all(ACCOUNT_ID)).unwrap()
    assert len(remaining) == 1
    assert remaining[0].resource_id == "res-untouched"


@pytest.mark.asyncio
async def test_delete_all_by_user_returns_zero_when_no_match(acl_policy_repo: MongoResourcePolicyRepository):
    result = await acl_policy_repo.delete_all_by_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    assert result.unwrap() == 0
