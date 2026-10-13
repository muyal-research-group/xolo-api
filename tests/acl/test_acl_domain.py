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

