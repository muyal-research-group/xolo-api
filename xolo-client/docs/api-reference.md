# API Reference

Complete reference for every public method on `XoloClient`. Every method returns `Result[SuccessDTO, XoloError]`; call `.unwrap()` on success or `.unwrap_err()` on failure.

---

## Constructor

### `XoloClient(account_id, api_key, api_url, secret, admin_token)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `account_id` | `str` | — | Account identifier used in all account-scoped routes. |
| `api_key` | `str` | — | Default API key for API-key-protected operations. |
| `api_url` | `str` | `"http://localhost:10000/api/v4"` | Base API root. |
| `secret` | `str` | `""` | Legacy compatibility field retained for older callers. |
| `admin_token` | `str` | `""` | Admin token for administration endpoints. |

**Returns:** configured `XoloClient` instance. Raises `ValueError` if `account_id` is empty.

---

## Core(Experimental)
!!! note "Experimental Feature"
    This feature is currently experimental. 
    It is subject to change or removal in future releases.



### `execute_script(script_text)`

Parses and executes an Xolo-CL DSL script, running each command against the client.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `script_text` | `str` | — | Full script text to parse and execute. |

**Returns:** `list` — one result entry per parsed command.

---

### `base_url()`

Returns the account-scoped base URL built from `api_url` and `account_id`.

**Returns:** `str` — e.g. `http://localhost:10000/api/v4/accounts/my-account`.

---

## Accounts

> **Auth:** `X-Admin-Token` (required for all methods in this section).

### `list_accounts(admin_token)`

Lists all accounts visible to the admin token.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[AccountDTO], XoloError]`

`AccountDTO` fields: `account_id`, `name`, `created_at`.

---

### `create_account(account_id, name, admin_token)`

Creates a new account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `account_id` | `str` | — | Unique identifier for the new account. |
| `name` | `str` | — | Human-readable account name. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[AccountDTO, XoloError]`

---

### `delete_account(account_id, admin_token)`

Deletes an account by identifier.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `account_id` | `str` | — | Identifier of the account to delete. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedAccountResponseDTO, XoloError]`

`DeletedAccountResponseDTO` fields: `ok`, `account_id`.

---

## Users

### `signup(username, first_name, last_name, email, password, scope, profile_photo, expiration, api_key)`

> **Auth:** `X-API-Key` (required).

Registers a new end user within the account and issues a verification token.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Unique username for the new user. |
| `first_name` | `str` | — | User's first name. |
| `last_name` | `str` | — | User's last name. |
| `email` | `str` | — | User's email address. |
| `password` | `str` | — | Plain-text password (hashed server-side). |
| `scope` | `str` | — | Initial scope requested during signup. |
| `profile_photo` | `str` | `""` | Optional profile photo URL. |
| `expiration` | `str` | `"1h"` | Access-token expiration hint, e.g. `"1h"`, `"1d"`. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[CreatedUserResponseDTO, XoloError]`

`CreatedUserResponseDTO` fields: `key` (the new user's internal ID).

---

### `create_user(username, first_name, last_name, email, password, profile_photo, admin_token, role)`

> **Auth:** `X-Admin-Token` (required).

Creates a user through the admin API, bypassing the signup verification flow.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Unique username for the new user. |
| `first_name` | `str` | — | User's first name. |
| `last_name` | `str` | — | User's last name. |
| `email` | `str` | — | User's email address. |
| `password` | `str` | — | Plain-text password (hashed server-side). |
| `profile_photo` | `str` | `""` | Optional profile photo URL. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |
| `role` | `str \| None` | `None` | Legacy compatibility field; ignored by the current API. |

**Returns:** `Result[CreatedUserResponseDTO, XoloError]`

---

### `list_users(admin_token)`

> **Auth:** `X-Admin-Token` (required).

Lists all users in the account with full profile data.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[UserDTO], XoloError]`

`UserDTO` fields: `key`, `username`, `first_name`, `last_name`, `email`, `profile_photo`, `disabled`.

---

### `list_users_discovery(admin_token)`

> **Auth:** `X-Admin-Token` (required).

Lightweight user list intended for dropdowns and autocomplete widgets. Same data as `list_users` but served from a separate discovery endpoint.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[UserDTO], XoloError]`

---

### `delete_user(username, api_key)`

> **Auth:** `X-API-Key` (required). The key must have the `users` (or `all`) scope and belong to the same account.

Deletes a user and all related data (licenses, scope assignments, sessions, ACL policies, security groups, NGAC nodes).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username to delete. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | **Deprecated.** Ignored. Pass `api_key` instead. |

**Returns:** `Result[DeletedUserResponseDTO, XoloError]`

`DeletedUserResponseDTO` fields: `ok`, `username`.

---

### `block_user(username, admin_token)`

