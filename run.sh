#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_ENV_FILE="$ROOT_DIR/deploy/env/compose.env"
APP_ENV_FILE="$ROOT_DIR/.env.dev"

cd "$ROOT_DIR"

export XOLO_ENV_FILE="$APP_ENV_FILE"
exec uvicorn xoloapi.server:app --host 0.0.0.0 --port 10000 --reload --log-level debug
