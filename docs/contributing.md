# Contributing

## Development workflow

1. fork or branch from the main line
2. install dependencies with `poetry install`
3. start local services with `bash run_local.sh`
4. make focused changes
5. add or update tests
6. update documentation when behavior or configuration changes

## Codebase conventions

### Keep controllers thin

Controllers should focus on:

- request parsing
- FastAPI dependency injection
- calling services
- structured logging
- translating typed errors to HTTP exceptions

### Put business rules in services

Service methods own orchestration and policy decisions.

### Keep repositories focused on I/O

Repositories should perform persistence work and return `Result` / `Option` values rather than shaping HTTP behavior.

### Preserve the error model

Prefer:

- `Ok(value)`
- `Err(EX.SomeError(...))`

instead of using exceptions for expected control flow.

## Testing guidance

Main command:

```bash
poetry run pytest
```

Coverage:

```bash
poetry run coverage run -m pytest && poetry run coverage report
```

Most tests assume MongoDB is reachable at `mongodb://localhost:27018`, and some controller-level tests also require Redis.

The repository CI workflow (`.github/workflows/ci.yml`) runs the full test suite with coverage and uploads `coverage.xml` to Codecov. For private repositories, set `CODECOV_TOKEN` in GitHub Actions secrets.

## Documentation workflow

The docs site is Markdown-based and uses native Zensical configuration.

```bash
poetry run zensical serve
poetry run zensical build
```

The docs workflow (`.github/workflows/docs.yml`) publishes the generated `site/` output to GitHub Pages.

Keep `README.md` and `docs/` aligned when changing:

- API behavior
- deployment steps
- environment variables
- architecture or module boundaries