> **Auth:** `X-Admin-Token` (required).

Blocks a user, preventing authentication.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username to block. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[BlockedUserResponseDTO, XoloError]`

`BlockedUserResponseDTO` fields: `ok`, `username`.

---

### `unblock_user(username, admin_token)`

> **Auth:** `X-Admin-Token` (required).

Restores a blocked user's ability to authenticate.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username to unblock. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[UnblockedUserResponseDTO, XoloError]`

`UnblockedUserResponseDTO` fields: `ok`, `username`.

---

### `enable_user(username, token, temporal_secret)`

> **Auth:** `Authorization: Bearer` + `Temporal-Secret-Key`. The caller can only enable their own account.

Re-enables a previously disabled user account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username to enable (must match the token's owner). |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |

**Returns:** `Result[UserEnabledResponseDTO, XoloError]`

`UserEnabledResponseDTO` fields: `ok`, `username`.

---

### `disable_user(username, token, temporal_secret)`

> **Auth:** `Authorization: Bearer` + `Temporal-Secret-Key`. The caller can only disable their own account.

Disables a user account without deleting it.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username to disable (must match the token's owner). |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |

**Returns:** `Result[UserDisabledResponseDTO, XoloError]`

`UserDisabledResponseDTO` fields: `ok`, `username`.

---

### `auth(username, password, scope, expiration, renew_token, api_key)`

> **Auth:** `X-API-Key` (required).

Authenticates a user and returns an access token and temporal secret.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username to authenticate. |
| `password` | `str` | — | Plain-text password. |
| `scope` | `str` | — | Scope to authenticate against. |
| `expiration` | `str` | `"1h"` | Token lifetime hint, e.g. `"15min"`, `"1d"`. |
| `renew_token` | `bool` | `False` | If `True`, issues a renewable session token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[AuthenticatedDTO, XoloError]`

`AuthenticatedDTO` fields: `username`, `first_name`, `last_name`, `email`, `profile_photo`, `access_token`, `temporal_secret`, `metadata`, `user_id`.

---

### `verify_token(access_token, username, secret)`

> **Auth:** none.

Verifies that an issued access token is valid.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `access_token` | `str` | — | The access token to verify. |
| `username` | `str` | — | Username the token was issued to. |
| `secret` | `str` | `""` | Temporal secret associated with the token. |

**Returns:** `Result[VerifyTokenResponseDTO, XoloError]`

`VerifyTokenResponseDTO` fields: `ok`, `username`, `access_token`.

---

### `get_current_user(token, temporal_secret)`

> **Auth:** `Authorization: Bearer` + `Temporal-Secret-Key`.

Returns the profile of the currently authenticated user.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |

**Returns:** `Result[UserDTO, XoloError]`

---

### `logout(username, access_token, token, temporal_secret)`

> **Auth:** `Authorization: Bearer` + `Temporal-Secret-Key`. Callers can only log out their own session.

Revokes the session represented by `access_token`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username of the session owner. |
| `access_token` | `str` | — | The access token to revoke. |
| `token` | `str` | — | Bearer token used to authorize the logout request. |
| `temporal_secret` | `str` | — | Temporal secret for the authorizing bearer token. |

**Returns:** `Result[OperationResultDTO, XoloError]`

`OperationResultDTO` fields: `ok`.

---

### `request_password_recovery(identifier)`

> **Auth:** none.

Starts the password-reset flow by sending a reset token to the user.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `identifier` | `str` | — | Username or email address of the target account. |

**Returns:** `Result[OperationResultDTO, XoloError]`

---

### `confirm_password_recovery(token, password)`

> **Auth:** none.

Completes the password-reset flow using the reset token.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Reset token received via email. |
| `password` | `str` | — | New plain-text password. |

**Returns:** `Result[OperationResultDTO, XoloError]`

---

### `update_user_password(username, password, secret)`

> **Auth:** none.

Compatibility wrapper for `confirm_password_recovery`. The `secret` parameter carries the reset token; `username` is accepted but ignored.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Ignored; retained for backwards compatibility. |
| `password` | `str` | — | New plain-text password. |
| `secret` | `str` | `""` | Reset token (formerly the admin secret). Required. |

**Returns:** `Result[UpdateUserPasswordResponseDTO, XoloError]`

`UpdateUserPasswordResponseDTO` fields: `ok`.

---

## Scopes

> **Auth:** `X-Admin-Token` (required for all methods except `list_scopes_discovery`).

### `create_scope(scope, secret, admin_token)`

Creates a scope within the account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scope` | `str` | — | Scope name to create. Stored uppercased. |
| `secret` | `str` | `""` | Legacy compatibility field; ignored. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[CreatedScopeResponseDTO, XoloError]`

`CreatedScopeResponseDTO` fields: `name` (uppercased).

---

### `list_scopes(admin_token)`

Lists all scopes defined in the account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[CreatedScopeResponseDTO], XoloError]`

---

### `delete_scope(scope, admin_token)`

Deletes a scope by name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scope` | `str` | — | Scope name to delete. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedScopeResponseDTO, XoloError]`

`DeletedScopeResponseDTO` fields: `ok`, `name`.

---

### `assign_scope(username, scope, secret, admin_token)`

Assigns a scope to a user.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username receiving the scope. |
| `scope` | `str` | — | Scope name to assign. |
| `secret` | `str` | — | Legacy compatibility field; ignored. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[AssignedScopeResponseDTO, XoloError]`

`AssignedScopeResponseDTO` fields: `ok`, `name` (uppercased), `username`.

---

### `unassign_scope(username, scope, admin_token)`

Removes a scope assignment from a user.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username losing the scope. |
| `scope` | `str` | — | Scope name to remove. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[UnassignedScopeResponseDTO, XoloError]`

`UnassignedScopeResponseDTO` fields: `ok`, `name`, `username`.

---

### `list_scope_assignments(admin_token)`

Lists all scope-to-user assignments in the account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[AssignedScopeResponseDTO], XoloError]`

---

### `list_scopes_discovery(api_key)`

> **Auth:** `X-API-Key` (required).

Lightweight scope list for dropdowns and autocomplete. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

## Licenses

> **Auth:** `X-Admin-Token` (required for all methods except `self_delete_license`).

### `create_license(username, scope, secret, expires_in, force, admin_token)`

Issues a license (JWT token grant) to a user for a specific scope.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username receiving the license. |
| `scope` | `str` | — | Scope name the license is issued for. |
| `secret` | `str` | — | Legacy compatibility field; ignored. |
| `expires_in` | `str` | `"1h"` | Relative duration string, e.g. `"1d"`, `"2h"`, `"30min"`. |
| `force` | `bool` | `True` | If `True`, replaces any existing license for the same user+scope. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[AssignLicenseResponseDTO, XoloError]`

`AssignLicenseResponseDTO` fields: `ok`, `expires_at` (ISO-8601 string).

---

### `list_licenses(admin_token)`

Lists all active licenses in the account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[LicenseDTO], XoloError]`

`LicenseDTO` fields: `username`, `scope`, `expires_at`, `issued_at`.

---

### `delete_license(username, scope, force, secret, admin_token)`

Revokes a user's license for a specific scope.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username whose license is revoked. |
| `scope` | `str` | — | Scope name of the license to revoke. |
| `force` | `bool` | `True` | If `True`, forces deletion even if the license is in use. |
| `secret` | `str` | `""` | Legacy compatibility field; ignored. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedLicenseResponseDTO, XoloError]`

