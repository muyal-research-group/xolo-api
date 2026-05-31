# Authentication and admin

Xolo separates user authentication, machine access, and super-admin operations.

## Authentication layers

### JWT bearer tokens

Normal authenticated API flows use bearer tokens returned by account-scoped endpoints such as:

- `POST /api/v4/accounts/{account_id}/users/auth`

Protected endpoints load the current user through `xoloapi.middleware.get_current_user`. The bearer token is expected to stay inside the same account context.

### API Keys

Some endpoints also require:

```http
X-API-Key: <key>
```

API Keys carry named scopes and are used for service-to-service access patterns. They are owned by a single account and must be used against URLs under that same `/accounts/{account_id}/...` prefix.

### Super-admin token

Administrative list/create/delete surfaces are protected by:

```http
X-Admin-Token: <super-admin-token>
```

Valid tokens come from `XOLO_SUPER_ADMIN_TOKENS`.

## Admin UI

The admin UI is mounted at `/admin`.

### Login flow

1. the operator opens `/admin/login`
2. they submit a valid admin token
3. the UI creates a signed HttpOnly session cookie with account context
4. subsequent admin pages use that cookie instead of resending the token

### Account selection

After login, the operator selects an account on the admin dashboard:

1. open `/admin` (dashboard)
2. select an account ID from the dropdown and submit
3. the account is stored in the session cookie (JWT claim)
4. all account-owned pages (users, scopes, licenses, API keys, scope assignments) now show data for that account
5. use the "Clear account" button to reset the selection

Once an account is selected, you don't need to specify it on each page—it persists across navigation.

### Admin UI sections

- **dashboard** - account selection and main navigation
- **accounts** - create and delete accounts
- **API Keys** - create and revoke API keys for the selected account
- **scopes** - create and delete scopes for the selected account
- **scope assignments** - assign scopes to users within the selected account
- **users** - create, block/unblock, and delete users in the selected account
- **licenses** - assign and manage licenses for the selected account
- **authorization** - ACL, RBAC, ABAC, and NGAC configuration for the selected account

The UI is intentionally simple and is designed for trusted internal operations rather than public self-service.

## User lifecycle notes

### Signup

Signup is account-scoped (`POST /api/v4/accounts/{account_id}/users/signup`) and requires an API key with the `users` scope. It creates the user and then triggers the welcome-email flow through the configured mail provider.

### Token refresh

A logged-in user can exchange their current token for a fresh one without re-entering credentials:

```http
POST /api/v4/accounts/{account_id}/users/refresh
Authorization: Bearer <access_token>
Temporal-Secret-Key: <temporal_secret>
Content-Type: application/json

{"expiration": "15min"}
```

The response contains a new `access_token` and `temporal_secret`. The old pair is immediately invalidated — subsequent calls to `/verify` with the old credentials will be rejected. The `expiration` field is optional and defaults to `15min`; it accepts human-friendly values such as `"1h"`, `"30min"`, `"2d"`.

### Password recovery

Password reset requests generate a reset token and send an email through the configured provider.

### User deletion

Deleting a user is a super-admin operation on an account-scoped URL and performs cleanup before removing the user record:

1. delete licenses for the user
2. delete scope assignments for the user
3. invalidate password reset tokens
4. clear cached access token state
5. delete the user record
