<p align="center">
  <img src="./assets/logo.png" alt="Xolo" width="220" />
</p>

<p align="center">
  <a href="https://github.com/muyal-research-group/xolo/actions/workflows/ci.yml"><img src="https://github.com/muyal-research-group/xolo/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/muyal-research-group/xolo"><img src="https://codecov.io/gh/muyal-research-group/xolo/branch/master/graph/badge.svg" alt="codecov"></a>
  <a href="https://test.pypi.org/project/xolo/"><img src="https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmuyal-research-group%2Fxolo%2Fmaster%2Fpyproject.toml&query=%24.tool.poetry.version&label=TestPyPI&logo=pypi&color=0A7ABC" alt="TestPyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Fair%20Source-0A7ABC" alt="License"></a>
</p>

<!-- <p align="center"> -->
<!-- <div align="center"> -->
  <!-- <h1>Xolo</h1> -->
  <!-- <p>Python client, local authorization engines, and tooling for the Xolo IAM platform.</p> -->

<!-- </div> -->


<!-- </p> -->

Xolo is a Python package that combines:

- a typed HTTP client for the Xolo IAM API,
- local authorization engines for ACL, ABAC, RBAC, NGAC, and policy evaluation,
- shared cryptographic and utility helpers used by the local engines.

This repository is primarily the **client and local-engine package**. The live API used by the integration tests comes from the local Docker stack in `docker-compose.yml`.

## What changed in the client surface

The current `XoloClient` is centered on **account-scoped APIs**:

```python
from xolo.client.client import XoloClient

client = XoloClient(
    account_id="my-account",
    api_key="xk_live_...",
    api_url="http://localhost:10000/api/v4",
    admin_token="admin-token-for-admin-only-operations",
)
```

Most operations now target `/api/v4/accounts/{account_id}/...`, and the client methods reflect this scoping. For example, instead of `client.create_user(...)`, you would use `client.create_user(account_id="my-account", ...)`. This design emphasizes the account context for all API interactions.

## Package areas

### `xolo.client`

`xolo.client.client.XoloClient` wraps the live HTTP API and returns typed `option.Result` values. Successful calls return DTOs from `xolo.client.models`; failures return `xolo.client.errors.XoloError` subclasses.

### `xolo.abac`

Local ABAC policy loading and evaluation utilities, including graph building and event matching.

### `xolo.acl`

Encrypted local ACL storage with an autosave daemon.

### `xolo.policies`

Policy parser and local policy-engine helpers, including the Xolo-CL DSL.

## Local development shortcuts

```bash
poetry install
poetry run ruff check .
poetry build
poetry run zensical build --clean
```

For the live API-backed test flow, start the local stack first:

```bash
mkdir -p "$PWD/xolo/log"
export XOLO_OUTPUT_PATH="$PWD/xolo"
export XOLO_LOG_PATH="$PWD/xolo/log"
chmod +x deploy.sh && ./deploy.sh
poetry run coverage run -m pytest -v -s
poetry run coverage report -m
```

Continue with the dedicated guides for authentication, entity coverage, and development details.
