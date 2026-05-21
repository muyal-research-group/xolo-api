# Access control models

Xolo supports several authorization styles because real systems often need more than one.

## ACL

**Base path:** `/api/v4/acl`

ACL is the ownership-and-sharing model.

### Best for

- resource ownership
- per-resource grants
- group-based sharing

### Core ideas

- the first claimer becomes owner
- owners grant and revoke permissions
- permissions can be granted to users or groups
- effective access is the union of direct and group permissions

### Groups

Groups are managed via the shared `xoloapi/groups/` bounded context (also used by RBAC). A group has a single owner and any number of members. When checking access, the caller's direct permissions plus those of every group they own or belong to are unioned together.

| Endpoint | Description |
| --- | --- |
| `POST /acl/groups` | Create a group (caller becomes owner and first member) |
| `DELETE /acl/groups/{group_id}` | Delete a group (owner only) |
| `POST /acl/groups/{group_id}/members` | Add members |
| `DELETE /acl/groups/{group_id}/members` | Remove members |
| `GET /acl/groups/{group_id}/members/{user_id}` | Check membership |

### Permission check

`POST /acl/check` evaluates whether a principal has a set of permissions on a resource.

```json
{
  "resource_id": "my-resource",
  "permissions": ["read", "write"],
  "principal_id": "grp-my-group-abc123",
  "principal_type": "GROUP"
}
```

| Field | Required | Description |
| --- | --- | --- |
| `resource_id` | yes | The resource to check |
| `permissions` | yes | List of permission strings (`read`, `write`, `delete`, `sys:manage`) |
| `principal_id` | no | ID of the user or group to check. Defaults to the authenticated caller |
| `principal_type` | no | `USER` or `GROUP`. Informational — the check resolves principals by ID |

When `principal_id` is omitted the check uses the authenticated user and expands all groups that user owns or belongs to. When a group ID is supplied directly the check resolves the group's own grants.

## ABAC Event

**Base path:** `/api/v4/abac`

ABAC Event stores policies in MongoDB and evaluates requests against event tuples:

`(subject, resource, location, time, action)`

### Best for

- context-aware access checks
- wildcard matching
- persistent rule sets

### Evaluation model

- evaluate all matching policies
- **DENY overrides ALLOW**
- no match means deny

## ABAC community policies

**Base path:** `/api/v4/policies`

This subsystem uses in-memory policy communities built around the `xolo.abac` library.

### Best for

- experimentation
- fast in-memory evaluation
- graph/community-based grouping

### Important limitation

Policy communities are **not persisted** across process restarts.

## NGAC

**Base path:** `/api/v4/ngac`

NGAC models the authorization system as a graph of users, objects, attributes, and policy classes.

### Best for

- graph-shaped authorization domains
- multi-domain policy composition
- fine-grained policy traversal

### Important rule

If an object belongs to multiple policy classes, the required permission must be satisfied through **every** governing policy class.

## Supporting IAM modules

### Scopes

Scopes are named permissions/capabilities that power API Keys, user assignments, and licenses.

### Licenses

Licenses bind users to scopes and can expire.

### API Keys

API Keys carry named scopes for service access.

### Users

Users authenticate, receive JWTs, and interact with the access-control subsystems.
