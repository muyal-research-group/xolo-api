import time as T

from option import Err, Ok, Result
from xoloapi.log import Log

import commonx.errors as EX

import xoloapi.config as Cfg
import xoloapi.scopes.dto as DTO
from xoloapi.logging import build_log_payload
from xoloapi.licenses.domain.repositories import ILicensesRepository
from xoloapi.scopes.domain.repositories import IScopesRepository

log = Log(
    name="xolo.scopes.service",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class ScopesService:
    def __init__(self, repository: IScopesRepository, licenses_repository: ILicensesRepository):
        self.repository = repository
        self.licenses_repository = licenses_repository

    async def list_scopes(self, account_id: str) -> Result[list[DTO.CreatedScopeResponseDTO], EX.XError]:
        start_time = T.time()
        try:
            result = await self.repository.find_all_scopes(account_id=account_id)
            if result.is_err:
                log.error(build_log_payload("scopes.list.error", started_at=start_time, error=result.unwrap_err()))
                return Err(result.unwrap_err())
            response = [DTO.CreatedScopeResponseDTO(name=scope.name) for scope in result.unwrap()]
            log.info(build_log_payload("scopes.list", started_at=start_time, scope_count=len(response)))
            return Ok(response)
        except Exception as e:
            log.error(build_log_payload("scopes.list.error", started_at=start_time, error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def list_assignments(self, account_id: str) -> Result[list[DTO.ScopeAssignmentDTO], EX.XError]:
        start_time = T.time()
        try:
            result = await self.repository.find_all_scope_users(account_id=account_id)
            if result.is_err:
                log.error(build_log_payload("scopes.assignments.list.error", started_at=start_time, error=result.unwrap_err()))
                return Err(result.unwrap_err())
            response = [DTO.ScopeAssignmentDTO(name=assignment.name, username=assignment.username) for assignment in result.unwrap()]
            log.info(build_log_payload("scopes.assignments.list", started_at=start_time, assignment_count=len(response)))
            return Ok(response)
        except Exception as e:
            log.error(build_log_payload("scopes.assignments.list.error", started_at=start_time, error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def delete(self, account_id: str, dto: DTO.CreateScopeDTO) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            dto.name = dto.name.strip().upper()
            log.debug(build_log_payload("scopes.delete.attempt", scope_name=dto.name))

            assignment_count_result = await self.repository.count_scope_users(account_id=account_id, name=dto.name)
            if assignment_count_result.is_err:
                log.error(build_log_payload("scopes.delete.error", started_at=start_time, error=assignment_count_result.unwrap_err(), scope_name=dto.name))
                return Err(assignment_count_result.unwrap_err())
            if assignment_count_result.unwrap() > 0:
                error = EX.AlreadyExists(
                    msg="Scope cannot be deleted while user assignments still exist.",
                    metadata={"entity": "Scope", "id": dto.name},
                )
                log.warning(build_log_payload("scopes.delete.error", started_at=start_time, error=error, scope_name=dto.name))
                return Err(error)

            license_count_result = await self.licenses_repository.count_by_scope(account_id=account_id, scope=dto.name)
            if license_count_result.is_err:
                log.error(build_log_payload("scopes.delete.error", started_at=start_time, error=license_count_result.unwrap_err(), scope_name=dto.name))
                return Err(license_count_result.unwrap_err())
            if license_count_result.unwrap() > 0:
                error = EX.AlreadyExists(
                    msg="Scope cannot be deleted while licenses still exist.",
                    metadata={"entity": "Scope", "id": dto.name},
                )
                log.warning(build_log_payload("scopes.delete.error", started_at=start_time, error=error, scope_name=dto.name))
                return Err(error)

            result = await self.repository.delete(account_id=account_id, name=dto.name)
            if result.is_err:
                log.error(build_log_payload("scopes.delete.error", started_at=start_time, error=result.unwrap_err(), scope_name=dto.name))
                return Err(result.unwrap_err())

            log.info(build_log_payload("scopes.delete", started_at=start_time, scope_name=dto.name))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("scopes.delete.error", started_at=start_time, error=e, scope_name=getattr(dto, "name", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def assign(self, account_id: str, dto: DTO.AssignScopeDTO) -> Result[DTO.AssignedScopeResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.name = dto.name.strip().upper()
            dto.username = dto.username.strip()
            log.debug(build_log_payload("scopes.assign.attempt", scope_name=dto.name, username=dto.username))
            exists_result = await self.repository.exists_scope_user(account_id=account_id, name=dto.name, username=dto.username)
            if exists_result.is_err:
                log.error(build_log_payload("scopes.assign.error", started_at=start_time, error=exists_result.unwrap_err(), scope_name=dto.name, username=dto.username))
                return Err(exists_result.unwrap_err())
            if exists_result.unwrap():
                error = EX.AlreadyExists(msg="The user is already assigned to the specified scope")
                log.warning(build_log_payload("scopes.assign.error", started_at=start_time, error=error, scope_name=dto.name, username=dto.username))
                return Err(error)

            result = await self.repository.assign(account_id=account_id, dto=dto)
            if result.is_err:
                err = result.unwrap_err()
                log.error(build_log_payload("scopes.assign.error", started_at=start_time, error=err, scope_name=dto.name, username=dto.username))
                return Err(err)

            log.info(build_log_payload("scopes.assign", started_at=start_time, scope_name=dto.name, username=dto.username))
            return Ok(DTO.AssignedScopeResponseDTO(name=dto.name, username=dto.username, ok=True))
        except Exception as e:
            log.error(build_log_payload("scopes.assign.error", started_at=start_time, error=e, scope_name=getattr(dto, "name", None), username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def unassign(self, account_id: str, dto: DTO.AssignScopeDTO) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            dto.name = dto.name.strip().upper()
            dto.username = dto.username.strip()
            log.debug(build_log_payload("scopes.unassign.attempt", scope_name=dto.name, username=dto.username))
            result = await self.repository.unassign(account_id=account_id, dto=dto)
            if result.is_err:
                log.error(build_log_payload("scopes.unassign.error", started_at=start_time, error=result.unwrap_err(), scope_name=dto.name, username=dto.username))
                return Err(result.unwrap_err())
            log.info(build_log_payload("scopes.unassign", started_at=start_time, scope_name=dto.name, username=dto.username))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("scopes.unassign.error", started_at=start_time, error=e, scope_name=getattr(dto, "name", None), username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def create(self, account_id: str, dto: DTO.CreateScopeDTO) -> Result[DTO.CreatedScopeResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.name = dto.name.strip().upper()
            log.debug(build_log_payload("scopes.create.attempt", scope_name=dto.name))

            exists_result = await self.repository.exists_scope(account_id=account_id, name=dto.name)
            if exists_result.is_err:
                log.error(build_log_payload("scopes.create.error", started_at=start_time, error=exists_result.unwrap_err(), scope_name=dto.name))
                return Err(exists_result.unwrap_err())
            if exists_result.unwrap():
                error = EX.AlreadyExists(
                    msg="A scope with this name already exists.",
                    metadata={"entity": "Scope", "id": dto.name},
                )
                log.warning(build_log_payload("scopes.create.error", started_at=start_time, error=error, scope_name=dto.name))
                return Err(error)

            result = await self.repository.create(account_id=account_id, dto=dto)
            if result.is_err:
                log.error(build_log_payload("scopes.create.error", started_at=start_time, error=result.unwrap_err(), scope_name=dto.name))
                return Err(result.unwrap_err())

            log.info(build_log_payload("scopes.create", started_at=start_time, scope_name=dto.name))
            return Ok(DTO.CreatedScopeResponseDTO(name=dto.name))
        except Exception as e:
            log.error(build_log_payload("scopes.create.error", started_at=start_time, error=e, scope_name=getattr(dto, "name", None)))
            return Err(EX.ServerError(raw_detail=str(e)))
