# Project structure

This page focuses on the feature modules under `xoloapi/`.

It intentionally keeps the view simple: shared support packages such as `config`, `db`, and `middleware` are not the main focus here.

## Generic module structure

Most feature modules follow the same internal shape:

```text
xoloapi/<module>/
├── application/       # use cases and orchestration
├── domain/            # business rules, aggregates, repository contracts
├── infrastructure/    # MongoDB or external-service adapters
├── controller.py      # FastAPI routes, dependency wiring, logging
├── dto.py             # request and response schemas
├── models.py          # persistence models when the module needs them
└── value_objects.py   # typed domain values when the module needs them
```

### What each part does

| Part | Role |
| --- | --- |
| `application/` | Coordinates module use cases and calls domain and infrastructure pieces. |
| `domain/` | Holds the core rules of the module: aggregates, services, repository interfaces, and value objects. |
| `infrastructure/` | Implements database access and integrations. |
| `controller.py` | Exposes HTTP endpoints and keeps request handling thin. |
| `dto.py` | Defines API-facing input and output shapes. |
| `models.py` | Defines persistence-oriented models when the module stores structured records. |
| `value_objects.py` | Defines reusable typed values with validation or matching logic. |

Not every module uses every file. Simpler modules may omit `models.py` or `value_objects.py`, and `admin_ui` is mostly controller-driven.

## Feature modules in `xoloapi/`

| Module | Purpose | Structure notes |
| --- | --- | --- |
| `accounts/` | Creates and manages tenant accounts, the root owner for account-scoped resources. | Uses `application/` and `infrastructure/`; includes `models.py` and `dependencies.py`. |
| `users/` | Handles signup, authentication, logout, password recovery, and user mail flows. | Follows the common `application/domain/infrastructure/controller/dto` pattern. |
| `scopes/` | Manages account scopes and scope assignments. | Follows the common layered module pattern. |
| `licenses/` | Creates, lists, and revokes licenses tied to users and scopes. | Follows the common layered module pattern. |
| `apikeys/` | Creates and manages account-owned API keys and their scope bindings. | Follows the common layered module pattern. |
| `acl/` | Provides ownership and permission-sharing access control. | Follows the common layered module pattern. |
| `abac/` | Implements the persisted ABAC Event subsystem. | Uses the full package-local layout and adds `models.py` and `value_objects.py`. |
| `ngac/` | Implements graph-based NGAC authorization with nodes, assignments, associations, and checks. | Uses package-local application/domain/infrastructure layers plus graph-specific helpers. |
| `rbac/` | Handles role-based access control flows. | Follows the common layered module pattern. |
| `admin_ui/` | Provides the internal super-admin web UI. | Mostly centered on `controller.py` and templates rather than the full layered layout. |

## How to read the module layout

There are two common styles behind these modules:

1. **Classic layered modules** such as `users`, `scopes`, `licenses`, `apikeys`, `acl`, and `rbac`
2. **Package-local vertical modules** such as `abac` and `ngac`, where the application, domain, and infrastructure pieces stay together inside the module

`accounts` sits close to the classic style, while `admin_ui` is intentionally lighter because it is a small internal web surface.

For the runtime and cross-cutting architecture around these modules, see [Architecture overview](architecture.md).
