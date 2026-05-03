# Configuration

Xolo reads configuration from environment variables, with optional loading from an env file selected by `XOLO_ENV_FILE`.

## Env-file selection

By default the app loads:

```bash
.env
```

To use the development file:

```bash
XOLO_ENV_FILE=.env.dev
```

## Important variable groups

### Core runtime

| Variable | Purpose |
| --- | --- |
| `XOLO_MONGODB_URI` | MongoDB connection string |
| `XOLO_MONGODB_DATABASE_NAME` | Mongo database name |
| `XOLO_CACHE_REDIS_URI` | Redis connection string |
| `XOLO_JWT_SECRET` | JWT signing secret |
| `XOLO_JWT_ALGORITHM` | JWT algorithm |
| `XOLO_JWT_EXPIRE_MINUTES` | access-token lifetime |

### OpenAPI and HTTP

| Variable | Purpose |
| --- | --- |
| `XOLO_OPENAPI_PREFIX` | root path prefix |
| `XOLO_OPENAPI_TITLE` | OpenAPI title |
| `XOLO_OPENAPI_VERSION` | OpenAPI version string |
| `XOLO_OPENAPI_SUMMARY` | short API summary |
| `XOLO_OPENAPI_DESCRIPTION` | longer API description |
| `XOLO_OPENAPI_LOGO` | logo URL for OpenAPI |

### CORS

| Variable | Purpose |
| --- | --- |
| `XOLO_CORS_ALLOW_ORIGINS` | allowed origins |
| `XOLO_CORS_CREDENTIALS` | allow credentials |
| `XOLO_CORS_ALLOW_METHODS` | allowed methods |
| `XOLO_CORS_ALLOW_HEADERS` | allowed headers |

### Admin and security

| Variable | Purpose |
| --- | --- |
| `XOLO_LICENSE_SECRET_KEY` | license-related secret key |
| `XOLO_SUPER_ADMIN_TOKENS` | comma-separated super-admin tokens |
| `XOLO_ADMIN_UI_SESSION_SECRET` | admin UI cookie signing secret |
| `XOLO_ADMIN_UI_SESSION_COOKIE_NAME` | admin UI cookie name |
| `XOLO_ADMIN_UI_SESSION_MAX_AGE` | admin UI session lifetime |
| `XOLO_ADMIN_UI_SESSION_SECURE` | secure cookie flag |

Legacy aliases remain supported for compatibility:

- `XOLO_ACL_KEY`
- `XOLO_SUPER_ADMIN_KEYS`

### Email delivery

| Variable | Purpose |
| --- | --- |
| `XOLO_EMAIL_PROVIDER` | `smtp`, `cloudflare`, or `noop` |
| `XOLO_MAIL_SENDER_ADDRESS` | sender email address |
| `XOLO_MAIL_SENDER_NAME` | sender display name |
| `XOLO_WELCOME_MAIL_SUBJECT` | welcome-email subject |
| `XOLO_PASSWORD_RESET_MAIL_SUBJECT` | password-reset subject |
| `XOLO_PASSWORD_RESET_URL_BASE` | frontend reset URL base |
| `XOLO_PASSWORD_RESET_TOKEN_EXPIRES_IN` | reset-token lifetime |

SMTP-specific:

- `XOLO_SMTP_HOST`
- `XOLO_SMTP_PORT`
- `XOLO_SMTP_USERNAME`
- `XOLO_SMTP_PASSWORD`
- `XOLO_SMTP_USE_TLS`
- `XOLO_SMTP_USE_SSL`

Cloudflare-specific:

- `XOLO_CLOUDFLARE_ACCOUNT_ID`
- `XOLO_CLOUDFLARE_EMAIL_API_TOKEN`

### Logging

| Variable | Purpose |
| --- | --- |
| `XOLO_LOG_NAME` | logger name |
| `XOLO_LOG_INTERVAL` | rotation interval |
| `XOLO_LOG_WHEN` | rotation unit |
| `XOLO_LOG_PATH` | log directory |

## Recommended local-development posture

For local development, prefer:

- `.env.dev`
- `XOLO_EMAIL_PROVIDER=noop`
- locally exposed MongoDB and Redis
- non-production secrets

## Recommended production posture

- use strong unique secrets
- set real `XOLO_SUPER_ADMIN_TOKENS`
- configure a real mail provider
- enable secure cookies for admin UI behind HTTPS
- review public ports and reverse-proxy settings
