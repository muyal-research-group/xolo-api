#!/bin/bash

docker compose -p xolo --env-file .env.dev down
docker compose -p xolo --env-file .env.dev up -d --build
