import redis.asyncio as aioredis  # Importar la versión asyncio
from typing import Optional
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)

redis_pool: Optional[aioredis.ConnectionPool] = None

def get_redis_client() -> Optional[aioredis.Redis]:
    global redis_pool
    if redis_pool is None:
        return None
    
    return aioredis.Redis(connection_pool=redis_pool)

async def connect_to_redis():
    global redis_pool
    if redis_pool is None:
        start_time = __import__("time").time()
        redis_pool = aioredis.ConnectionPool.from_url(
            Cfg.XOLO_CACHE_REDIS_URI,
            decode_responses=True
        )
        try:
            client = aioredis.Redis(connection_pool=redis_pool)
            await client.ping()
            log.info(
                build_log_payload(
                    "runtime.redis.connect",
                    started_at=start_time,
                    redis_uri=Cfg.XOLO_CACHE_REDIS_URI,
                )
            )
        except Exception as e:
            log.error(
                build_log_payload(
                    "runtime.redis.connect.error",
                    started_at=start_time,
                    error=e,
                    redis_uri=Cfg.XOLO_CACHE_REDIS_URI,
                )
            )
            redis_pool = None
            raise e
    else:
        log.debug(build_log_payload("runtime.redis.connect.skipped", redis_uri=Cfg.XOLO_CACHE_REDIS_URI))

async def close_redis_connection():
    global redis_pool
    if redis_pool:
        start_time = __import__("time").time()
        await redis_pool.disconnect()
        redis_pool = None
        log.info(build_log_payload("runtime.redis.disconnect", started_at=start_time))
