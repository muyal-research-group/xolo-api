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
import jwt

log            = Log(
        name   = "xolo.licensesservice",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)
class LicensesService(object):
    def __init__(self, 
            repository:R.LicensesRepository,
            users_repository:R.UsersRepository,
            secret_key:str
        ):
        self.users_repository = users_repository
        self.repository = repository
        self.lm = LicenseManager(secret_key=secret_key.encode())
        self.tz  = ZoneInfo("America/Mexico_City")
    
    async def self_delete_license(self,dto:DTO.SelfDeleteLicenseDTO)->OP.Result[DTO.DeletedLicenseResponseDTO,EX.XoloError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            try: 
                decoded = jwt.decode(jwt= dto.token, key=dto.tmp_secret_key,algorithms="HS256")
                self_scope = decoded.get("iss","")
                self_username = decoded.get("uid2","")
                print(decoded)
                if self_scope != dto.scope or self_username != dto.username:
                    return OP.Err(EX.Unauthorized(message="Permission denied: you do not have rights to delete licenses assigned to other users"))
            except jwt.ExpiredSignatureError:
                return OP.Err(EX.TokenExpired())
            except jwt.InvalidTokenError:
                return OP.Err(EX.Unauthorized(message="Token is invalid"))
            except Exception as e:
                raise e
            # token = dto.token

            result = await self.repository.delete_by_username_scope(username=dto.username, scope=dto.scope)
            if result.is_err:
                return OP.Err(result.unwrap_err())
            log.info({
                "event":"DELETED.LICENSE",
                "username":dto.username,
                "scope":dto.scope,
                "response_time":T.time()-start_time
            })
            return  OP.Ok(DTO.DeletedLicenseResponseDTO(ok = result.unwrap_or(False)))
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))
    async def delete_license(self,dto:DTO.DeleteLicenseDTO)->OP.Result[DTO.DeletedLicenseResponseDTO,EX.XoloError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            result = await self.repository.delete_by_username_scope(username=dto.username, scope=dto.scope)
            if result.is_err:
                return OP.Err(result.unwrap_err())
            log.info({
                "event":"DELETED.LICENSE",
                "username":dto.username,
                "scope":dto.scope,
                "response_time":T.time()-start_time
            })
            return  OP.Ok(DTO.DeletedLicenseResponseDTO(ok = result.unwrap_or(False)))
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))
    async def assign_license(self,dto:DTO.AssignLicenseDTO)->OP.Result[DTO.AssignLicenseResponseDTO, EX.XoloError]:
        try:
            start_time = T.time()
            dto.username   = dto.username.strip()
            dto.scope      = dto.scope.strip().upper()
            log.debug({
                "event":"ASSIGN.LICENSE",
                "username":dto.username,
                "scope":dto.scope,
            })
            current_license_result = await self.repository.find_by_username_and_scope(
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
                delete_result  = await self.repository.delete_by_username_scope(username=dto.username, scope= dto.scope)
                license_result = self.lm.generate_license(user_id=dto.username, app_id=dto.scope,expires_in=dto.expires_in)
                
                if license_result.is_err:
                    return OP.Err(EX.LicenseCreationError())
                license        = license_result.unwrap()
                expires_at     = (datetime.now(timezone.utc) + timedelta(seconds=int(HF.parse_timespan(dto.expires_in)))).astimezone(self.tz)
                expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S %Z")
                result         = await self.repository.create(username=dto.username, license=license, scope=dto.scope,expires_at = expires_at_str)
                
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