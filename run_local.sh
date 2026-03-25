#!/bin/bash
docker volume create xolo-db 
docker volume create xolo-cache-data
docker compose -f docker-compose.yml up -d xolo-db
docker compose -f docker-compose.yml up -d xolo-cache
uvicorn xoloapi.server:app --host ${XOLO_HOST-localhost} --port ${XOLO_PORT-10000} --reload --log-level debug