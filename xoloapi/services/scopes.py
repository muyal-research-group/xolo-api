from xoloapi.repositories.scopes import ScopesRepository
from xoloapi.dto.user import CreateScopeDTO,AssignScopeDTO,CreatedScopeResponseDTO,AssignedScopeResponseDTO
import xoloapi.errors as EX
from option import Result,Ok,Err
from xolo.log import Log
import os
import time as T

log            = Log(
        name   = "xolo.scopesservice",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)
class ScopesService(object):
    def __init__(self,repository:ScopesRepository):
        self.repository = repository
    async def assign(self,dto:AssignScopeDTO)->Result[AssignedScopeResponseDTO, EX.XoloError]:
        try:
            start_time = T.time()
            dto.name = dto.name.strip().upper()
            dto.username = dto.username.strip()
            exists_result = await self.repository.exists_scope_user(name=dto.name,username=dto.username)
            if exists_result.is_err:
                return Err(exists_result.unwrap_err())
            exists = exists_result.unwrap()
            if  exists:
                return Err(EX.AlreadyExists(entity="Scope/User"))
            
            result        = await self.repository.assign(dto = dto)
            log.info({
                "event":"SCOPE.ASSIGNED",
                "name":dto.name,
                "username":dto.username,
                "response_time":T.time() - start_time
            })
            return Ok(AssignedScopeResponseDTO(name=dto.name, username=dto.username, ok=True))
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
    async def create(self,dto:CreateScopeDTO)->Result[CreatedScopeResponseDTO, EX.XoloError]:
        try:
            start_time = T.time()
            dto.name = dto.name.strip().upper()
     
            exists_result = (await self.repository.exists_scope(name=dto.name))
            if exists_result.is_err:
                return Err(exists_result.unwrap_err())
            exists = exists_result.unwrap()
            if exists:
                return Err(EX.AlreadyExists(entity="Scope"))
            
            result        = await self.repository.create(dto = dto)
            log.info({
                "event":"SCOPE.CREATED",
                "name":dto.name,
                "response_time":T.time() - start_time
            })
            return Ok(CreatedScopeResponseDTO(name=dto.name))
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))