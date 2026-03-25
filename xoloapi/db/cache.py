
import redis.asyncio as aioredis  # Importar la versión asyncio
import xoloapi.config  as Cfg
from typing import Optional

redis_pool: Optional[aioredis.ConnectionPool] = None

def get_redis_client() -> Optional[aioredis.Redis]:
    global redis_pool
    if redis_pool is None:
        return None
    
    return aioredis.Redis(connection_pool=redis_pool)

async def connect_to_redis():
    global redis_pool
    if redis_pool is None: 
        redis_pool = aioredis.ConnectionPool.from_url(
            Cfg.XOLO_CACHE_REDIS_URI,
            decode_responses=True
        )
        try:
            client = aioredis.Redis(connection_pool=redis_pool)
            await client.ping()
        except Exception as e:
            print(f"Error connecting to Redis: {e}")
            redis_pool = None
            raise e

async def close_redis_connection():
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None