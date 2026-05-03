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
bash build.sh my-registry/xolo-api:0.1.0a0 1
```

## Full Docker deployment

The repository includes a full stack `docker-compose.yml`.

Start it with:

```bash
./deploy.sh
```

The script:

1. loads `deploy/env/compose.env`
2. creates the Docker network if needed
3. runs `docker compose up -d --build`

## Documentation deployment

The repository also includes a GitHub Pages workflow for the Zensical docs site:

- workflow file: `.github/workflows/docs.yml`
- build command: `poetry run zensical build -f zensical.toml`
- publish target: `site/`

Once GitHub Pages is enabled in the repository settings, pushes to the release branch build and publish the docs automatically.

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
- set `XOLO_SUPER_ADMIN_TOKENS`
- configure mail provider credentials
- confirm MongoDB and Redis authentication posture
- verify the external port mapping
- put the API behind HTTPS and a reverse proxy if exposed publicly
