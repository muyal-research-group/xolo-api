from fastapi.routing import APIRouter
from fastapi import status, Depends,HTTPException,Header
from xoloapi.db import get_collection
from typing import Annotated, Union
import xoloapi.services as S
import xoloapi.repositories as R
import xoloapi.dto as DTO
import os
from xolo.log import Log

router = APIRouter(prefix="/api/v4/licenses")
XOLO_ACL_KEY = os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2")
log            = Log(
        name   = "users.controller",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
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


@router.post("/")
async def create_license(
    dto: DTO.AssignLicenseDTO,
    secret: Annotated[Union[str,None], Header()]=None,
    licenses_service:S.LicensesService = Depends(get_licenses_service)
):

    if secret == None or not secret == XOLO_ACL_KEY:
        log.error({
            "event":"INVALID.SECRET_KEY"
        })
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await licenses_service.assign_license(dto = dto)
    if response.is_ok:
        return response.unwrap()
    error = response.unwrap_err()
    raise HTTPException(status_code= error.status_code, detail= error.detail)
    
@router.delete("/")
async def delete_license(
    dto: DTO.DeleteLicenseDTO,
    secret: Annotated[Union[str,None], Header()]=None,
    licenses_service:S.LicensesService = Depends(get_licenses_service)
):

    if secret == None or not secret == XOLO_ACL_KEY:
        log.error({
            "event":"INVALID.SECRET_KEY"
        })
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await licenses_service.delete_license(dto = dto)
    if response.is_ok:
        return response.unwrap()
    error = response.unwrap_err()
    raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.delete("/self")
async def self_delete_license(
    dto: DTO.SelfDeleteLicenseDTO,
    licenses_service:S.LicensesService = Depends(get_licenses_service)
):
    # if secret == None or not secret == XOLO_ACL_KEY:
    #     log.error({
    #         "event":"INVALID.SECRET_KEY"
    #     })
    #     raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await licenses_service.self_delete_license(dto = dto)
    if response.is_ok:
        return response.unwrap()
    error = response.unwrap_err()
    raise HTTPException(status_code= error.status_code, detail= error.detail)