`DeletedLicenseResponseDTO` fields: `ok`.

---

### `self_delete_license(username, scope, token, secret, force)`

> **Auth:** none (the license JWT itself proves identity).

Allows a user to revoke their own license without admin involvement.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username deleting the license (must match the token's owner). |
| `scope` | `str` | — | Scope name of the license to revoke. |
| `token` | `str` | — | The access token associated with the license. |
| `secret` | `str` | — | Temporal secret key issued with the access token. |
| `force` | `bool` | `True` | If `True`, forces deletion even if the license is in use. |

**Returns:** `Result[DeletedLicenseResponseDTO, XoloError]`

---

### `rotate_license(username, scope, expires_in, admin_token)`

Re-issues an existing license with a new expiration, invalidating the previous one.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Username whose license is rotated. |
| `scope` | `str` | — | Scope name of the license to rotate. |
| `expires_in` | `str` | — | New duration string for the re-issued license, e.g. `"7d"`. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[AssignLicenseResponseDTO, XoloError]`

---

## API Keys

> **Auth:** `X-Admin-Token` (required for all methods in this section).

### `create_api_key(name, scopes, expires_at, admin_token)`

Creates an API key for the account. The raw key value is returned only once.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Human-readable label for the key. |
| `scopes` | `list[str \| APIKeyScope]` | — | List of scopes the key can access. Trusted automation must include `"service"` explicitly; `"all"` does not include it. |
| `expires_at` | `str \| None` | `None` | Optional RFC 3339 expiration timestamp. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[CreatedAPIKeyResponseDTO, XoloError]`

`CreatedAPIKeyResponseDTO` fields: `account_id`, `key_id`, `key` (raw — store securely), `key_prefix`, `name`, `scopes`, `expires_at`, `created_at`.

---

### `list_api_keys(admin_token)`

Lists API key metadata for the account. Raw key values are never returned.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[APIKeyMetadataDTO], XoloError]`

`APIKeyMetadataDTO` fields: `account_id`, `key_id`, `key_prefix`, `name`, `scopes`, `is_active`, `created_at`, `expires_at`, `last_used_at`.

---

### `get_api_key(key_id, admin_token)`

Fetches metadata for a single API key.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_id` | `str` | — | API key identifier. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[APIKeyMetadataDTO, XoloError]`

---

### `revoke_api_key(key_id, admin_token)`

Permanently revokes an API key.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_id` | `str` | — | Identifier of the key to revoke. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RevokedAPIKeyResponseDTO, XoloError]`

`RevokedAPIKeyResponseDTO` fields: `ok`, `key_id`.

---

### `rotate_api_key(key_id, admin_token)`

Issues a new secret for an existing API key, invalidating the previous one. The new raw key is returned only once.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_id` | `str` | — | Identifier of the key to rotate. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RotatedAPIKeyResponseDTO, XoloError]`

`RotatedAPIKeyResponseDTO` fields: `account_id`, `key_id`, `key` (raw — store securely), `key_prefix`.

---

## ACL

> **Auth (CRUD):** `Authorization: Bearer` + `Temporal-Secret-Key` + at least one of `X-API-Key` or `X-Admin-Token`.
>
> **Auth (discovery):** `X-API-Key` only.

### `get_users_resources(token, temporal_secret, owned_page, owned_page_size, shared_page, shared_page_size, api_key, admin_token)`

Returns all resources visible to the authenticated user, split into owned and shared, with pagination on each set.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `owned_page` | `int` | `1` | Page number for owned resources. |
| `owned_page_size` | `int` | `10` | Page size for owned resources. |
| `shared_page` | `int` | `1` | Page number for shared resources. |
| `shared_page_size` | `int` | `10` | Page size for shared resources. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[UsersResourcesDTO, XoloError]`

