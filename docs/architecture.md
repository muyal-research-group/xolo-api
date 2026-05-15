# Architecture overview

## Runtime entrypoint

`xoloapi/server.py` builds the FastAPI application, connects MongoDB and Redis in the lifespan hooks, and mounts routers under `/api/v4`.

## Two architectural styles

### 1. Classic layered modules

Used mainly for:

- accounts
- users
- scopes
- licenses
- older ACL-adjacent flows

Flow:

```text
controller -> service -> repository -> db
```

Responsibilities:

- **controller**: HTTP routing, validation, logging, dependency injection
- **service**: business rules and orchestration
- **repository**: persistence and query logic
- **db**: MongoDB and Redis client access

Common examples:

- `accounts`
- `users`
- `scopes`
- `licenses`
- `apikeys`
- `acl`
- `rbac`

### 2. Vertical subsystems

Used for:

- `xoloapi/abac/`
- `xoloapi/ngac/`

These packages keep their own controller/application/domain/infrastructure structure or local service composition so subsystem logic stays together.

`admin_ui` is a small exception: it is mostly controller- and template-driven rather than a full domain package.

For a module-by-module view of the feature packages under `xoloapi/`, see [Project structure](project-structure.md).

## Error handling convention

Services and repositories use `option.Result` / `Option` instead of raising normal control-flow exceptions.

Typical pattern:

```python
if result.is_err:
    raise result.unwrap_err().to_http_exception()
return result.unwrap()
```

## Dependency injection

FastAPI dependency factories create services at request time. This keeps wiring near the HTTP layer and avoids unnecessary global state.

The notable exception is `xoloapi/policies/`, where module-level singletons are deliberate because that subsystem is in memory.

## Logging

Controllers and services log structured payloads built through:

- `xoloapi.logging.build_log_payload()`

The common pattern is:

- `info` on success
- `error` on failure
- include action names, identifiers, and elapsed time

## Configuration model

Configuration is import-time global state defined in `xoloapi/config/__init__.py`.

The active env file is selected with:

```bash
XOLO_ENV_FILE=.env.dev
```

Because settings are read at import time, environment selection must happen before importing the app.
