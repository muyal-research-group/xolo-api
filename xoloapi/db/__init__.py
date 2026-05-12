# xoloapi/db/__init__.py
import time as T

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload
# MONGODB_URI = 
# client                   = MongoClient(MONGODB_URI)
# MONGO_DATABASE_NAME      = 
client = None

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)

# Get the MongoDB client and database instance
def get_database():
    global client
    return  client[Cfg.XOLO_MONGODB_DATABASE_NAME] if client else None 

def get_collection(name:str)->AsyncIOMotorCollection:
    db =  get_database()
    return db[name] if not db is None else None 
# Startup event to initialize the MongoClient when the application starts
async def connect_to_mongo():
    global client
    start_time = T.time()
    try:
        client = AsyncIOMotorClient(Cfg.XOLO_MONGODB_URI)
        await client.admin.command("ping")
        log.info(
            build_log_payload(
                "runtime.mongodb.connect",
                started_at=start_time,
                mongodb_uri=Cfg.XOLO_MONGODB_URI,
                database_name=Cfg.XOLO_MONGODB_DATABASE_NAME,
            )
        )
    except Exception as e:
        client = None
        log.error(
            build_log_payload(
                "runtime.mongodb.connect.error",
                started_at=start_time,
                error=e,
                mongodb_uri=Cfg.XOLO_MONGODB_URI,
                database_name=Cfg.XOLO_MONGODB_DATABASE_NAME,
            )
        )
        raise

# Shutdown event to close the MongoClient when the application shuts down
async def close_mongo_connection():
    global client
    if client is None:
        log.debug(build_log_payload("runtime.mongodb.disconnect.skipped"))
        return

    start_time = T.time()
    client.close()
    client = None
    log.info(build_log_payload("runtime.mongodb.disconnect", started_at=start_time))
