from option import NONE, Ok, Some
import pytest

from commonx.models.xolo import User
from xoloapi.acl.application.acl_service import ACLService
from xoloapi.acl.domain.value_objects import PrincipalType
from xoloapi.groups.application.group_service import GroupService
from xoloapi.groups.domain.aggregates import GroupMember


ACCOUNT_ID = "acc-usernames"


def _user(key: str, username: str) -> User:
    return User(
        key=key,
        first_name=username.title(),
        last_name="User",
        username=username,
        email=f"{username}@example.com",
        hash_password="unused",
    )


class MemoryUsers:
    def __init__(self):
        self.users = {"user-alice": _user("user-alice", "alice")}

    async def find_by_username(self, account_id, username):
        return next((Some(user) for user in self.users.values() if user.username == username), NONE)

    async def find_by_id(self, user_id, account_id=None):
        return Some(self.users[user_id]) if user_id in self.users else NONE

    async def find_all(self, account_id):
        return Ok(list(self.users.values()))


class MemoryPolicies:
    def __init__(self):
        self.policies = {}

    async def find_by_resource(self, account_id, resource_id):
        policy = self.policies.get((account_id, resource_id))
        return Ok(Some(policy) if policy else NONE)

    async def save(self, policy):
        self.policies[(policy.account_id, policy.resource_id)] = policy
        return Ok(True)


class MemoryGroups:
    def __init__(self):
        self.groups = {}
        self.members = set()

    async def find_by_id(self, account_id, group_id):
        group = self.groups.get((account_id, group_id))
        return Ok(Some(group) if group else NONE)

    async def find_by_name(self, account_id, name):
        group = next((g for (account, _), g in self.groups.items() if account == account_id and g.name == name), None)
        return Ok(Some(group) if group else NONE)

    async def find_groups_for_user(self, account_id, user_id):
        return Ok([
            group
            for (account, group_id), group in self.groups.items()
            if account == account_id and (account_id, group_id, user_id) in self.members
        ])

    async def list_all(self, account_id):
        return Ok([group for (account, _), group in self.groups.items() if account == account_id])

    async def save(self, group):
        self.groups[(group.account_id, group.group_id)] = group
        return Ok(True)

    async def add_member(self, account_id, group_id, user_id):
        self.members.add((account_id, group_id, user_id))
        return Ok(True)

    async def remove_member(self, account_id, group_id, user_id):
        self.members.discard((account_id, group_id, user_id))
        return Ok(True)

    async def list_members(self, account_id, group_id):
        return Ok([
            GroupMember(account_id=account_id, group_id=group_id, user_id=user_id)
            for account, stored_group_id, user_id in self.members
            if account == account_id and stored_group_id == group_id
        ])


@pytest.mark.asyncio
async def test_acl_resolves_username_to_user_id_and_can_clean_up_dangling_grant():
    users = MemoryUsers()
    policies = MemoryPolicies()
    groups = MemoryGroups()
    service = ACLService(policies, groups, users)

    assert (await service.claim_resource(ACCOUNT_ID, "owner", "document:1")).is_ok
    granted = await service.grant(
        ACCOUNT_ID,
        "owner",
        "document:1",
        None,
        PrincipalType.USER,
        ["read"],
        principal_username="alice",
    )
    assert granted.is_ok

    policy = policies.policies[(ACCOUNT_ID, "document:1")]
    assert any(grant.principal.id == "user-alice" for grant in policy.grants)
    assert all(grant.principal.id != "alice" for grant in policy.grants)

    users.users.clear()
    revoked = await service.revoke(
        ACCOUNT_ID,
        "owner",
        "document:1",
        "user-alice",
        ["read"],
    )
    assert revoked.is_ok
    policy = policies.policies[(ACCOUNT_ID, "document:1")]
    assert all(grant.principal.id != "user-alice" for grant in policy.grants)


@pytest.mark.asyncio
async def test_group_members_accept_usernames_and_group_grants_can_be_checked_directly():
    users = MemoryUsers()
    policies = MemoryPolicies()
    groups = MemoryGroups()
    group_service = GroupService(groups, users)
    acl_service = ACLService(policies, groups, users)

    group_id = (await group_service.create_group(ACCOUNT_ID, "owner", "Reviewers")).unwrap()
    added = await group_service.add_members(
        ACCOUNT_ID,
        "owner",
        group_id,
        [],
        usernames=["alice"],
    )
    assert added.is_ok
    assert (ACCOUNT_ID, group_id, "user-alice") in groups.members

    assert (await acl_service.claim_resource(ACCOUNT_ID, "owner", "document:2")).is_ok
    assert (await acl_service.grant(
        ACCOUNT_ID,
        "owner",
        "document:2",
        group_id,
        PrincipalType.GROUP,
        ["read"],
    )).is_ok
    checked = await acl_service.check(
        ACCOUNT_ID,
        group_id,
        "document:2",
        ["read"],
        principal_type=PrincipalType.GROUP,
    )
    assert checked.unwrap() is True
