#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_ENV_FILE="$ROOT_DIR/deploy/env/compose.env"
APP_ENV_FILE="$ROOT_DIR/.env.dev"

cd "$ROOT_DIR"

set -a
source "$COMPOSE_ENV_FILE"
set +a

docker network inspect "${XOLO_NETWORK_NAME:-xolo-net}" >/dev/null 2>&1 || \
  docker network create "${XOLO_NETWORK_NAME:-xolo-net}"

docker compose --env-file "$COMPOSE_ENV_FILE" up -d xolo-db xolo-cache

export XOLO_ENV_FILE="$APP_ENV_FILE"
exec uvicorn xoloapi.server:app --host 0.0.0.0 --port 10000 --reload --log-level debug