`UsersResourcesDTO` fields: `user_id`, `groups` (`list[GroupDetailDTO]`), `owned_resources` (`PaginatedDTO[ResourceDetailDTO]`), `shared_resources` (`PaginatedDTO[ResourceDetailDTO]`).

---

### `create_group(name, description, token, temporal_secret, api_key, admin_token)`

Creates an ACL security group.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Group name. |
| `description` | `str` | — | Human-readable group description. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[CreatedGroupResponseDTO, XoloError]`

`CreatedGroupResponseDTO` fields: `ok`, `group_id`.

---

### `delete_group(group_id, token, temporal_secret, api_key, admin_token)`

Deletes an ACL security group.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_id` | `str` | — | Group identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedGroupResponseDTO, XoloError]`

`DeletedGroupResponseDTO` fields: `ok`, `group_id`.

---

### `add_members_to_group(group_id, members, token, temporal_secret, api_key, admin_token)`

Adds one or more user IDs to a security group.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_id` | `str` | — | Group identifier. |
| `members` | `list[str]` | — | User identifiers to add. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[GroupMembersUpdateResponseDTO, XoloError]`

`GroupMembersUpdateResponseDTO` fields: `ok`, `group_id`, `members`.

---

### `remove_members_from_group(group_id, members, token, temporal_secret, api_key, admin_token)`

Removes one or more user IDs from a security group.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_id` | `str` | — | Group identifier. |
| `members` | `list[str]` | — | User identifiers to remove. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[GroupMembersUpdateResponseDTO, XoloError]`

---

### `grant_permission(resource_id, principal_id, permissions, token, temporal_secret, principal_type, api_key, admin_token)`

Grants ACL permissions to a user or group on a resource.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resource_id` | `str` | — | Identifier of the resource to protect. |
| `principal_id` | `str` | — | User or group identifier receiving the permissions. |
| `permissions` | `list[str]` | — | Permissions to grant, e.g. `["read", "write"]`. Valid values: `read`, `write`, `delete`, `sys:manage`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `principal_type` | `str` | `"USER"` | Principal kind: `"USER"` or `"GROUP"`. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[PermissionUpdateResponseDTO, XoloError]`

`PermissionUpdateResponseDTO` fields: `ok`, `resource_id`, `principal_id`, `principal_type`, `permissions`.

---

### `revoke_permission(resource_id, principal_id, permissions, token, temporal_secret, principal_type, api_key, admin_token)`

Revokes ACL permissions from a user or group on a resource.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resource_id` | `str` | — | Identifier of the target resource. |
| `principal_id` | `str` | — | User or group identifier losing the permissions. |
| `permissions` | `list[str]` | — | Permissions to revoke. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `principal_type` | `str` | `"USER"` | Principal kind: `"USER"` or `"GROUP"`. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[PermissionUpdateResponseDTO, XoloError]`

---

### `claim_resource(resource_id, token, temporal_secret, api_key, admin_token)`

Claims exclusive ownership of a resource. A resource can only be claimed once.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resource_id` | `str` | — | Identifier of the resource to claim. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[ClaimedResourceResponseDTO, XoloError]`

`ClaimedResourceResponseDTO` fields: `ok`, `resource_id`.

---

### `check_permission_auth(resource_id, permissions, token, temporal_secret, api_key, admin_token)`

Checks whether the authenticated caller holds the specified permissions on a resource.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resource_id` | `str` | — | Resource to check. |
| `permissions` | `list[str]` | — | Permissions to verify. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[CheckPermissionResponseDTO, XoloError]`

`CheckPermissionResponseDTO` fields: `has_permission`.

---

### `check_group_membership(group_id, user_id, token, temporal_secret, api_key, admin_token)`

Checks whether a user is a member of a group.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_id` | `str` | — | Group identifier. |
| `user_id` | `str` | — | User identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[GroupMembershipResponseDTO, XoloError]`

`GroupMembershipResponseDTO` fields: `user_id`, `group_id`, `is_member`.

---

### `list_acl_groups_discovery(api_key)`

Lightweight group list for dropdowns. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_acl_principals_discovery(api_key)`

