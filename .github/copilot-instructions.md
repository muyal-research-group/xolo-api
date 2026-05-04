# Copilot instructions for xolo-api

## Build and test commands

Use Poetry for dependency management.

```bash
poetry install
XOLO_ENV_FILE=.env.dev uvicorn xoloapi.server:app --reload
bash run_local.sh
bash build.sh
pytest
coverage run -m pytest && coverage report
pytest tests/test_services.py::test_main_logic
pytest tests/ngac/test_ngac_graph.py::test_and_rule_user_satisfies_both_pcs
pytest tests/abac/test_abac_controller.py -k evaluate
```

Most tests assume MongoDB is reachable at `mongodb://localhost:27018`; controller-level ABAC/NGAC tests also need Redis because FastAPI lifespan startup connects both backends.

## High-level architecture

`xoloapi/server.py` builds one FastAPI app, connects MongoDB and Redis in the lifespan hooks, and mounts every API under `/api/v4`.

The codebase has two architectural styles:

1. Core IAM modules (`users`, `licenses`, `scopes`, older ACL flows) use the classic stack `controllers -> services -> repositories -> db`, with Pydantic models in `xoloapi/models/` and shared DTOs mostly coming from `commonx.dto.xolo`.
2. Newer authorization subsystems are vertical packages under `xoloapi/`:
   - `xoloapi/abac/` is the persisted ABAC Event system with `controller`, `application`, `domain`, and `infrastructure` layers backed by MongoDB.
   - `xoloapi/ngac/` follows the same package-local layering for graph-based authorization.
   - `xoloapi/policies/` is different: it keeps module-level singleton repository/service state in memory so policy communities survive across requests, but not across process restarts.

Authentication and authorization are layered on top of that routing:

1. `xoloapi/middleware/__init__.py` loads the current user from the bearer token and returns a `UserDTO`.
2. Many access-control endpoints also require `Depends(require_api_key("<scope>"))`, so protected routes often need both JWT auth and an `X-API-Key` with the right scope.

## Key conventions

- Service and repository methods communicate with `option.Result` / `Option` values instead of raising normal control-flow exceptions. Controllers are expected to unwrap success values and turn failures into HTTP errors with `.to_http_exception()`.
- Controllers are intentionally thin and do structured logging with `xolo.log.Log`. Log payloads are dicts, usually with `action` or `event` plus identifiers and elapsed time.
- Construct services through FastAPI dependency factories like `get_users_service()` or `get_abac_service()` inside the controller/middleware layer rather than creating them at import time. The main exception is `xoloapi/policies/controller.py`, where module-level singletons are deliberate because that subsystem is in-memory.
- Config is import-time global state in `xoloapi/config/__init__.py`, and `.env` loading is controlled by `XOLO_ENV_FILE`. If behavior depends on environment values, set that variable before importing the app.
- Shared API DTOs live mostly in `commonx.dto.xolo`; local package-specific DTOs live in `xoloapi/dto/` or the subsystem package itself (`xoloapi/abac/dto.py`, `xoloapi/ngac/dto.py`).
- Controller tests commonly override dependencies on `xoloapi.server.app` (`app.dependency_overrides[...]`) instead of minting real tokens, but the app lifespan still runs unless the test bypasses it explicitly.
