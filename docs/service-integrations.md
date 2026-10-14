# Service integrations

Xolo supports a trusted service mode for control planes and other backend services. It lets a service manage ACL resources and groups without borrowing a user's session.

## The two credentials

A service API key needs both scopes:

- `service`: explicitly marks the key as trusted for service-to-service operations.
- The feature scope, such as `acl` or `users`: limits what that service may use.

The `all` scope does **not** include `service`. This prevents an existing broad API key from silently gaining trusted automation privileges after an upgrade.

Create separate keys per consuming service and environment, set an expiry when practical, and rotate or revoke them independently. Xolo stores only the key hash and shows the raw key once.

## Bootstrap without the admin UI

Top-level account creation cannot use an account-owned key because that account does not exist yet. Automate this once with a super-admin token kept in a deployment secret store:

1. `POST /api/v4/accounts` with `X-Admin-Token` creates the Xolo account.
2. `POST /api/v4/accounts/{account_id}/apikeys` with the same token creates the control-plane key with `service`, `users`, and `acl` scopes.
3. Store the raw key in the control plane's secret store; Xolo will not show it again.
4. Normal operation uses only that account-scoped key. Do not expose or continuously distribute the super-admin token.

If the control plane also automates RBAC, add `rbac`. Create a different key for each environment so a leaked development key cannot reach production.

## AXO example

AXO owns the business model. One AXO deployment uses one Xolo account, while each VirtualEnvironment (VE) is represented by an ACL resource such as `ve:123`.

For every AXO team, create three Xolo groups and store their returned `group_id` values:

| AXO role | Xolo group | Resource access |
|---|---|---|
| Team owner | `team:<id>:owners` | Owns the VE; all permissions including `sys:manage` |
| Team admin | `team:<id>:admins` | `read`, `write`, `update`, `delete` |
| Team member | `team:<id>` | `read` |

When AXO creates a VE:

1. Claim `ve:<id>` for the team's owners group with `POST .../acl/service/claim`.
2. Grant the admins group `read`, `write`, `update`, and `delete`.
3. Grant the members group `read`.

Xolo combines a user's direct and group grants. No AXO-specific role rules are required inside Xolo.

## Available service operations

All routes are below `/api/v4/accounts/{account_id}/acl/service` and require `X-API-Key`.

| Operation | Route |
|---|---|
| Claim a resource for a user or group | `POST /claim` |
| Grant or revoke permissions | `POST /grant`, `DELETE /revoke` |
| Read a user's effective permissions | `GET /resources/{resource_id}/users/{user_id}/access` |
| List a resource's grants | `GET /resources/{resource_id}/grants` |
| List resources visible to a user | `GET /users/{user_id}/resources` |
| Transfer or delete a resource policy | `POST /resources/{resource_id}/owner`, `DELETE /resources/{resource_id}` |
| Create or delete groups | `POST /groups`, `DELETE /groups/{group_id}` |
| Add, remove, or list members | `POST`, `DELETE`, or `GET /groups/{group_id}/members` |
| Transfer group ownership | `POST /groups/{group_id}/owner` |

Session introspection is `POST /api/v4/accounts/{account_id}/users/introspect`. It requires a key with both `service` and `users`, plus the user's bearer token and `Temporal-Secret-Key`. A revoked, replaced, disabled, expired, or account-mismatched session is rejected.

## PATs stay in the consuming platform

Xolo API keys identify trusted services and are account-wide. They should not be handed to users or SDK programs.

AXO should continue to issue its own personal access tokens (PATs), store only their hashes, and restrict each PAT to a user, VE, role, and optional expiry. AXO authenticates the PAT, then asks Xolo for the user's current effective access. The lower of the PAT's limit and the user's current role wins.
# Authorization v2 breaking changes

Authorization v2 is a coordinated breaking release. Deploy the API and
`xolo-client` together, run `scripts/migrate_authorization.py --dry-run`, resolve
any reported group-name collisions, and then run the migration without
`--dry-run` before enabling the new UI.

- Group lifecycle and membership routes moved from
  `/accounts/{account_id}/acl/groups` and `/acl/service/groups` to
  `/accounts/{account_id}/groups`. There are no compatibility aliases.
- Group API keys require the new `groups` scope. Audit readers require the new
  `audit` scope. ACL and RBAC keys may read `/groups/references` only.
- Groups are shared principals. Ownership does not imply membership, and a
  group has no ACL/RBAC type flag.
- RBAC assignments now always contain `subject_type` (`USER` or `GROUP`). The
  migration permanently removes pre-v2 untyped assignments after reporting
  their count.
- New ABAC policies use `glob_v2`; migrated policies retain `legacy_v1` until
  explicitly upgraded.

The migration creates timestamped backup collections in the same database,
records an idempotent completion marker, and creates the required indexes.
