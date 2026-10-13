# Deployment

## Local development

Use the helper script:

```bash
bash run_local.sh
```

This starts MongoDB and Redis with Docker and runs the API locally with `.env.dev`.

## Build the application image

```bash
bash build.sh
```

You can optionally pass an image name and push flag:

```bash
bash build.sh my-registry/xolo-api:0.1.0a5 1
```

## Full Docker deployment

The repository includes a full stack `docker-compose.yml` with MongoDB, Redis, the API, and the Nuxt console.

Start it with:

```bash
./deploy.sh
```

The script:

1. loads `deploy/env/compose.env`
2. creates the Docker network if needed
3. runs `docker compose up -d --build`

The console publishes port `3001` on the host by default (mapped to port `3000` inside the container). Its browser-side API URL defaults to `http://localhost:10000/api/v4`; override `XOLO_UI_API_BASE` when the API is reachable at another address.

## Documentation deployment

The repository also includes a GitHub Pages workflow for the Zensical docs site:

- workflow file: `.github/workflows/docs.yml`
- build command: `poetry run zensical build -f zensical.toml`
- publish target: `site/`

Once GitHub Pages is configured to use GitHub Actions, pushes to `main`, `master`, or `v2` build and publish the API site plus the Python client site under `/client/`.

Image and package publishing use component-specific tags. See [Releases](releases.md).

## Deployment files

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | full stack definition |
| `deploy/env/compose.env` | compose interpolation values |
| `deploy/env/app.prod.env` | API runtime env vars |
| `deploy/env/mongodb.env` | MongoDB container env |
| `deploy/env/redis.env` | Redis container env |

## Health model

The API container healthcheck requests:

```text
/openapi.json
```

MongoDB and Redis are also configured with container healthchecks before the API service is considered ready.

## Production checklist

- replace placeholder secrets
- review `XOLO_JWT_SECRET`
- review `XOLO_LICENSE_SECRET_KEY`
- set `XOLO_PLATFORM_BOOTSTRAP_PASSWORD` to a unique value before the first startup
- set `XOLO_SUPER_ADMIN_TOKENS`
- configure mail provider credentials
- confirm MongoDB and Redis authentication posture
- verify the external port mapping
- put the API behind HTTPS and a reverse proxy if exposed publicly

## Deploying with root_path

If deploying Xolo behind a reverse proxy that serves it at a non-root path (e.g., `https://example.com/api/xolo/`), configure FastAPI's `root_path` parameter:

```python
# In server.py or your deployment configuration
app = FastAPI(
    root_path="/api/xolo",  # Match your reverse proxy path
    # ... other config
)
```

API routes respect the configured `root_path`. Set `NUXT_PUBLIC_API_BASE` (or `XOLO_UI_API_BASE` in Compose) to the externally reachable API prefix used by the browser.
