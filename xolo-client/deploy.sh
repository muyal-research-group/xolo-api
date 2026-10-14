#!/bin/bash
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml --env-file .env.dev up -d 
