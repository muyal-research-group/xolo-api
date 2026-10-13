<div align="center">
  <img src="docs/assets/logo.png" width="200" alt="Xolo logo" />
</div>

<div align="center">
  <h1>Xolo</h1>
  <p>Python client, local authorization engines, and tooling for the Xolo IAM platform.</p>

  [![CI](https://github.com/muyal-research-group/xolo/actions/workflows/ci.yml/badge.svg)](https://github.com/muyal-research-group/xolo/actions/workflows/ci.yml)
  [![codecov](https://codecov.io/gh/muyal-research-group/xolo/branch/master/graph/badge.svg)](https://codecov.io/gh/muyal-research-group/xolo)
  [![TestPyPI](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmuyal-research-group%2Fxolo%2Fmaster%2Fpyproject.toml&query=%24.tool.poetry.version&label=TestPyPI&logo=pypi&color=0A7ABC)](https://test.pypi.org/project/xolo/)
  [![License](https://img.shields.io/badge/license-Fair%20Source-0A7ABC)](LICENSE)
</div>

## Overview

This repository ships the **Python package** for Xolo. It includes:

- a typed `XoloClient` for the live Xolo API,
- local ACL, ABAC, RBAC, NGAC, and policy-evaluation helpers,
- shared crypto, logging, parsing, and utility modules used by those engines.

The API server itself is **not** implemented in this repository. For integration tests and local client exercises, the repository starts MongoDB, Redis, and an external Xolo API image through `docker-compose.yml`.

## Installation

### Requirements

- Python 3.10+
- Poetry

### Install the project

```bash
poetry install
```

## `XoloClient`

The main HTTP integration surface is `xolo.client.client.XoloClient`.

### Constructor

```python
from xolo.client.client import XoloClient

client = XoloClient(
    account_id="research-account",
    api_key="xk_live_...",
    api_url="http://localhost:10000/api/v4",
    admin_token="admin-token",
)
```

### Why `account_id` and `api_key` are first-class

The live API is centered on account-scoped routes such as:

```text
/api/v4/accounts/{account_id}/users/auth
/api/v4/accounts/{account_id}/rbac/roles
/api/v4/accounts/{account_id}/acl/groups
```

As a result, the client now builds most routes from the configured `account_id`, and `api_key` is used directly on API-key-protected operations. Those public methods also accept an optional per-call `api_key=""` override when one request must use a different key than the client default.

### Return model

Client methods follow the repository convention of returning `option.Result` values:

```python
result = client.list_roles(token=access_token, temporal_secret=temporal_secret)

if result.is_ok:
    roles = result.unwrap()
else:
    error = result.unwrap_err()
```

Successful values are typed DTOs from `xolo.client.models`. Failures are normalized into `xolo.client.errors.XoloError` subclasses.

## Authentication model

The live API uses three complementary auth mechanisms:

1. **`X-Admin-Token`** for admin-only endpoints such as accounts, API keys, scopes, licenses, and admin user lifecycle operations.
2. **`X-API-Key`** for signup/auth and account-scoped authorization APIs.
3. **Bearer token + `Temporal-Secret-Key`** for authenticated user-context calls.

Methods outside the API-key-backed route families do not send `X-API-Key`.

For ACL, ABAC, NGAC, and RBAC methods, the client now supports `admin_token` **or** `api_key` alongside bearer auth; at least one of those headers must be present.

Typical flow:

1. Create or obtain an API key for the account.
2. Sign up or provision a user.
3. Call `auth()` to receive `access_token` and `temporal_secret`.
4. Use those credentials for ACL, ABAC, NGAC, RBAC, and policy-engine operations.

## Entity coverage

The refreshed client covers these entity families from the live OpenAPI contract:

- accounts
- users
- scopes
- licenses
- API keys
- ACL
- ABAC
- NGAC
- RBAC
- global policy-engine endpoints under `/api/v4/policies`

See `docs/entity-operations.md` for the full operation inventory.

## Examples

### Sign up and authenticate

```python
signup = client.signup(
    username="alice",
    first_name="Alice",
    last_name="Smith",
    email="alice@example.com",
    password="secret",
    scope="research",
)

auth = client.auth(
    username="alice",
    password="secret",
    scope="research",
    renew_token=True,
)
```

### Create a scope and a license

```python
client.create_scope("research")
client.assign_scope(username="alice", scope="research", secret="")
client.create_license(username="alice", scope="research", secret="", expires_in="1d")
```

### Create an RBAC role

```python
role = client.create_role(
    name="reader",
    description="Read-only access",
    permissions=["documents:read"],
    token=auth.unwrap().access_token,
    temporal_secret=auth.unwrap().temporal_secret,
    api_key="override-only-if-needed",
    admin_token="admin-override-only-if-needed",
)
```

## Local engines

### `xolo.abac`

Local ABAC policy loading, graph building, and event matching.

### `xolo.acl`

Encrypted ACL persistence with autosave support.

### `xolo.policies`

Policy DTOs, evaluation helpers, and the Xolo-CL DSL parser.

### `xolo.license`

Cryptographic license generation and validation helpers.

### `xolo.utils`

Shared crypto, filesystem, hashing, and key-management helpers.

## Development commands

### Lint

```bash
poetry run ruff check .
```

### Build the package

```bash
poetry build
```

### Build the docs

```bash
poetry run zensical build --clean
```

### Run the non-integration pytest subset

```bash
poetry run pytest tests/test_abac.py tests/test_evaluator.py tests/test_acl.py tests/test_xolo_acl.py tests/test_license.py tests/test_abac_ngac_client.py -q
```

### Run focused client contract tests

```bash
poetry run pytest tests/client/test_client_core.py tests/client/test_client_contracts.py -q
```

### Run the live API-backed flow

```bash
mkdir -p "$PWD/xolo/log"
export XOLO_OUTPUT_PATH="$PWD/xolo"
export XOLO_LOG_PATH="$PWD/xolo/log"
chmod +x deploy.sh && ./deploy.sh
poetry run coverage run -m pytest -v -s
poetry run coverage report -m
```

## Documentation

Project documentation is built with Zensical from `zensical.toml` and `docs/`.

- local build: `poetry run zensical build --clean`
- CI validation: `.github/workflows/docs-ci.yml`
- GitHub Pages deployment: `.github/workflows/docs.yml`

## Publishing

Package publishing remains in `.github/workflows/publish.yml` and uses Poetry to build and upload distributions.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
