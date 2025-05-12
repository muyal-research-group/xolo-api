#!/bin/bash
./build.sh
docker compose -f xolo.yml up -d
