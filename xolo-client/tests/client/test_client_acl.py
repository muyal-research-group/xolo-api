from xolo.client.client import XoloClient
from xolo.client import models as M


def test_acl_methods_return_expected_dtos(
    protected_client: XoloClient,
    make_signed_up_user,
    rand_name,
    unwrap_ok,
):
    shared_scope = rand_name("scope")
    created_scope = unwrap_ok(
        protected_client.create_scope(scope=shared_scope, secret=protected_client.secret),
        M.CreatedScopeResponseDTO,
    )
    assert created_scope.name == shared_scope.upper()

    owner = make_signed_up_user(scope=shared_scope)
    guest = make_signed_up_user(scope=shared_scope)

    dashboard = unwrap_ok(
        protected_client.get_users_resources(
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.UsersResourcesDTO,
    )
    assert dashboard.user_id == owner.user_key
    assert isinstance(dashboard.groups, list)
    assert isinstance(dashboard.owned_resources.items, list)
    assert isinstance(dashboard.shared_resources.items, list)

    direct_resource_id = rand_name("resource")
    claimed_resource = unwrap_ok(
        protected_client.claim_resource(
            resource_id=direct_resource_id,
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.ClaimedResourceResponseDTO,
    )
    assert claimed_resource.ok is True
    assert claimed_resource.resource_id == direct_resource_id

    denied_check = unwrap_ok(
        protected_client.check_permission_auth(
            resource_id=direct_resource_id,
            permissions=["read"],
            token=guest.auth.access_token,
            temporal_secret=guest.auth.temporal_secret,
        ),
        M.CheckPermissionResponseDTO,
    )
    assert denied_check.has_permission is False

    granted_permission = unwrap_ok(
        protected_client.grant_permission(
            resource_id=direct_resource_id,
            principal_id=guest.user_key,
            permissions=["read"],
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
            principal_type="USER",
        ),
        M.PermissionUpdateResponseDTO,
    )
    assert granted_permission.resource_id == direct_resource_id
    assert granted_permission.principal_id == guest.user_key
    assert granted_permission.permissions == ["read"]
    assert granted_permission.principal_type == "USER"

    allowed_check = unwrap_ok(
        protected_client.check_permission_auth(
            resource_id=direct_resource_id,
            permissions=["read"],
            token=guest.auth.access_token,
            temporal_secret=guest.auth.temporal_secret,
        ),
        M.CheckPermissionResponseDTO,
    )
    assert allowed_check.has_permission is True

    revoked_permission = unwrap_ok(
        protected_client.revoke_permission(
            resource_id=direct_resource_id,
            principal_id=guest.user_key,
            permissions=["read"],
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.PermissionUpdateResponseDTO,
    )
    assert revoked_permission.resource_id == direct_resource_id
    assert revoked_permission.principal_id == guest.user_key
    assert revoked_permission.permissions == ["read"]

    denied_after_revoke = unwrap_ok(
        protected_client.check_permission_auth(
            resource_id=direct_resource_id,
            permissions=["read"],
            token=guest.auth.access_token,
            temporal_secret=guest.auth.temporal_secret,
        ),
        M.CheckPermissionResponseDTO,
    )
    assert denied_after_revoke.has_permission is False

    group = unwrap_ok(
        protected_client.create_group(
            name=rand_name("group"),
            description="client-acl-group",
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.CreatedGroupResponseDTO,
    )
    assert group.ok is True
    assert group.group_id

    added_members = unwrap_ok(
        protected_client.add_members_to_group(
            group_id=group.group_id,
            members=[guest.user_key],
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.GroupMembersUpdateResponseDTO,
    )
    assert added_members.group_id == group.group_id
    assert added_members.members == [guest.user_key]

    is_member = unwrap_ok(
        protected_client.check_group_membership(
            group_id=group.group_id,
            user_id=guest.user_key,
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.GroupMembershipResponseDTO,
    )
    assert is_member.group_id == group.group_id
    assert is_member.user_id == guest.user_key
    assert is_member.is_member is True

    group_resource_id = rand_name("resource")
    claimed_group_resource = unwrap_ok(
        protected_client.claim_resource(
            resource_id=group_resource_id,
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.ClaimedResourceResponseDTO,
    )
    assert claimed_group_resource.resource_id == group_resource_id

    granted_group_permission = unwrap_ok(
        protected_client.grant_permission(
            resource_id=group_resource_id,
            principal_id=group.group_id,
            permissions=["read"],
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
            principal_type="GROUP",
        ),
        M.PermissionUpdateResponseDTO,
    )
    assert granted_group_permission.principal_id == group.group_id
    assert granted_group_permission.principal_type == "GROUP"

    allowed_via_group = unwrap_ok(
        protected_client.check_permission_auth(
            resource_id=group_resource_id,
            permissions=["read"],
            token=guest.auth.access_token,
            temporal_secret=guest.auth.temporal_secret,
        ),
        M.CheckPermissionResponseDTO,
    )
    assert allowed_via_group.has_permission is True

    removed_members = unwrap_ok(
        protected_client.remove_members_from_group(
            group_id=group.group_id,
            members=[guest.user_key],
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.GroupMembersUpdateResponseDTO,
    )
    assert removed_members.group_id == group.group_id
    assert removed_members.members == [guest.user_key]

    not_member = unwrap_ok(
        protected_client.check_group_membership(
            group_id=group.group_id,
            user_id=guest.user_key,
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.GroupMembershipResponseDTO,
    )
    assert not_member.is_member is False

    denied_after_member_removal = unwrap_ok(
        protected_client.check_permission_auth(
            resource_id=group_resource_id,
            permissions=["read"],
            token=guest.auth.access_token,
            temporal_secret=guest.auth.temporal_secret,
        ),
        M.CheckPermissionResponseDTO,
    )
    assert denied_after_member_removal.has_permission is False

    deleted_group = unwrap_ok(
        protected_client.delete_group(
            group_id=group.group_id,
            token=owner.auth.access_token,
            temporal_secret=owner.auth.temporal_secret,
        ),
        M.DeletedGroupResponseDTO,
    )
    assert deleted_group.ok is True
    assert deleted_group.group_id == group.group_id
