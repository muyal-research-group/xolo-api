<div align="center">
  <img src="assets/logo.png" width="180" alt="Xolo logo" />
</div>

<div align="center">
  <a href="https://github.com/muyal-research-group/xolo-api/actions/workflows/ci.yml">
    <img src="https://github.com/muyal-research-group/xolo-api/actions/workflows/ci.yml/badge.svg" alt="ci">
  </a>
  <a href="https://github.com/muyal-research-group/xolo-api/actions/workflows/docs.yml">
    <img src="https://github.com/muyal-research-group/xolo-api/actions/workflows/docs.yml/badge.svg" alt="docs">
  </a>
  <a href="https://codecov.io/gh/muyal-research-group/xolo-api">
    <img src="https://codecov.io/gh/muyal-research-group/xolo-api/graph/badge.svg" alt="codecov">
  </a>
  <img src="https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/muyal-research-group/xolo-api/master/pyproject.toml&query=$.tool.poetry.version&label=version&color=green" alt="version">
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="python">
  <img src="https://img.shields.io/badge/framework-FastAPI-009688" alt="fastapi">
  <img src="https://img.shields.io/badge/database-MongoDB-47A248" alt="mongodb">
  <img src="https://img.shields.io/badge/cache-Redis-DC382D" alt="redis">
</div>

# Xolo API

Xolo is an **Identity and Access Management API** built with **FastAPI**, **MongoDB**, and **Redis**. It combines multiple authorization models in one service so teams can choose the right mechanism for each use case instead of forcing every workload into a single policy style.

All API routes are served under **`/api/v4`**.

## Why Xolo exists

Xolo brings together four complementary access-control styles:

| Model | Best fit | Persistence |
| --- | --- | --- |
| **ACL** | resource ownership and sharing | MongoDB |
| **ABAC Event** | request-time rules with subject/resource/location/time/action | MongoDB |
| **ABAC community policies** | graph/community-based policy evaluation | in memory |
| **NGAC** | graph traversal with policy classes and AND semantics | MongoDB |

Supporting modules like **accounts**, **users**, **scopes**, **licenses**, **API Keys**, and the **admin UI** make those authorization models usable in real applications.

## Multi-Tenant SaaS Model

Xolo is designed as a **multi-tenant IAM service** where each tenant is an **Account**. This enables:

- **Platform operators** (Xolo admins) to manage accounts and bootstrap API keys
- **Account owners** (primary users) to manage their own users, scopes, licenses, and authorization policies via API keys

**Key principle:** All resources (users, scopes, licenses, policies) belong to an account. Account owners interact with Xolo via the REST API using account-scoped API keys. The admin UI is reserved for Xolo operators only.

### Account Owner Workflow

1. Xolo admin creates an account and generates an API key with scopes
2. Account owner uses the API key to:
   - Create users
   - Define scopes and assign them to users
   - Issue licenses for users and scopes
   - Configure authorization rules (ACL, ABAC, NGAC, RBAC)

All operations are isolated to the account; account owners cannot access other accounts' data.

## Architecture at a glance

Xolo uses two architectural styles:

1. **Classic layered modules** for users, licenses, scopes, and older ACL flows:
   `controller -> service -> repository -> db`
2. **Vertical slices** for newer authorization systems:
   - `xoloapi/abac/`
   - `xoloapi/ngac/`

Cross-cutting conventions:

- services and repositories return `Result` / `Option` instead of raising control-flow exceptions
- controllers stay thin and translate typed errors into HTTP responses
- structured logging is built with `xoloapi.logging.build_log_payload()`
- configuration is loaded at import time from `XOLO_ENV_FILE`

## Project structure

```text
xolo-api/
├── xoloapi/
│   ├── server.py              # FastAPI app, lifespan, router mounting
│   ├── config/                # Environment-driven settings
│   ├── db/                    # MongoDB and Redis connections
│   ├── middleware/            # JWT auth and admin guards
│   ├── controllers/           # Classic IAM controllers
│   ├── services/              # Classic IAM service layer
│   ├── repositories/          # Classic IAM persistence layer
│   ├── accounts/              # Top-level account lifecycle and ownership
│   ├── users/                 # User flows, password reset, mail providers
│   ├── scopes/                # Scope management and assignments
│   ├── licenses/              # License issuance and revocation
│   ├── apikeys/               # API key creation and management
│   ├── admin_ui/              # Minimal internal super-admin UI
│   ├── acl/                   # ACL subsystem
│   ├── groups/                # SecurityGroup shared bounded context (used by ACL and RBAC)
│   ├── abac/                  # Persisted ABAC Event subsystem
│   └── ngac/                  # NGAC graph subsystem
├── tests/                     # Integration and module tests
├── deploy/env/                # Deployment env files
├── assets/                    # Static project assets
├── docker-compose.yml         # Full stack deployment
└── zensical.toml             # Native Zensical docs config
```

