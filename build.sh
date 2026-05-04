#!/bin/bash
readonly IMG_NAME=${1:-"nachocode/xolo:api-0.0.8a12"}
readonly PUSH=${2:-0}
docker build -f ./Dockerfile -t "$IMG_NAME" .

if [ "$PUSH" -eq 1 ]; then
    docker push "$IMG_NAME"
fi