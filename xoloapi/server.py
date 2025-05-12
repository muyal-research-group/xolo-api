# 
from xolo.log import Log
# 
from xoloapi.dto.acl import GrantsDTO,CheckDTO
from xoloapi.db import connect_to_mongo,close_mongo_connection
from xoloapi.controllers import licenses_router,scopes_router,users_router,policies_router
# 
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

log            = Log(
        name   = "xolo-api",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)





@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield 
    await close_mongo_connection()


app = FastAPI(
    root_path=os.environ.get("OPENAPI_PREFIX","/xoloapi"),
    title= os.environ.get("OPENAPI_TITLE","Xolo: Identity & Accesss Management"),
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def generate_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Xolo - API",
        version="0.0.1",
        summary="This API enable the manipulation of observatories and catalogs",
        description="",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": os.environ.get("OPENAPI_LOGO","")
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema
app.openapi = generate_openapi

app.include_router(users_router)
app.include_router(licenses_router)
app.include_router(scopes_router)
app.include_router(policies_router)
        