## Quick start

### Requirements

- Python **3.10+**
- [Poetry](https://python-poetry.org/)
- Docker and Docker Compose for local MongoDB/Redis

### Install and run locally

```bash
poetry install
bash run_local.sh
```

That script starts MongoDB and Redis with Docker, sets `XOLO_ENV_FILE=.env.dev`, and runs the API with auto-reload on port `10000`.

If you prefer to start the app manually:

```bash
poetry install
XOLO_ENV_FILE=.env.dev uvicorn xoloapi.server:app --reload --host 0.0.0.0 --port 10000
```

Open:

- API: `http://localhost:10000`
- OpenAPI: `http://localhost:10000/docs`
- Admin UI: `http://localhost:10000/admin/login`

## Authentication and admin model

Xolo now treats **accounts** as the top-level owner for core IAM data. Core routes are account-scoped:

- `POST /api/v4/accounts` creates an account
- `POST /api/v4/accounts/{account_id}/apikeys` creates an account-owned API key
- `POST /api/v4/accounts/{account_id}/users` creates a user inside that account
- `POST /api/v4/accounts/{account_id}/scopes` creates a scope inside that account
- `POST /api/v4/accounts/{account_id}/licenses` assigns a license inside that account

That same account prefix is used for list/delete/auth flows on those core modules.

Xolo uses different credentials for different surfaces:

- **JWT bearer tokens** for normal authenticated API usage
- **`X-API-Key`** for endpoints guarded by scope-based API-key access; the key must belong to the same `{account_id}` in the URL
- **`X-Admin-Token`** for super-admin create/list/delete operations
- **Admin UI login token** for the web admin panel at `/admin`

The admin UI is intentionally minimal and is meant for trusted internal operators. It includes:

1. **Dashboard** - select an account once to use across all admin pages
2. **Accounts** - create and delete accounts
3. **Account-aware forms** - API Keys, scopes, assignments, users, licenses, and authorization configuration

The selected account is stored in your session cookie, so you don't need to specify it on each page.

### Users API-key requirement

Public user auth/signup endpoints are account-scoped and require an API key with the `users` scope:

```http
POST /api/v4/accounts/{account_id}/users/auth
X-API-Key: <account-owned-users-key>
```

The API key account must match the `{account_id}` in the request path.

## Email delivery

User-facing email delivery is configurable:

- `smtp`
- `cloudflare`
- `noop`

The `noop` provider is useful in development and is the intended default for `.env.dev`, so the application can start without a real mail provider.

Current email use cases:

- welcome email on signup
- password reset email

## Testing

Run the main test suite with:

```bash
poetry run pytest
```

Useful focused commands:

```bash
poetry run pytest tests/test_services.py::test_main_logic
poetry run pytest tests/ngac/test_ngac_graph.py::test_and_rule_user_satisfies_both_pcs
poetry run pytest tests/abac/test_abac_controller.py -k evaluate
poetry run coverage run -m pytest && poetry run coverage report
```

Most tests expect MongoDB at `mongodb://localhost:27018` and some controller-level tests also require Redis because the FastAPI lifespan connects both services.

## Documentation site

This repository now includes a **native Zensical Markdown docs site** configured with `zensical.toml`.

GitHub Actions can build and publish the generated site to **GitHub Pages** through `.github/workflows/docs.yml`.

### Serve the docs locally

```bash
poetry install
poetry run zensical serve
```

### Build the docs

```bash
poetry run zensical build
```

The source pages live in `docs/`.
The published site target is `https://muyal-research-group.github.io/xolo-api/` once GitHub Pages is enabled for the repository.

## Deployment

### Local infrastructure only

```bash
bash run_local.sh
```

### Full Docker deployment

```bash
./deploy.sh
```

The deployment stack uses:

- `docker-compose.yml`
- `deploy/env/compose.env`
- `deploy/env/app.prod.env`
- `deploy/env/mongodb.env`
- `deploy/env/redis.env`

Before deploying outside development, replace placeholder secrets and review:

- `XOLO_JWT_SECRET`
- `XOLO_LICENSE_SECRET_KEY`
- `XOLO_SUPER_ADMIN_TOKENS`
- mail-provider credentials
- MongoDB and Redis connection/auth settings

## Contributing

1. Create a branch for your change.
2. Install dependencies with `poetry install`.
3. Start the local stack with `bash run_local.sh` or run MongoDB/Redis yourself.
4. Add or update tests for the affected module.
5. Keep controllers thin and business rules in services.
6. Preserve the existing `Result` / `Option` error-handling pattern.
7. Update the docs when behavior or configuration changes.

## Extended documentation

The full documentation set lives in `docs/` and covers:

- getting started
- authentication and admin flows
- access-control models
- architecture
- configuration
- deployment
- project structure
- contribution workflow

## License

This project is licensed under the terms in [LICENSE](LICENSE).
