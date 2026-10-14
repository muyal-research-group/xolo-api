import datetime
import pytest

from xoloapi.groups.domain.aggregates import SecurityGroup
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from tests.groups.conftest import ACCOUNT_ID

USER_ID = "u-alice"
OTHER_USER_ID = "u-bob"


def _group(group_id: str, owner_id: str) -> SecurityGroup:
    now = datetime.datetime.now(datetime.timezone.utc)
    return SecurityGroup(
        account_id=ACCOUNT_ID,
        group_id=group_id,
        name=group_id,
        owner_id=owner_id,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_delete_all_for_user_blocks_when_user_owns_group(
    groups_repo: MongoSecurityGroupRepository,
):
    await groups_repo.save(_group("g-alice", USER_ID))
    await groups_repo.add_member(ACCOUNT_ID, "g-alice", OTHER_USER_ID)

    result = await groups_repo.delete_all_for_user(ACCOUNT_ID, USER_ID)

    assert result.is_err
    assert result.unwrap_err().metadata["group_ids"] == ["g-alice"]
    remaining = (await groups_repo.list_all(ACCOUNT_ID)).unwrap()
    assert [group.group_id for group in remaining] == ["g-alice"]
    members = (await groups_repo.list_members(ACCOUNT_ID, "g-alice")).unwrap()
    assert [member.user_id for member in members] == [OTHER_USER_ID]


@pytest.mark.asyncio
async def test_delete_all_for_user_removes_user_memberships(
    groups_repo: MongoSecurityGroupRepository,
):
    await groups_repo.save(_group("g-bob", OTHER_USER_ID))
    await groups_repo.add_member(ACCOUNT_ID, "g-bob", USER_ID)

    result = await groups_repo.delete_all_for_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    # The group itself (owned by OTHER_USER) must survive
    remaining = (await groups_repo.list_all(ACCOUNT_ID)).unwrap()
    assert len(remaining) == 1
    assert remaining[0].group_id == "g-bob"
    # But alice is no longer a member
    is_member = (await groups_repo.is_member(ACCOUNT_ID, "g-bob", USER_ID)).unwrap()
    assert is_member is False


@pytest.mark.asyncio
async def test_delete_all_for_user_does_not_affect_other_users_groups(
    groups_repo: MongoSecurityGroupRepository,
):
    await groups_repo.save(_group("g-bob", OTHER_USER_ID))
    await groups_repo.add_member(ACCOUNT_ID, "g-bob", OTHER_USER_ID)

    result = await groups_repo.delete_all_for_user(ACCOUNT_ID, USER_ID)

    assert result.is_ok
    assert result.unwrap() == 0
    remaining = (await groups_repo.list_all(ACCOUNT_ID)).unwrap()
    assert len(remaining) == 1
    members = (await groups_repo.list_members(ACCOUNT_ID, "g-bob")).unwrap()
    assert len(members) == 1


@pytest.mark.asyncio
async def test_delete_all_for_user_does_not_remove_memberships_when_ownership_blocks(
    groups_repo: MongoSecurityGroupRepository,
):
    # alice owns g1, is a member in g2 (owned by bob)
    await groups_repo.save(_group("g1", USER_ID))
    await groups_repo.add_member(ACCOUNT_ID, "g1", OTHER_USER_ID)
    await groups_repo.save(_group("g2", OTHER_USER_ID))
    await groups_repo.add_member(ACCOUNT_ID, "g2", USER_ID)

    result = await groups_repo.delete_all_for_user(ACCOUNT_ID, USER_ID)

    assert result.is_err
    assert result.unwrap_err().metadata["group_ids"] == ["g1"]
    # The operation is blocked before any memberships or groups are changed.
    remaining = (await groups_repo.list_all(ACCOUNT_ID)).unwrap()
    assert [g.group_id for g in remaining] == ["g1", "g2"]
    members_g1 = (await groups_repo.list_members(ACCOUNT_ID, "g1")).unwrap()
    assert [member.user_id for member in members_g1] == [OTHER_USER_ID]
    is_member = (await groups_repo.is_member(ACCOUNT_ID, "g2", USER_ID)).unwrap()
    assert is_member is True


@pytest.mark.asyncio
async def test_delete_all_for_user_returns_zero_when_no_data(
    groups_repo: MongoSecurityGroupRepository,
):
    result = await groups_repo.delete_all_for_user(ACCOUNT_ID, USER_ID)
    assert result.is_ok
    assert result.unwrap() == 0
