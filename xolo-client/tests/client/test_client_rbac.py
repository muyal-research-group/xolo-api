from xolo.client.client import XoloClient
from xolo.client import models as M


def test_rbac_methods_return_expected_dtos(
    protected_client: XoloClient,
    make_signed_up_user,
    rand_name,
    unwrap_ok,
    unwrap_ok_list,
):
    user = make_signed_up_user()

    parent_role = unwrap_ok(
        protected_client.create_role(
            name=rand_name("parent-role"),
            description="parent role",
            permissions=["documents:read"],
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert parent_role.role_id
    assert "documents:read" in parent_role.permissions

    child_role = unwrap_ok(
        protected_client.create_role(
            name=rand_name("child-role"),
            description="child role",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert child_role.role_id

    roles = unwrap_ok_list(
        protected_client.list_roles(
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert any(item.role_id == child_role.role_id for item in roles)

    fetched_role = unwrap_ok(
        protected_client.get_role(
            role_id=child_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert fetched_role.role_id == child_role.role_id
    assert fetched_role.name == child_role.name

    updated_role = unwrap_ok(
        protected_client.update_role(
            role_id=child_role.role_id,
            name=rand_name("updated-role"),
            description="updated description",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert updated_role.role_id == child_role.role_id
    assert updated_role.description == "updated description"

    role_with_permission = unwrap_ok(
        protected_client.add_role_permission(
            role_id=child_role.role_id,
            permission="documents:write",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert "documents:write" in role_with_permission.permissions

    role_without_permission = unwrap_ok(
        protected_client.remove_role_permission(
            role_id=child_role.role_id,
            permission="documents:write",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert "documents:write" not in role_without_permission.permissions

    role_with_permission_again = unwrap_ok(
        protected_client.add_role_permission(
            role_id=child_role.role_id,
            permission="documents:write",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert "documents:write" in role_with_permission_again.permissions

    role_with_parent = unwrap_ok(
        protected_client.add_role_parent(
            role_id=child_role.role_id,
            parent_role_id=parent_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert parent_role.role_id in role_with_parent.parent_role_ids

    role_without_parent = unwrap_ok(
        protected_client.remove_role_parent(
            role_id=child_role.role_id,
            parent_role_id=parent_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert parent_role.role_id not in role_without_parent.parent_role_ids

    role_with_parent_again = unwrap_ok(
        protected_client.add_role_parent(
            role_id=child_role.role_id,
            parent_role_id=parent_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert parent_role.role_id in role_with_parent_again.parent_role_ids

    assignment = unwrap_ok(
        protected_client.assign_role(
            subject_id=user.user_key,
            role_id=child_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.AssignmentDTO,
    )
    assert assignment.subject_id == user.user_key
    assert assignment.role_id == child_role.role_id

    role_check = unwrap_ok(
        protected_client.has_role(
            subject_id=user.user_key,
            role_id=child_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.HasRoleDTO,
    )
    assert role_check.subject_id == user.user_key
    assert role_check.role_id == child_role.role_id
    assert role_check.has_role is True

    subject_roles = unwrap_ok_list(
        protected_client.get_subject_roles(
            subject_id=user.user_key,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RoleDTO,
    )
    assert any(item.role_id == child_role.role_id for item in subject_roles)

    checked_permission = unwrap_ok(
        protected_client.check_rbac_permission(
            subject_id=user.user_key,
            permission="documents:read",
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.RBACCheckResultDTO,
    )
    assert checked_permission.subject_id == user.user_key
    assert checked_permission.permission == "documents:read"
    assert checked_permission.has_access is True

    effective_permissions = unwrap_ok(
        protected_client.get_effective_permissions(
            subject_id=user.user_key,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.EffectivePermissionsDTO,
    )
    assert effective_permissions.subject_id == user.user_key
    assert "documents:read" in effective_permissions.permissions
    assert "documents:write" in effective_permissions.permissions

    unassigned_role = unwrap_ok(
        protected_client.unassign_role(
            subject_id=user.user_key,
            role_id=child_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.UnassignedRoleResponseDTO,
    )
    assert unassigned_role.ok is True
    assert unassigned_role.subject_id == user.user_key
    assert unassigned_role.role_id == child_role.role_id

    deleted_child_role = unwrap_ok(
        protected_client.delete_role(
            role_id=child_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.DeletedRoleResponseDTO,
    )
    assert deleted_child_role.ok is True
    assert deleted_child_role.role_id == child_role.role_id

    deleted_parent_role = unwrap_ok(
        protected_client.delete_role(
            role_id=parent_role.role_id,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.DeletedRoleResponseDTO,
    )
    assert deleted_parent_role.ok is True
    assert deleted_parent_role.role_id == parent_role.role_id