Lightweight principal list for dropdowns. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_acl_resources_discovery(api_key)`

Lightweight resource list for dropdowns. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

## ABAC

> **Auth (CRUD + evaluate):** `Authorization: Bearer` + `Temporal-Secret-Key` + at least one of `X-API-Key` or `X-Admin-Token`.
>
> **Auth (discovery):** `X-API-Key` only.

See [Data types](#data-types) for `GeoPointDTO`, `GeoZoneDTO`, and `TimeWindowMode`.

### `create_abac_policy(name, effect, events, token, temporal_secret, api_key, admin_token)`

Creates an account-scoped ABAC policy containing one or more event rules.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Human-readable policy name. |
| `effect` | `str \| Effect` | — | `"ALLOW"` or `"DENY"`. |
| `events` | `list[dict]` | — | List of event rule dicts. See event shape below. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Event dict shape:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subject` | `str` | — | Subject pattern, e.g. `"Doctor"` or `"*"` for wildcard. |
| `resource` | `str` | — | Resource pattern, e.g. `"Chart"` or `"*"` for wildcard. |
| `action` | `str` | — | Action pattern, e.g. `"read"` or `"*"` for wildcard. |
| `location` | `dict \| None` | `None` | `GeoZoneDTO` dict `{lat, lng, radius_km}` or `None` for wildcard. |
| `time_mode` | `str` | `"wildcard"` | One of `"wildcard"`, `"datetime"`, `"time_of_day"`, `"date"`. |
| `time_start` | `str \| None` | `None` | Start bound; format depends on `time_mode`. |
| `time_end` | `str \| None` | `None` | End bound; format depends on `time_mode`. |

**Returns:** `Result[CreatedABACPolicyResponseDTO, XoloError]`

`CreatedABACPolicyResponseDTO` fields: `ok`, `policy_id`.

---

### `list_abac_policies(token, temporal_secret, api_key, admin_token)`

Lists all ABAC policies in the account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[ABACPolicyDTO], XoloError]`

`ABACPolicyDTO` fields: `policy_id`, `name`, `effect`, `events` (`list[ABACEventRecordDTO]`), `created_at`.

---

### `get_abac_policy(policy_id, token, temporal_secret, api_key, admin_token)`

Fetches a single ABAC policy by identifier.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `policy_id` | `str` | — | Policy identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[ABACPolicyDTO, XoloError]`

---

### `delete_abac_policy(policy_id, token, temporal_secret, api_key, admin_token)`

Deletes an ABAC policy.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `policy_id` | `str` | — | Policy identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedABACPolicyResponseDTO, XoloError]`

`DeletedABACPolicyResponseDTO` fields: `ok`, `policy_id`.

---

### `evaluate_abac(subject, resource, action, token, temporal_secret, location, time, api_key, admin_token)`

Evaluates an ABAC access request against all account policies. DENY overrides ALLOW; no match defaults to DENY.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject` | `str` | — | Subject identifier to evaluate, e.g. `"Doctor"`. |
| `resource` | `str` | — | Resource identifier to evaluate, e.g. `"Chart"`. |
| `action` | `str` | — | Action being requested, e.g. `"read"`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `location` | `GeoPointDTO \| None` | `None` | Caller's current geo-point `{lat, lng}`. `None` = wildcard pass (location not declared). |
| `time` | `str \| None` | `None` | Current time as ISO-8601 string, e.g. `"2026-05-13T14:30"`. `None` = wildcard pass. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[ABACDecisionDTO, XoloError]`

`ABACDecisionDTO` fields: `allowed`, `matched_policy`, `matched_event`, `reason`.

---

### `list_abac_policies_discovery(api_key)`

Lightweight policy list for dropdowns. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_abac_subjects_discovery(api_key)`

