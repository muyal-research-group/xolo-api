# Client guide

`XoloClient` is the main integration surface for the live Xolo API.

## Constructor

```python
from xolo.client.client import XoloClient

client = XoloClient(
    account_id="research-account",
    api_key="xk_live_...",
    api_url="http://localhost:10000/api/v4",
    admin_token="admin-token",
)
```

### Constructor fields

- `account_id`: required account scope for account-bound endpoints.
- `api_key`: default key for API-key-protected routes and user-context authorization flows.
- `api_url`: base API root; defaults to `http://localhost:10000/api/v4`.
- `admin_token`: used for admin-only routes such as account management, API-key management, scopes, licenses, and admin user lifecycle operations.
- `secret`: legacy compatibility field retained for older callers. The new account API primarily uses `api_key`, `admin_token`, bearer tokens, and temporal secrets.

## Return style

Public methods follow the repository convention of returning `option.Result` values:

```python
result = client.list_api_keys()
if result.is_ok:
    keys = result.unwrap()
else:
    error = result.unwrap_err()
```

## Error handling

See the dedicated [Error handling](error-handling.md) guide for the full error class
reference and `Result` extraction patterns.

## Method families

### Admin-token methods

These use `X-Admin-Token` and are mainly for account administration:

- accounts
- API keys
- scopes
- licenses
- admin-style user lifecycle operations (`create_user`, `list_users`, `block_user`, `unblock_user`)

### API-key methods

These rely on `X-API-Key`:

- `signup`
- `auth`
- `delete_user` (requires the `users` or `all` scope)
- account-scoped user-context calls that also require bearer auth for ACL, ABAC, NGAC, and RBAC

All API-key-backed public methods also accept an optional trailing `api_key=""` override when one request must use a different key than the client default.

### Bearer-token methods

These use `Authorization: Bearer ...` and often add `Temporal-Secret-Key`:

- `get_current_user`
- `logout`
- `refresh_token`
- `enable_user`
- `disable_user`
- ACL, ABAC, NGAC, and RBAC evaluation/manipulation routes

For ACL, ABAC, NGAC, and RBAC methods, bearer auth now combines with **either** `api_key` **or** `admin_token`; at least one of those headers must be available for the request.

## Examples

### Sign up and authenticate

```python
signup = client.signup(
    username="alice",
    first_name="Alice",
    last_name="Smith",
    email="alice@example.com",
    password="secret",
    scope="research",
)

auth = client.auth(
    username="alice",
    password="secret",
    scope="research",
    renew_token=True,
)
```

### Admin scope management

```python
client.create_scope("research")
client.assign_scope(username="alice", scope="research", secret="")
```

### RBAC operations

```python
role = client.create_role(
    name="reader",
    description="Read-only access",
    permissions=["documents:read"],
    token=access_token,
    temporal_secret=temporal_secret,
    api_key="override-only-if-needed",
    admin_token="admin-override-only-if-needed",
)
```

The public client methods include Google-style docstrings so IDEs and generated documentation can surface argument and return details directly from the code.

For a method-by-method summary of parameters, return DTOs, and route/auth expectations, see the dedicated [API reference](api-reference.md).
