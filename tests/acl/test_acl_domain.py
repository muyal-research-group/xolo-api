from xoloapi.acl.domain.aggregates import ResourcePolicy
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType


def test_owner_receives_every_permission_including_update():
    policy = ResourcePolicy(account_id="acc-1", resource_id="ve:1")
    claimed = policy.claim_principal(Principal(type=PrincipalType.GROUP, id="team:1:owners"))

    assert claimed.is_ok
    owned = claimed.unwrap()
    assert owned.effective_permissions(["team:1:owners"]) == set(Permission)
    assert owned.is_owned_by_any(["team:1:owners"]) is True


def test_three_team_groups_combine_to_the_expected_roles():
    policy = ResourcePolicy(account_id="acc-1", resource_id="ve:1")
    policy = policy.claim_principal(Principal(type=PrincipalType.GROUP, id="team:1:owners")).unwrap()
    owner_ids = ["team:1:owners"]
    policy = policy.grant(
        Principal(type=PrincipalType.GROUP, id="team:1:admins"),
        {Permission.READ, Permission.WRITE, Permission.UPDATE, Permission.DELETE},
        owner_ids,
    ).unwrap()
    policy = policy.grant(
        Principal(type=PrincipalType.GROUP, id="team:1"),
        {Permission.READ},
        owner_ids,
    ).unwrap()

    assert policy.effective_permissions(["team:1"]) == {Permission.READ}
    assert policy.effective_permissions(["team:1", "team:1:admins"]) == {
        Permission.READ,
        Permission.WRITE,
        Permission.UPDATE,
        Permission.DELETE,
    }
    assert policy.effective_permissions(["team:1", "team:1:owners"]) == set(Permission)


def test_transferring_owner_can_retain_limited_access_for_previous_owner():
    original = Principal(type=PrincipalType.USER, id="user-1")
    replacement = Principal(type=PrincipalType.GROUP, id="team:1:owners")
    policy = ResourcePolicy(account_id="acc-1", resource_id="ve:1").claim_principal(original).unwrap()

    transferred = policy.transfer_owner(replacement, {Permission.READ}).unwrap()

    assert transferred.effective_permissions([original.id]) == {Permission.READ}
    assert transferred.is_owned_by_any([original.id]) is False
    assert transferred.effective_permissions([replacement.id]) == set(Permission)
    assert transferred.is_owned_by_any([replacement.id]) is True


def test_update_grant_permissions_replaces_permissions_and_preserves_grant_identity():
    owner = Principal(type=PrincipalType.USER, id="owner-1")
    reader = Principal(type=PrincipalType.USER, id="reader-1")
    policy = ResourcePolicy(account_id="acc-1", resource_id="ve:1").claim_principal(owner).unwrap()
    policy = policy.grant(reader, {Permission.READ}, [owner.id]).unwrap()
    original = next(grant for grant in policy.grants if grant.principal == reader)

    updated = policy.update_grant_permissions(
        original.grant_id,
        {Permission.WRITE, Permission.UPDATE},
        [owner.id],
    ).unwrap()
    changed = next(grant for grant in updated.grants if grant.principal == reader)

    assert changed.grant_id == original.grant_id
    assert changed.principal == original.principal
    assert changed.permissions == {Permission.WRITE, Permission.UPDATE}


def test_update_grant_permissions_rejects_owner_grant_and_unauthorized_caller():
    owner = Principal(type=PrincipalType.USER, id="owner-1")
    reader = Principal(type=PrincipalType.USER, id="reader-1")
    policy = ResourcePolicy(account_id="acc-1", resource_id="ve:1").claim_principal(owner).unwrap()
    policy = policy.grant(reader, {Permission.READ}, [owner.id]).unwrap()
    owner_grant = next(grant for grant in policy.grants if grant.is_owner)
    reader_grant = next(grant for grant in policy.grants if grant.principal == reader)

    assert policy.update_grant_permissions(owner_grant.grant_id, {Permission.READ}, [owner.id]).is_err
    assert policy.update_grant_permissions(reader_grant.grant_id, {Permission.WRITE}, ["stranger"]).is_err
    assert policy.update_grant_permissions(reader_grant.grant_id, set(), [owner.id]).is_err