Lightweight subject list for dropdowns.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_abac_resources_discovery(api_key)`

Lightweight resource list for dropdowns.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_abac_locations_discovery(api_key)`

Lightweight location list for dropdowns.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

## NGAC

> **Auth (CRUD + check):** `Authorization: Bearer` + `Temporal-Secret-Key` + at least one of `X-API-Key` or `X-Admin-Token`.
>
> **Auth (discovery):** `X-API-Key` only.

### `create_ngac_node(name, node_type, token, temporal_secret, properties, api_key, admin_token)`

Creates an NGAC graph node.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Node display name. |
| `node_type` | `str \| NodeType` | — | One of `"user"`, `"object"`, `"user_attribute"`, `"object_attribute"`, `"policy_class"`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `properties` | `dict \| None` | `None` | Arbitrary key-value metadata attached to the node. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[CreatedNGACNodeResponseDTO, XoloError]`

`CreatedNGACNodeResponseDTO` fields: `ok`, `node_id`.

---

### `list_ngac_nodes(token, temporal_secret, node_type, api_key, admin_token)`

Lists NGAC nodes, optionally filtered by type.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `node_type` | `str \| None` | `None` | If set, filters results to this node type. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[NGACNodeDTO], XoloError]`

`NGACNodeDTO` fields: `node_id`, `node_type`, `name`, `properties`, `created_at`.

---

### `get_ngac_node(node_id, token, temporal_secret, api_key, admin_token)`

Fetches a single NGAC node by identifier.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | `str` | — | Node identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[NGACNodeDTO, XoloError]`

---

### `delete_ngac_node(node_id, token, temporal_secret, api_key, admin_token)`

Deletes an NGAC node and cascades removal of its assignments.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | `str` | — | Node identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedNGACNodeResponseDTO, XoloError]`

`DeletedNGACNodeResponseDTO` fields: `ok`, `node_id`.

---

### `ngac_assign(from_id, to_id, token, temporal_secret, api_key, admin_token)`

Creates a directed assignment edge from a child node to a parent node.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from_id` | `str` | — | Child node identifier (e.g. a `user` or `object`). |
| `to_id` | `str` | — | Parent node identifier (e.g. a `user_attribute`). |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[NGACAssignmentMutationResponseDTO, XoloError]`

`NGACAssignmentMutationResponseDTO` fields: `ok`, `from_id`, `to_id`.

---

### `ngac_remove_assignment(from_id, to_id, token, temporal_secret, api_key, admin_token)`

Removes an assignment edge between two nodes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from_id` | `str` | — | Child node identifier. |
| `to_id` | `str` | — | Parent node identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[NGACAssignmentMutationResponseDTO, XoloError]`

---

### `list_ngac_assignments(token, temporal_secret, api_key, admin_token)`

Lists all assignment edges in the account's NGAC graph.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[NGACAssignmentDTO], XoloError]`

`NGACAssignmentDTO` fields: `assignment_id`, `from_id`, `to_id`, `created_at`.

---

### `ngac_associate(user_attribute_id, object_attribute_id, operations, token, temporal_secret, api_key, admin_token)`

Creates an association granting a user-attribute permission over an object-attribute.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_attribute_id` | `str` | — | User-attribute node identifier. |
| `object_attribute_id` | `str` | — | Object-attribute node identifier. |
| `operations` | `list[str]` | — | Operations granted, e.g. `["read", "write"]`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[NGACAssociationMutationResponseDTO, XoloError]`

`NGACAssociationMutationResponseDTO` fields: `ok`, `user_attribute_id`, `object_attribute_id`, `operations`.

---

### `ngac_remove_association(association_id, token, temporal_secret, api_key, admin_token)`

Deletes an association by its identifier.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `association_id` | `str` | — | Association identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[NGACAssociationDeletionResponseDTO, XoloError]`

`NGACAssociationDeletionResponseDTO` fields: `ok`, `association_id`.

---

### `list_ngac_associations(token, temporal_secret, api_key, admin_token)`

Lists all associations in the account's NGAC graph.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[NGACAssociationDTO], XoloError]`

`NGACAssociationDTO` fields: `association_id`, `user_attribute_id`, `object_attribute_id`, `operations`, `created_at`.

---

### `ngac_check(user_id, object_id, operation, token, temporal_secret, api_key, admin_token)`

