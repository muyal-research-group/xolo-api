# Project structure

```text
xolo-api/
├── xoloapi/
│   ├── server.py
│   ├── config/
│   ├── db/
│   ├── middleware/
│   ├── controllers/
│   ├── services/
│   ├── repositories/
│   ├── users/
│   ├── scopes/
│   ├── licenses/
│   ├── apikeys/
│   ├── admin_ui/
│   ├── acl/
│   ├── abac/
│   ├── ngac/
│   ├── policies/
│   ├── dto/
│   ├── models/
│   ├── errors/
│   └── security/
├── tests/
├── deploy/
├── db/
├── assets/
├── scripts/
├── docker-compose.yml
├── run_local.sh
├── deploy.sh
├── build.sh
├── pyproject.toml
└── zensical.toml
```

## Key directories

### `xoloapi/users/`

User signup, authentication, logout, password recovery, and outbound mail integration.

### `xoloapi/scopes/`

Scope creation, assignment, listing, guarded deletion, and admin-facing scope metadata.

### `xoloapi/licenses/`

License creation, listing, self-service deletion, and admin deletion flows.

### `xoloapi/apikeys/`

API key generation, metadata storage, revocation/deletion, and scope binding.

### `xoloapi/admin_ui/`

Minimal internal Jinja-based admin panel for super-admin operations.

### `xoloapi/abac/`

Persisted ABAC Event implementation.

### `xoloapi/ngac/`

NGAC graph subsystem with nodes, assignments, associations, and access checks.

### `xoloapi/policies/`

In-memory community-based policy system.

### `deploy/env/`

Runtime env files for Docker deployment and supporting services.

### `tests/`

Pytest-based integration and module tests.
