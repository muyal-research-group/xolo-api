# xoloapi/services/scopes.py
from xoloapi.repositories.scopes import ScopesRepository
from commonx.dto.xolo import CreateScopeDTO,AssignScopeDTO,CreatedScopeResponseDTO,AssignedScopeResponseDTO
import xoloapi.errors as EX
from option import Result,Ok,Err
from xolo.log import Log
import time as T
import xoloapi.config as Cfg

log            = Log(
        name                   = "xolo.scopes.service",
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)

class ScopesService(object):
    def __init__(self,repository:ScopesRepository):
        self.repository = repository
    async def assign(self,dto:AssignScopeDTO)->Result[AssignedScopeResponseDTO, EX.XError]:
        try:
            start_time   = T.time()
            dto.name     = dto.name.strip().upper()
            dto.username = dto.username.strip()
            exists_result = await self.repository.exists_scope_user(name=dto.name,username=dto.username)
            if exists_result.is_err:
                return Err(exists_result.unwrap_err())
            exists = exists_result.unwrap()
            if  exists:
                return Err(EX.AlreadyExists(entity="Scope/User",raw_detail="The user is already assigned to the specified scope"))
            
            result        = await self.repository.assign(dto = dto)
            log.info({
                "event":"SCOPE.ASSIGNED",
                "name":dto.name,
                "username":dto.username,
                "response_time":T.time() - start_time
            })
            return Ok(AssignedScopeResponseDTO(name=dto.name, username=dto.username, ok=True))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    async def create(self,dto:CreateScopeDTO)->Result[CreatedScopeResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.name = dto.name.strip().upper()
     
            exists_result = (await self.repository.exists_scope(name=dto.name))
            if exists_result.is_err:
                return Err(exists_result.unwrap_err())
            exists = exists_result.unwrap()
            if exists:
                return Err(EX.AlreadyExists(entity="Scope",raw_detail="A scope with this name already exists."))
            
            result        = await self.repository.create(dto = dto)
            log.info({
                "event":"SCOPE.CREATED",
                "name":dto.name,
                "response_time":T.time() - start_time
            })
            return Ok(CreatedScopeResponseDTO(name=dto.name))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))