Evaluates whether a user has access to an object for a given operation using the NGAC AND rule: access is granted only if the user satisfies every Policy Class governing the object.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | `str` | — | User node identifier. |
| `object_id` | `str` | — | Object node identifier. |
| `operation` | `str` | — | Operation to check, e.g. `"read"`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[NGACDecisionDTO, XoloError]`

`NGACDecisionDTO` fields: `allowed`, `reason`, `user_id`, `object_id`, `operation`.

---

### `list_ngac_nodes_discovery(api_key)`

Lightweight node list for dropdowns. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_ngac_assignments_discovery(api_key)`

Lightweight assignment list for dropdowns.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_ngac_associations_discovery(api_key)`

Lightweight association list for dropdowns.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

## RBAC

> **Auth:** `Authorization: Bearer` + `Temporal-Secret-Key` + at least one of `X-API-Key` or `X-Admin-Token`.
>
> **Auth (discovery):** `X-API-Key` only.

### `create_role(name, token, temporal_secret, description, permissions, api_key, admin_token)`

Creates an RBAC role.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Role display name. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `description` | `str \| None` | `None` | Optional human-readable description. |
| `permissions` | `list[str] \| None` | `None` | Initial permission strings, e.g. `["documents:read"]`. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

`RoleDTO` fields: `role_id`, `name`, `description`, `permissions`, `parent_role_ids`.

---

### `list_roles(token, temporal_secret, api_key, admin_token)`

Lists all RBAC roles in the account.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[RoleDTO], XoloError]`

---

### `get_role(role_id, token, temporal_secret, api_key, admin_token)`

Fetches a single role by identifier.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Role identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

---

### `update_role(role_id, token, temporal_secret, name, description, api_key, admin_token)`

Updates a role's name or description.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Role identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `name` | `str \| None` | `None` | New name; omit to leave unchanged. |
| `description` | `str \| None` | `None` | New description; omit to leave unchanged. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

---

### `delete_role(role_id, token, temporal_secret, api_key, admin_token)`

Deletes a role.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Role identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[DeletedRoleResponseDTO, XoloError]`

`DeletedRoleResponseDTO` fields: `ok`, `role_id`.

---

### `add_role_permission(role_id, permission, token, temporal_secret, api_key, admin_token)`

Adds a single permission string to a role.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Role identifier. |
| `permission` | `str` | — | Permission string to add, e.g. `"documents:write"`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

---

### `remove_role_permission(role_id, permission, token, temporal_secret, api_key, admin_token)`

Removes a single permission string from a role.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Role identifier. |
| `permission` | `str` | — | Permission string to remove. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

---

### `add_role_parent(role_id, parent_role_id, token, temporal_secret, api_key, admin_token)`

Establishes role inheritance: `role_id` inherits all permissions from `parent_role_id`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Child role identifier. |
| `parent_role_id` | `str` | — | Parent role identifier to inherit from. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

---

### `remove_role_parent(role_id, parent_role_id, token, temporal_secret, api_key, admin_token)`

Removes a role inheritance link.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role_id` | `str` | — | Child role identifier. |
| `parent_role_id` | `str` | — | Parent role identifier to remove. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RoleDTO, XoloError]`

---

### `assign_role(subject_id, role_id, token, temporal_secret, subject_type, api_key, admin_token)`

Assigns a role to a subject.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject_id` | `str` | — | Subject identifier (user key or group id). |
| `role_id` | `str` | — | Role identifier to assign. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `subject_type` | `str` | `"user"` | Subject type: `"user"` or `"group"`. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[AssignmentDTO, XoloError]`

`AssignmentDTO` fields: `assignment_id`, `subject_id`, `role_id`.

---

### `unassign_role(subject_id, role_id, token, temporal_secret, api_key, admin_token)`

Removes a role assignment from a subject.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject_id` | `str` | — | Subject identifier. |
| `role_id` | `str` | — | Role identifier to remove. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[UnassignedRoleResponseDTO, XoloError]`

`UnassignedRoleResponseDTO` fields: `ok`, `subject_id`, `role_id`.

---

### `get_subject_roles(subject_id, token, temporal_secret, api_key, admin_token)`

Lists all roles currently assigned to a subject.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject_id` | `str` | — | Subject identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[list[RoleDTO], XoloError]`

---

### `check_rbac_permission(subject_id, permission, token, temporal_secret, api_key, admin_token)`

Checks whether a subject holds a specific permission, including inherited permissions from parent roles.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject_id` | `str` | — | Subject identifier. |
| `permission` | `str` | — | Permission string to check, e.g. `"documents:read"`. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[RBACCheckResultDTO, XoloError]`

`RBACCheckResultDTO` fields: `subject_id`, `permission`, `has_access`.

---

### `get_effective_permissions(subject_id, token, temporal_secret, api_key, admin_token)`

Returns the full set of permissions a subject holds, including those inherited from parent roles.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject_id` | `str` | — | Subject identifier. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[EffectivePermissionsDTO, XoloError]`

`EffectivePermissionsDTO` fields: `subject_id`, `permissions` (deduplicated, includes inherited).

---

### `has_role(subject_id, role_id, token, temporal_secret, api_key, admin_token)`

Checks whether a subject has a specific role, including roles inherited via group membership.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subject_id` | `str` | — | Subject identifier. |
| `role_id` | `str` | — | Role identifier to check. |
| `token` | `str` | — | Bearer access token. |
| `temporal_secret` | `str` | — | Temporal secret issued alongside the access token. |
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |
| `admin_token` | `str` | `""` | Overrides the client-level admin token for this call. |

