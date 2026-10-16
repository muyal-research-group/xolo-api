# Authentication and platform console

Xolo separates tenant-user sessions, service credentials, emergency administration, and platform-console identities.

## Tenant users

Tenant applications authenticate through account-scoped endpoints such as `POST /api/v4/accounts/{account_id}/users/auth`. Protected application endpoints use the returned bearer token and temporal secret in the same account context.

## API keys

Account API keys are service credentials sent in `X-API-Key`. They carry scopes, belong to one account, and cannot sign in to the platform console. Trusted automation additionally requires the explicit `service` scope plus the feature scope; `all` deliberately does not imply `service`.

Raw API keys are returned only at creation or rotation. The API and console show only safe metadata afterward.

The console gets the complete supported scope list from `GET /api/v4/accounts/{account_id}/apikeys/scopes`. `DELETE /api/v4/accounts/{account_id}/apikeys/{key_id}` revokes a key but retains its metadata; `DELETE /api/v4/accounts/{account_id}/apikeys/{key_id}/permanent` invalidates the key and permanently removes its record. Both actions require API-key management permission and a confirmation in the console.

## Emergency admin tokens

`XOLO_SUPER_ADMIN_TOKENS` configures restart-bound `X-Admin-Token` credentials for automation and recovery. These tokens are never returned to the browser console.

## Platform users

Platform users sign in at `POST /api/v4/platform/session` with a username and password. They are a separate identity type and cannot use their password or console session as an account API key.

The roles are:

- `admin`: all console permissions and all accounts
- `user`: explicitly assigned read/manage permissions and account IDs
- `guest`: explicitly assigned read permissions and account IDs; manage permissions are discarded

The last active administrator cannot be deleted, disabled, or demoted. An administrator also cannot delete their own platform identity.

On an empty database, startup creates the initial administrator from `XOLO_PLATFORM_BOOTSTRAP_USERNAME` and `XOLO_PLATFORM_BOOTSTRAP_PASSWORD`. Startup fails if the collection is empty and no valid bootstrap password is configured. The bootstrap user must change the password before using management APIs.

### Locked-out administrator recovery

The bootstrap password creates the first administrator only; changing it does not update an existing user. If every administrator is locked out, run the interactive recovery script from the repository root:

```bash
./scripts/reset-platform-password
```

The wrapper securely prompts for the username, password, and confirmation, builds the current API image if needed, and runs the one-shot reset command. The password must contain at least 12 characters. The script updates only an existing platform user, marks the password for change after sign-in, and invalidates that user's existing sessions.

## Console sessions

Successful login creates an opaque random session in Redis. The browser receives:

- an HttpOnly, SameSite=Strict session cookie
- a readable SameSite=Strict CSRF cookie

State-changing calls must send the CSRF value in `X-CSRF-Token`; the API verifies both copies. Disabling a user, resetting their password, or changing their permissions invalidates all of that user's sessions.

The Nuxt/Vuetify console in `xolo-ui/` uses only these API endpoints. It never reads an admin token or account API key for its own authentication, and Compose exposes it on localhost by default.

## Tenant-user lifecycle

Signup requires an account key with the `users` scope. Session introspection requires a key with both `service` and `users`, and checks the active Redis session so logout takes effect immediately. Password recovery uses the configured mail provider. Tenant-user deletion removes licenses, scope assignments, password-reset tokens, cached session state, and the user record.
