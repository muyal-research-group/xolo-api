# xoloapi/controllers/scopes.py
import os
from fastapi.routing import APIRouter
from fastapi import Depends,HTTPException
from xoloapi.db import get_collection
import xoloapi.services as S
import xoloapi.repositories as R
import xoloapi.dto as DTO
from xolo.log import Log

router = APIRouter(prefix="/api/v4/scopes")
XOLO_ACL_KEY = os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2")
log            = Log(
        name   = "users.controller",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)

def get_scopes_service()->S.ScopesService:
    repository = R.ScopesRepository(
        collection= get_collection(name="scopes"),
        scope_user_collection= get_collection("scopes_users")
    )
    service = S.ScopesService(repository= repository)
    return service

@router.post("/")
async def create_scope(
    dto:DTO.CreateScopeDTO,
    scopes_service:S.ScopesService = Depends(get_scopes_service)
):
    response = await scopes_service.create(dto = dto)
    if response.is_ok:
        return response.unwrap()
    e = response.unwrap_err()
    raise HTTPException(detail=e.detail, status_code=e.status_code)

@router.post("/assign")
async def assign_scope(
    dto:DTO.AssignScopeDTO,
    scopes_service:S.ScopesService = Depends(get_scopes_service)
):
    response = await scopes_service.assign(dto = dto)
    if response.is_ok:
        return response.unwrap()
    e = response.unwrap_err()
    raise HTTPException(detail=e.detail, status_code=e.status_code)