**Returns:** `Result[HasRoleDTO, XoloError]`

`HasRoleDTO` fields: `subject_id`, `role_id`, `has_role`.

---

### `list_rbac_roles_discovery(api_key)`

Lightweight role list for dropdowns. Returns `{id, name}` pairs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---

### `list_rbac_permissions_discovery(api_key)`

Lightweight permission list for dropdowns.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Overrides the client-level API key for this call. |

**Returns:** `Result[list[dict], XoloError]`

---


## Data types

### `GeoPointDTO`

Represents a geographic coordinate used in ABAC evaluation requests.

| Field | Type | Description |
|-------|------|-------------|
| `lat` | `float` | Latitude in decimal degrees. |
| `lng` | `float` | Longitude in decimal degrees. |

```python
from xolo.client.models import GeoPointDTO

location = GeoPointDTO(lat=19.43, lng=-99.13)
```

---

### `GeoZoneDTO`

Represents a geographic zone used in ABAC policy event rules.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lat` | `float` | — | Center latitude in decimal degrees. |
| `lng` | `float` | — | Center longitude in decimal degrees. |
| `radius_km` | `float` | `1.0` | Zone radius in kilometres. Must be `> 0` and `≤ 5.0`. |

```python
from xolo.client.models import GeoZoneDTO

zone = GeoZoneDTO(lat=19.43, lng=-99.13, radius_km=2.0)
```

---

### `TimeWindowMode`

Controls how `time_start` and `time_end` are interpreted in an ABAC event rule.

| Value | `time_start` / `time_end` format | Behaviour |
|-------|----------------------------------|-----------|
| `"wildcard"` | both `None` | Always matches; time is not restricted. |
| `"datetime"` | `"YYYY-MM-DDTHH:MM"` | Full datetime range check. |
| `"time_of_day"` | `"HH:MM"` | Recurring daily window; supports midnight-spanning ranges. |
| `"date"` | `"YYYY-MM-DD"` | Date range only; time of day is ignored. |

---

### `Effect`

| Value | Meaning |
|-------|---------|
| `"ALLOW"` | The policy permits the matched request. |
| `"DENY"` | The policy denies the matched request. DENY always overrides ALLOW. |

---

### `NodeType`

Valid values for the `node_type` parameter in NGAC node methods.

| Value | Role |
|-------|------|
| `"user"` | A subject leaf node. Can only be assigned to `user_attribute`. |
| `"object"` | A resource leaf node. Can only be assigned to `object_attribute`. |
| `"user_attribute"` | Groups users into a named category. |
| `"object_attribute"` | Groups objects into a named category. |
| `"policy_class"` | Root of a policy domain. Associations terminate here. |

---

### `APIKeyScope`

Valid scope values for `create_api_key`.

| Value | Access granted |
|-------|----------------|
| `"users"` | User management and authentication endpoints. |
| `"scopes"` | Scope and scope-assignment endpoints. |
| `"licenses"` | License management endpoints. |
| `"acl"` | ACL resource and group endpoints. |
| `"rbac"` | RBAC role and assignment endpoints. |
| `"abac"` | ABAC policy and evaluation endpoints. |
| `"ngac"` | NGAC graph endpoints. |
| `"service"` | Trusted service-to-service operations; also requires the relevant feature scope. |
| `"all"` | All normal feature scopes, excluding `"service"`. |

---

## Error handling

All methods return `Result[DTO, XoloError]`. On failure, `unwrap_err()` returns a typed `XoloError` subclass:

| Subclass | HTTP status | When raised |
|----------|-------------|-------------|
| `UnauthorizedError` | 401 | Missing or invalid credentials. |
| `AccessDeniedError` | 403 | Valid credentials but insufficient permissions. |
| `NotFoundError` | 404 | Resource does not exist. |
| `ConflictError` | 409 | Resource already exists or conflicts with existing state. |
| `ValidationError` | 422 | Request payload failed server-side validation. |
| `XoloError` | any | Base class; also used for network-level failures. |

```python
result = client.create_role(name="editor", token=token, temporal_secret=secret)

if result.is_err:
    err = result.unwrap_err()
    print(err.status_code, err.detail)
else:
    role = result.unwrap()
```
