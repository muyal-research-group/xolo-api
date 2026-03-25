# xoloapi/controllers/scopes.py
import os
from fastapi.routing import APIRouter
from fastapi import Depends,HTTPException
from xoloapi.db import get_collection
import xoloapi.services as S
import xoloapi.repositories as R
import commonx.dto.xolo as DTO
from xolo.log import Log
import xoloapi.config as Cfg

router = APIRouter(prefix="/scopes")
# XOLO_ACL_KEY = CX.XOLO_ACL_KEY
log            = Log(
        name                   = "scopes.controller",
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
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
        log.info({
            "event":"SCOPE_CREATED",
            "scope_name":dto.name
        })
        return response.unwrap()
    e = response.unwrap_err()
    log.error({
        "event":"SCOPE_CREATION_FAILED",
        "reason":e.detail
    })
    raise HTTPException(detail=e.detail, status_code=e.status_code)

@router.post("/assign")
async def assign_scope(
    dto:DTO.AssignScopeDTO,
    scopes_service:S.ScopesService = Depends(get_scopes_service)
):
    response = await scopes_service.assign(dto = dto)
    if response.is_ok:
        log.info({
            "event":"SCOPE_ASSIGNED",
            "scope_id":dto.name,
            "username":dto.username
        })
        return response.unwrap()
    e = response.unwrap_err()
    log.error({
        "event":"SCOPE_ASSIGN_FAILED",
        "scope_id":dto.name,
        "username":dto.username,
        "reason":e.detail
    })
    raise HTTPException(detail=e.detail, status_code=e.status_code)
