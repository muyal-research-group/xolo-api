# Development

## Install dependencies

```bash
poetry install
```

## Lint and build

```bash
poetry run ruff check .
poetry build
poetry run zensical build --clean
```

## Tests

Run the non-integration subset:

```bash
poetry run pytest tests/test_abac.py tests/test_evaluator.py tests/test_acl.py tests/test_xolo_acl.py tests/test_license.py tests/test_abac_ngac_client.py -q
```

Run a focused client unit-style subset:

```bash
poetry run pytest tests/client/test_client_core.py tests/client/test_client_contracts.py -q
```

Run the live API-backed flow after the local stack is available:

```bash
mkdir -p "$PWD/xolo/log"
export XOLO_OUTPUT_PATH="$PWD/xolo"
export XOLO_LOG_PATH="$PWD/xolo/log"
chmod +x deploy.sh && ./deploy.sh
poetry run coverage run -m pytest -v -s
poetry run coverage report -m
```

## Documentation

The docs site is driven by `zensical.toml` and the `docs/` tree.

Local build:

```bash
poetry run zensical build --clean
```

GitHub Actions:

- `docs-ci.yml` validates documentation builds in CI.
- `docs.yml` publishes the built site to GitHub Pages on pushes to the main branch set.
