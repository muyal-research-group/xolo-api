# Authentication

The Xolo API uses three main authentication mechanisms, and the client combines them depending on the route family.

## 1. `X-Admin-Token`

Used for account-administration endpoints such as:

- `GET/POST /api/v4/accounts`
- account API key management
- scopes
- licenses
- admin user lifecycle operations

Configure it once on the client when you need those methods:

```python
client = XoloClient(
    account_id="research-account",
    api_key="xk_live_...",
    admin_token="admin-token",
)
```

## 2. `X-API-Key`

Used for:

- signup and auth flows,
- account-scoped user-context authorization APIs.

This is why `api_key` is a first-class constructor argument.

## 3. Bearer token + temporal secret

User-context routes rely on a bearer token issued by `auth()` and frequently a `Temporal-Secret-Key` header:

```python
auth = client.auth(
    username="alice",
    password="secret",
    scope="research",
    renew_token=True,
).unwrap()

client.get_current_user(
    token=auth.access_token,
    temporal_secret=auth.temporal_secret,
)
```

## Refreshing a session

Call `refresh_token()` to extend an active session without re-authenticating. The server
invalidates the old token pair on success, so always switch to the new credentials immediately:

```python
refreshed = client.refresh_token(
    token=auth.access_token,
    temporal_secret=auth.temporal_secret,
    expiration="1h",          # optional; defaults to "15min"
).unwrap()

# old credentials are now dead — use the new pair
access_token = refreshed.access_token
temporal_secret = refreshed.temporal_secret
```

Accepted `expiration` values follow a human-friendly format: `"15min"`, `"1h"`, `"2d"`, etc.

## Typical flow

1. Create or obtain an API key for the target account.
2. Sign up or provision users in that account.
3. Authenticate with `auth()` to obtain a bearer token and temporal secret.
4. Call `refresh_token()` before expiry to extend the session.
5. Use the bearer token plus temporal secret for ACL, ABAC, NGAC, and RBAC operations.

## Notes about password recovery

The live account API exposes a two-step password recovery flow:

1. `request_password_recovery(identifier=...)`
2. `confirm_password_recovery(token=..., password=...)`

The older `update_user_password()` method remains as a compatibility wrapper and now expects the recovery token in its `secret` argument.
