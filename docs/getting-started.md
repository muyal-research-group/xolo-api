# Getting started

## Requirements

- Python 3.10+
- Poetry
- Docker and Docker Compose

## Install dependencies

```bash
poetry install
```

## Run the local development stack

The easiest local entrypoint is:

```bash
bash run_local.sh
```

That script:

1. ensures the Docker network exists
2. starts MongoDB and Redis
3. sets `XOLO_ENV_FILE=.env.dev`
4. runs Uvicorn with reload enabled on port `10000`

## Manual startup

If you want to start the app yourself:

```bash
XOLO_ENV_FILE=.env.dev uvicorn xoloapi.server:app --reload --host 0.0.0.0 --port 10000
```

For a new database, set `XOLO_PLATFORM_BOOTSTRAP_PASSWORD` to a unique value of at least 12 characters before starting the API. In another terminal, start the console with the already installed UI dependencies:

```bash
cd xolo-ui
pnpm dev
```

## Useful URLs

- API root: `http://localhost:10000`
- OpenAPI UI: `http://localhost:10000/docs`
- Platform console: `http://localhost:3000`
- OpenAPI JSON: `http://localhost:10000/openapi.json`

## First account-aware steps

A typical bootstrap flow is:

1. sign in to the local console with the bootstrap platform administrator and change its password
2. create an account in the console or with `POST /api/v4/accounts`
3. create an account-owned API key with `POST /api/v4/accounts/{account_id}/apikeys`
4. use that key on account-scoped user auth/signup routes such as `POST /api/v4/accounts/{account_id}/users/auth`
5. manage account resources through the console or the matching `/api/v4/accounts/{account_id}/...` endpoints

## Running tests

Run everything:

```bash
poetry run pytest
```

Useful targeted commands:

```bash
poetry run pytest tests/test_services.py::test_main_logic
poetry run pytest tests/ngac/test_ngac_graph.py::test_and_rule_user_satisfies_both_pcs
poetry run pytest tests/abac/test_abac_controller.py -k evaluate
poetry run coverage run -m pytest && poetry run coverage report
```

## Working on documentation

This repository ships with a native Zensical docs site.

Serve it locally:

```bash
poetry run zensical serve
```

Build it:

```bash
poetry run zensical build
```
