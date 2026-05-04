import time as T
from typing import Annotated, Union

from fastapi import Depends
from fastapi.routing import APIRouter
from xolo.log import Log

import xoloapi.config as Cfg
from xoloapi.accounts.dependencies import require_existing_account
import xoloapi.licenses.dto as DTO
from xoloapi.middleware.admin import require_admin_token
from xoloapi.logging import build_log_payload
from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.application.licenses_service import LicensesService
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository

router = APIRouter(
    prefix="/accounts/{account_id}/licenses",
    dependencies=[Depends(require_existing_account)],
)
XOLO_LICENSE_SECRET_KEY = Cfg.XOLO_LICENSE_SECRET_KEY
log = Log(
    name="licenses.controller",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def get_licenses_service() -> LicensesService:
    return LicensesService(
        users_repository=MongoUsersRepository(
            collection=get_collection(CollectionNames.USERS_COLLECTION_NAME),
        ),
        repository=MongoLicensesRepository(
            collection=get_collection(CollectionNames.LICENSES_COLLECTION_NAME),
        ),
        secret_key=XOLO_LICENSE_SECRET_KEY,
    )


@router.get("")
async def list_licenses(
    account_id: str,
    _: object = Depends(require_admin_token),
    licenses_service: LicensesService = Depends(get_licenses_service),
):
    t1 = T.time()
    response = await licenses_service.list_licenses(account_id=account_id)
    if response.is_ok:
        log.info(build_log_payload("licenses.list", started_at=t1, license_count=len(response.unwrap())))
        return response.unwrap()
    error = response.unwrap_err()
    log.error(build_log_payload("licenses.list.error", started_at=t1, error=error))
    raise error.to_http_exception()


@router.post("")
async def create_license(
    account_id: str,
    dto: DTO.AssignLicenseDTO,
    _: object = Depends(require_admin_token),
    licenses_service: LicensesService = Depends(get_licenses_service),
):
    t1 = T.time()
    response = await licenses_service.assign_license(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(
            build_log_payload(
                "licenses.create",
                started_at=t1,
                username=getattr(dto, "username", None),
            )
        )
        return response.unwrap()
    error = response.unwrap_err()
    log.error(
        build_log_payload(
            "licenses.create.error",
            started_at=t1,
            error=error,
            username=getattr(dto, "username", None),
        )
    )
    raise error.to_http_exception()


@router.delete("")
async def delete_license(
    account_id: str,
    dto: DTO.DeleteLicenseDTO,
    _: object = Depends(require_admin_token),
    licenses_service: LicensesService = Depends(get_licenses_service),
):
    t1 = T.time()
    response = await licenses_service.delete_license(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(
            build_log_payload(
                "licenses.delete",
                started_at=t1,
                username=getattr(dto, "username", None),
                license_id=getattr(dto, "license_id", None),
            )
        )
        return response.unwrap()
    error = response.unwrap_err()
    log.error(
        build_log_payload(
            "licenses.delete.error",
            started_at=t1,
            error=error,
            username=getattr(dto, "username", None),
            license_id=getattr(dto, "license_id", None),
        )
    )
    raise error.to_http_exception()


@router.delete("/self")
async def self_delete_license(
    account_id: str,
    dto: DTO.SelfDeleteLicenseDTO,
    licenses_service: LicensesService = Depends(get_licenses_service),
):
    t1 = T.time()
    response = await licenses_service.self_delete_license(account_id=account_id, dto=dto)
    if response.is_ok:
        log.info(
            build_log_payload(
                "licenses.self_delete",
                started_at=t1,
                username=getattr(dto, "username", None),
                license_id=getattr(dto, "license_id", None),
            )
        )
        return response.unwrap()
    error = response.unwrap_err()
    log.error(
        build_log_payload(
            "licenses.self_delete.error",
            started_at=t1,
            error=error,
            username=getattr(dto, "username", None),
            license_id=getattr(dto, "license_id", None),
        )
    )
    raise error.to_http_exception()
