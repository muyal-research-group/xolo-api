from datetime import datetime, timedelta, timezone
import time as T

import humanfriendly as HF
import jwt
import option as OP
from xolo.license import LicenseManager
from xoloapi.log import Log
from zoneinfo import ZoneInfo

import commonx.errors as EX

import xoloapi.config as Cfg
import xoloapi.licenses.dto as DTO
from xoloapi.log.format import build_log_payload
from xoloapi.licenses.domain.repositories import ILicensesRepository

log = Log(
    name="xolo.licenses.service",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class LicensesService:
    def __init__(self, repository: ILicensesRepository, users_repository, secret_key: str):
        self.users_repository = users_repository
        self.repository = repository
        self.lm = LicenseManager(secret_key=secret_key.encode())
        self.tz = ZoneInfo("America/Mexico_City")

    async def list_licenses(self, account_id: str) -> OP.Result[list[DTO.LicenseSummaryDTO], EX.XError]:
        start_time = T.time()
        try:
            result = await self.repository.find_all(account_id=account_id)
            if result.is_err:
                log.error(build_log_payload("licenses.list.error", started_at=start_time, error=result.unwrap_err()))
                return OP.Err(result.unwrap_err())
            response = [
                DTO.LicenseSummaryDTO(
                    username=license.username,
                    scope=license.scope,
                    expires_at=license.expires_at,
                )
                for license in result.unwrap()
            ]
            log.info(build_log_payload("licenses.list", started_at=start_time, license_count=len(response)))
            return OP.Ok(response)
        except Exception as e:
            log.error(build_log_payload("licenses.list.error", started_at=start_time, error=e))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def self_delete_license(self, account_id: str, dto: DTO.SelfDeleteLicenseDTO) -> OP.Result[DTO.DeletedLicenseResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            log.debug(build_log_payload("licenses.self_delete.attempt", username=dto.username, scope_name=dto.scope))
            try:
                decoded = jwt.decode(jwt=dto.token, key=dto.tmp_secret_key, algorithms=["HS256"])
                self_scope = decoded.get("iss", "")
                self_username = decoded.get("uid2", "")
                if self_scope != dto.scope or self_username != dto.username:
                    error = EX.Unauthorized(
                        raw_detail="Permission denied: you do not have rights to delete licenses assigned to other users"
                    )
                    log.warning(build_log_payload("licenses.self_delete.error", started_at=start_time, error=error, username=dto.username, scope_name=dto.scope))
                    return OP.Err(
                        error
                    )
            except jwt.ExpiredSignatureError as e:
                log.warning(build_log_payload("licenses.self_delete.error", started_at=start_time, error=e, username=dto.username, scope_name=dto.scope))
                return OP.Err(EX.TokenExpired(raw_detail=str(e)))
            except jwt.InvalidTokenError as e:
                log.warning(build_log_payload("licenses.self_delete.error", started_at=start_time, error=e, username=dto.username, scope_name=dto.scope))
                return OP.Err(EX.Unauthorized(raw_detail=str(e)))
            except Exception as e:
                log.warning(build_log_payload("licenses.self_delete.error", started_at=start_time, error=e, username=dto.username, scope_name=dto.scope))
                return OP.Err(EX.Unauthorized(raw_detail=str(e)))

            result = await self.repository.delete_by_username_scope(account_id=account_id, username=dto.username, scope=dto.scope)
            if result.is_err:
                log.error(build_log_payload("licenses.self_delete.error", started_at=start_time, error=result.unwrap_err(), username=dto.username, scope_name=dto.scope))
                return OP.Err(result.unwrap_err())

            log.info(build_log_payload("licenses.self_delete", started_at=start_time, username=dto.username, scope_name=dto.scope))
            return OP.Ok(DTO.DeletedLicenseResponseDTO(ok=result.unwrap_or(False)))
        except Exception as e:
            log.error(build_log_payload("licenses.self_delete.error", started_at=start_time, error=e, username=getattr(dto, "username", None), scope_name=getattr(dto, "scope", None)))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def delete_license(self, account_id: str, dto: DTO.DeleteLicenseDTO) -> OP.Result[DTO.DeletedLicenseResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            log.debug(build_log_payload("licenses.delete.attempt", username=dto.username, scope_name=dto.scope))
            result = await self.repository.delete_by_username_scope(account_id=account_id, username=dto.username, scope=dto.scope)
            if result.is_err:
                log.error(build_log_payload("licenses.delete.error", started_at=start_time, error=result.unwrap_err(), username=dto.username, scope_name=dto.scope))
                return OP.Err(result.unwrap_err())
            log.info(build_log_payload("licenses.delete", started_at=start_time, username=dto.username, scope_name=dto.scope))
            return OP.Ok(DTO.DeletedLicenseResponseDTO(ok=result.unwrap_or(False)))
        except Exception as e:
            log.error(build_log_payload("licenses.delete.error", started_at=start_time, error=e, username=getattr(dto, "username", None), scope_name=getattr(dto, "scope", None)))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def rotate_license(self, account_id: str, dto: DTO.RotateLicenseDTO) -> OP.Result[DTO.AssignLicenseResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            username = dto.username.strip()
            scope = dto.scope.strip().upper()
            log.debug(build_log_payload("licenses.rotate.attempt", username=username, scope_name=scope))

            existing = await self.repository.find_by_username_and_scope(account_id=account_id, username=username, scope=scope)
            if existing.is_err:
                log.warning(build_log_payload("licenses.rotate.error", started_at=start_time, error=existing.unwrap_err(), username=username, scope_name=scope))
                return OP.Err(existing.unwrap_err())

            await self.repository.delete_by_username_scope(account_id=account_id, username=username, scope=scope)
            license_result = self.lm.generate_license(user_id=username, app_id=scope, expires_in=dto.expires_in)
            if license_result.is_err:
                error = EX.LicenseCreationError(raw_detail=str(license_result.unwrap_err()))
                log.error(build_log_payload("licenses.rotate.error", started_at=start_time, error=error, username=username, scope_name=scope))
                return OP.Err(error)

            license = license_result.unwrap()
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(HF.parse_timespan(dto.expires_in)))
            ).astimezone(self.tz)
            expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S %Z")
            result = await self.repository.create(
                account_id=account_id,
                username=username,
                license=license,
                scope=scope,
                expires_at=expires_at_str,
            )
            if result.is_err:
                log.error(build_log_payload("licenses.rotate.error", started_at=start_time, error=result.unwrap_err(), username=username, scope_name=scope))
                return OP.Err(result.unwrap_err())

            log.info(build_log_payload("licenses.rotate", started_at=start_time, username=username, scope_name=scope, expires_at=expires_at_str))
            return OP.Ok(DTO.AssignLicenseResponseDTO(expires_at=expires_at_str, ok=result.unwrap_or(False)))
        except Exception as e:
            log.error(build_log_payload("licenses.rotate.error", started_at=start_time, error=e, username=getattr(dto, "username", None), scope_name=getattr(dto, "scope", None)))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def assign_license(self, account_id: str, dto: DTO.AssignLicenseDTO) -> OP.Result[DTO.AssignLicenseResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            log.debug(build_log_payload("licenses.assign.attempt", username=dto.username, scope_name=dto.scope, force=dto.force))

            current_license_result = await self.repository.find_by_username_and_scope(
                account_id=account_id,
                username=dto.username,
                scope=dto.scope,
            )
            if current_license_result.is_err:
                is_valid = False
            else:
                current_license = current_license_result.unwrap()
                is_valid = self.lm.verify(
                    user_id=dto.username,
                    app_id=dto.scope,
                    license_key=current_license,
                ).unwrap_or(False)

            if dto.force or not is_valid:
                await self.repository.delete_by_username_scope(account_id=account_id, username=dto.username, scope=dto.scope)
                license_result = self.lm.generate_license(
                    user_id=dto.username,
                    app_id=dto.scope,
                    expires_in=dto.expires_in,
                )
                if license_result.is_err:
                    error = EX.LicenseCreationError(raw_detail=str(license_result.unwrap_err()))
                    log.error(build_log_payload("licenses.assign.error", started_at=start_time, error=error, username=dto.username, scope_name=dto.scope))
                    return OP.Err(error)

                license = license_result.unwrap()
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=int(HF.parse_timespan(dto.expires_in)))
                ).astimezone(self.tz)
                expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S %Z")
                result = await self.repository.create(
                    account_id=account_id,
                    username=dto.username,
                    license=license,
                    scope=dto.scope,
                    expires_at=expires_at_str,
                )
                if result.is_err:
                    log.error(build_log_payload("licenses.assign.error", started_at=start_time, error=result.unwrap_err(), username=dto.username, scope_name=dto.scope))
                    return OP.Err(result.unwrap_err())

                log.info(build_log_payload("licenses.assign", started_at=start_time, username=dto.username, scope_name=dto.scope, expires_at=expires_at_str))
                return OP.Ok(DTO.AssignLicenseResponseDTO(expires_at=expires_at_str, ok=result.unwrap_or(False)))

            error = EX.AlreadyExists(
                entity="License",
                raw_detail="A valid license already exists for this user and scope",
            )
            log.warning(build_log_payload("licenses.assign.error", started_at=start_time, error=error, username=dto.username, scope_name=dto.scope))
            return OP.Err(error)
        except Exception as e:
            log.error(build_log_payload("licenses.assign.error", started_at=start_time, error=e, username=getattr(dto, "username", None), scope_name=getattr(dto, "scope", None)))
            return OP.Err(EX.ServerError(raw_detail=str(e)))
