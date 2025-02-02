#!/bin/bash
docker volume create xolo-db 
docker compose -f xolo.yml up -d xolo-db
uvicorn xoloapi.server:app --host ${XOLO_HOST-localhost} --port ${XOLO_PORT-10000} --reload --log-level debug