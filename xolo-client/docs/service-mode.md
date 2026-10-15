# Service mode

Use service methods only from a trusted backend. The configured API key must have the explicit `service` scope plus the feature scope (`acl`, `users`, or `groups`). A key with only `all` is intentionally rejected.

```python
from xolo.client.client import XoloClient

client = XoloClient(
    account_id="axo-production",
    api_key="XOLO_...",  # service + acl + users + groups
    api_url="https://xolo.example.com/api/v4",
)

owners = client.service_create_group("team:42:owners", owner_id="user-1").unwrap()
admins = client.service_create_group("team:42:admins", owner_id="user-1").unwrap()
members = client.service_create_group("team:42", owner_id="user-1").unwrap()
client.service_add_group_members(members.group_id, ["alice"]).unwrap()
client.service_transfer_group_owner(members.group_id, "alice", keep_previous_as_member=True).unwrap()

client.service_claim_resource("ve:123", owners.group_id, owner_type="GROUP").unwrap()
client.service_grant_permission(
    "ve:123",
    admins.group_id,
    ["read", "write", "update", "delete"],
    principal_type="GROUP",
).unwrap()
client.service_grant_permission(
    "ve:123",
    members.group_id,
    ["read"],
    principal_type="GROUP",
).unwrap()
```

To validate a UI session in a control plane:

```python
user = client.introspect_session(access_token, temporal_secret).unwrap()
access = client.service_get_effective_access("ve:123", user.key).unwrap()

if "write" not in access.permissions:
    raise PermissionError("The user cannot modify this VE")
```

Service methods cover resource claims, grants, revocations, effective access, grant lists, user-visible resources, ownership transfers, policy deletion, and group lifecycle operations. They need no user session unless the session itself is being introspected.

Never embed a service key in a browser, mobile app, CLI distributed to users, or user-facing SDK. Issue application-specific PATs from your control plane for those cases.
