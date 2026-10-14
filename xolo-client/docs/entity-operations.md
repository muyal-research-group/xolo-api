# Entity operations

The refreshed client is designed around the entity groups exposed by the live OpenAPI contract.

## Accounts

- `list_accounts()`
- `create_account()`
- `delete_account()`

## Users

- `signup()`
- `auth()`
- `verify_token()`
- `logout()`
- `get_current_user()`
- `create_user()`
- `list_users()`
- `delete_user()`
- `block_user()`
- `unblock_user()`
- `enable_user()`
- `disable_user()`
- `request_password_recovery()`
- `confirm_password_recovery()`
- `introspect_session()` (trusted service)

## Scopes

- `create_scope()`
- `list_scopes()`
- `delete_scope()`
- `assign_scope()`
- `unassign_scope()`
- `list_scope_assignments()`

## Licenses

- `create_license()`
- `list_licenses()`
- `delete_license()`
- `self_delete_license()`

## API keys

- `create_api_key()`
- `list_api_keys()`
- `get_api_key()`
- `revoke_api_key()`
- `rotate_api_key()`

## ACL

- `get_users_resources()`
- `create_group()`
- `delete_group()`
- `add_members_to_group()`
- `remove_members_from_group()`
- `grant_permission()`
- `revoke_permission()`
- `claim_resource()`
- `check_permission_auth()`
- `check_group_membership()`

Trusted service variants are prefixed with `service_` and cover claims, grants, revocations, effective access, grant lists, user-visible resources, ownership transfers, policy deletion, and group lifecycle operations. See [Service mode](service-mode.md).

## ABAC

- `create_abac_policy()`
- `list_abac_policies()`
- `get_abac_policy()`
- `delete_abac_policy()`
- `evaluate_abac()`

## NGAC

- `create_ngac_node()`
- `list_ngac_nodes()`
- `get_ngac_node()`
- `delete_ngac_node()`
- `ngac_assign()`
- `ngac_remove_assignment()`
- `list_ngac_assignments()`
- `ngac_associate()`
- `ngac_remove_association()`
- `list_ngac_associations()`
- `ngac_check()`

## RBAC

- `create_role()`
- `list_roles()`
- `get_role()`
- `update_role()`
- `delete_role()`
- `add_role_permission()`
- `remove_role_permission()`
- `add_role_parent()`
- `remove_role_parent()`
- `assign_role()`
- `unassign_role()`
- `get_subject_roles()`
- `get_effective_permissions()`
- `has_role()`
- `check_rbac_permission()`
