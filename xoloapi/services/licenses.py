import xoloapi.repositories as R
import xoloapi.dto as DTO
import xoloapi.errors as EX
import option as OP
import humanfriendly as HF
from datetime import datetime,timedelta,timezone
import time as T
from xolo.license import LicenseManager
from xolo.log import Log
from zoneinfo import ZoneInfo
import os

log            = Log(
        name   = "xolo.licensesservice",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)
class LicensesService(object):
    def __init__(self, repository:R.LicensesRepository,secret_key:str):
        self.repository = repository
        self.lm = LicenseManager(secret_key=secret_key.encode())
        self.tz  = ZoneInfo("America/Mexico_City")
    
    def delete_license(self,dto:DTO.DeleteLicenseDTO)->OP.Result[DTO.DeletedLicenseResponseDTO,EX.XoloError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            result = self.repository.delete_by_username_scope(username=dto.username, scope=dto.scope)
            if result.is_err:
                return OP.Err(result.unwrap_err())
            log.info({
                "event":"DELETED.LICENSE",
                "username":dto.username,
                "scope":dto.scope,
                "response_time":T.time()-start_time
            })
            return  OP.Ok(DTO.DeletedLicenseResponseDTO(ok = result.unwrap_err(False)))
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))
    def assign_license(self,dto:DTO.AssignLicenseDTO)->OP.Result[DTO.AssignLicenseResponseDTO, EX.XoloError]:
        try:
            start_time = T.time()
            dto.username   = dto.username.strip()
            dto.scope      = dto.scope.strip().upper()
            log.debug({
                "event":"ASSIGN.LICENSE",
                "username":dto.username,
                "scope":dto.scope,
            })
            current_license_result = self.repository.find_by_username_and_scope(
                username=dto.username,
                scope=dto.scope
            )
            # print("CURRENT_LICENSE", current_license_result)
            if current_license_result.is_err:
                is_valid = False
            else:
                current_license = current_license_result.unwrap()
                is_valid        = self.lm.verify(user_id=dto.username, app_id=dto.scope, license_key=current_license).unwrap_or(False)
            
            if dto.force or not is_valid:
                delete_result  = self.repository.delete_by_username_scope(username=dto.username, scope= dto.scope)
                license_result = self.lm.generate_license(user_id=dto.username, app_id=dto.scope,expires_in=dto.expires_in)
                
                if license_result.is_err:
                    return OP.Err(EX.LicenseCreationError())
                license        = license_result.unwrap()
                expires_at     = (datetime.now(timezone.utc) + timedelta(seconds=int(HF.parse_timespan(dto.expires_in)))).astimezone(self.tz)
                expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S %Z")
                result         = self.repository.create(username=dto.username, license=license, scope=dto.scope,expires_at = expires_at_str)
                
                if result.is_err:
                    return OP.Err(result.unwrap_err())
                log.info({
                    "event":"ASSIGNED.LICENSE",
                    "username":dto.username,
                    "scope":dto.scope,
                    "response_time":T.time()-start_time
                })
                return OP.Ok(DTO.AssignLicenseResponseDTO(expires_at=expires_at_str,ok=result.unwrap_or(False)))
            else: 
                return OP.Err(EX.AlreadyExists(entity="License"))
            
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))