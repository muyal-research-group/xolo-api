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
3. the UI creates a signed HttpOnly session cookie
4. subsequent admin pages use that cookie instead of resending the token

### Admin UI sections

- dashboard
- accounts
- API Keys
- scopes
- scope assignments
- users
- licenses

The UI is intentionally simple and is designed for trusted internal operations rather than public self-service.

## User lifecycle notes

### Signup

Signup is account-scoped (`POST /api/v4/accounts/{account_id}/users/signup`) and requires an API key with the `users` scope. It creates the user and then triggers the welcome-email flow through the configured mail provider.

### Password recovery

Password reset requests generate a reset token and send an email through the configured provider.

### User deletion

Deleting a user is a super-admin operation on an account-scoped URL and performs cleanup before removing the user record:

1. delete licenses for the user
2. delete scope assignments for the user
3. invalidate password reset tokens
4. clear cached access token state
5. delete the user record
