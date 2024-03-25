#!/bin/bash
docker run \
-e  MONGO_IP_ADDR="mongol" \
-e MONGO_PORT="27017" \
-e MONGO_DATABASE_NAME="mictlanx" \
-e IP_ADDR="0.0.0.0" \
-e PORT="10001" \
-e RELOAD="0" \
--name xolo-api \
--network="mictlanx" \
-p 10001:10001 \
-d \
nachocode/xolo:api
