# xoloapi/controllers/licenses.py
from fastapi.routing import APIRouter
import time as T
from fastapi import status, Depends,HTTPException,Header
from xoloapi.db import get_collection
from typing import Annotated, Union
import xoloapi.services as S
import xoloapi.repositories as R
from xolo.log import Log
import xoloapi.config  as Cfg

import commonx.dto.xolo as DTO

router       = APIRouter(prefix="/licenses")
XOLO_ACL_KEY = Cfg.XOLO_ACL_KEY


log            = Log(
        name                   = "licenses.controller",
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)

def get_licenses_service()->S.LicensesService:
    service = S.LicensesService(
        users_repository= R.UsersRepository(
            collection= get_collection("users")
        ),
        repository=R.LicensesRepository(
            collection=get_collection("licenses")
        ),
        secret_key=XOLO_ACL_KEY
    )
    return service


@router.post("")
async def create_license(
    dto: DTO.AssignLicenseDTO,
    secret: Annotated[Union[str,None], Header()]=None,
    licenses_service:S.LicensesService = Depends(get_licenses_service)
):
    t1 = T.time()
    if secret == None or not secret == XOLO_ACL_KEY:
        log.error({
            "event":"INVALID.SECRET_KEY"
        })
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await licenses_service.assign_license(dto = dto)
    if response.is_ok:
        log.info({
            "event":"LICENSE_CREATED",
            "response_time":T.time()-t1
        })
        return response.unwrap()
    error = response.unwrap_err()
    log.info({
        "event":"LICENSE_CREATION_FAILED",
        "detail":error.detail
    })
    raise HTTPException(status_code= error.status_code, detail= error.detail)
    
@router.delete("")
async def delete_license(
    dto: DTO.DeleteLicenseDTO,
    secret: Annotated[Union[str,None], Header()]=None,
    licenses_service:S.LicensesService = Depends(get_licenses_service)
):
    t1 = T.time()
    if secret == None or not secret == XOLO_ACL_KEY:
        log.error({
            "event":"INVALID.SECRET_KEY"
        })
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await licenses_service.delete_license(dto = dto)
    if response.is_ok:
        log.info({
            "event":"LICENSE.DELETED",
            "response_time":T.time()-t1
        })
        return response.unwrap()
    error = response.unwrap_err()
    log.info({
        "event":"LICENSE.DELETION.FAILED",
        "detail":error.detail
    })
    raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.delete("/self")
async def self_delete_license(
    dto: DTO.SelfDeleteLicenseDTO,
    licenses_service:S.LicensesService = Depends(get_licenses_service)
):
    t1 = T.time()
    response = await licenses_service.self_delete_license(dto = dto)
    if response.is_ok:
        log.info({
            "event":"LICENSE.SELF_DELETED",
            "response_time":T.time()-t1
        })
        return response.unwrap()
    
    error = response.unwrap_err()
    log.info({
        "event":"LICENSE.SELF_DELETION.FAILED",
        "detail":error.detail
    })
    raise HTTPException(status_code= error.status_code, detail= error.detail)
