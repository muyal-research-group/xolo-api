#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_ENV_FILE="${1:-$ROOT_DIR/deploy/env/compose.env}"

cd "$ROOT_DIR"

set -a
source "$COMPOSE_ENV_FILE"
set +a

docker network inspect "${XOLO_NETWORK_NAME:-xolo-net}" >/dev/null 2>&1 || \
  docker network create "${XOLO_NETWORK_NAME:-xolo-net}"

docker compose --env-file "$COMPOSE_ENV_FILE" up -d --build
