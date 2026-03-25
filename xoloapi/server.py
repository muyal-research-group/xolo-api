# 
from xolo.log import Log
# 
from xoloapi.db import connect_to_mongo,close_mongo_connection
from xoloapi.controllers import licenses_router,scopes_router,users_router,policies_router,acl_router
# 
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from xoloapi.db.cache import connect_to_redis, close_redis_connection
import xoloapi.config  as Cfg

log            = Log(
        name                   = Cfg.XOLO_LOG_NAME,
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)





@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await connect_to_redis()
    yield 
    await close_mongo_connection()
    await close_redis_connection()


app = FastAPI(
    root_path = Cfg.XOLO_OPENAPI_PREFIX,
    title     = Cfg.XOLO_OPENAPI_TITLE,
    lifespan  = lifespan
)





app.add_middleware(
    CORSMiddleware,
    allow_origins     = Cfg.XOLO_CORS_ALLOW_ORIGINS,
    allow_credentials = Cfg.XOLO_CORS_CREDENTIALS,
    allow_methods     = Cfg.XOLO_CORS_ALLOW_METHODS,
    allow_headers     = Cfg.XOLO_CORS_ALLOW_HEADERS
)

def generate_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title       = Cfg.XOLO_OPENAPI_TITLE,
        version     = Cfg.XOLO_OPENAPI_VERSION,
        summary     = Cfg.XOLO_OPENAPI_SUMMARY,
        description = Cfg.XOLO_OPENAPI_DESCRIPTION,
        routes      = app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": Cfg.XOLO_OPENAPI_LOGO
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema
app.openapi = generate_openapi

app.include_router(users_router,prefix="/api/v4",tags=["users"])
app.include_router(licenses_router,prefix="/api/v4",tags=["licenses"])
app.include_router(scopes_router,prefix="/api/v4",tags=["scopes"])
app.include_router(policies_router,prefix="/api/v4",tags=["policies"])
app.include_router(acl_router,prefix="/api/v4",tags=["acl"])       






