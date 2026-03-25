
# xoloapi/services/users.py
import time as T
import xoloapi.repositories as R
import xoloapi.dto as DTO 
from xoloapi.services.licenses import LicensesService
from option import Ok,Result,Err
from xolo.log import Log
import xoloapi.errors as EX
from xolo.utils import Utils as XoloUtils
from datetime import datetime,timezone,timedelta
from uuid import uuid4
import jwt
import xoloapi.config as Cfg
import humanfriendly  as HF
from xoloapi.security import Security

log            = Log(
    name                   = "xolo.users.service",
    console_handler_filter = lambda x: True,
    interval               = Cfg.XOLO_LOG_INTERVAL,
    when                   = Cfg.XOLO_LOG_WHEN,
    path                   = Cfg.XOLO_LOG_PATH
)

class UsersService(object):
    def __init__(self, 
        repository:R.UsersRepository,
        scopes_repository:R.ScopesRepository,
        licenses_service:LicensesService
    ):
        self.repository        = repository
        self.scopes_repository = scopes_repository
        self.licenses_service  = licenses_service

    async def get_by_id(self,user_id:str)->Result[DTO.UserDTO,EX.XError]:
        try:
            maybe_user = await self.repository.find_by_id(user_id=user_id)
            if maybe_user.is_none:
                return Err(EX.NotFound(raw_detail="User not found"))
            user       = maybe_user.unwrap()
            user_dto   = DTO.UserDTO(
                key           = user.key,
                username      = user.username,
                first_name    = user.first_name,
                last_name     = user.last_name,
                email         = user.email,
                profile_photo = user.profile_photo,
            )
            return Ok(user_dto)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        

    async def logout(self,dto:DTO.LogoutDTO)->Result[bool,EX.XError]:
        try:
            _username   = dto.username.strip()
            maybe_user  = await self.repository.find_by_username(username=_username)
            if maybe_user.is_none:
                return Err(EX.NotFound(raw_detail="User not found"))
            user           = maybe_user.unwrap()
            # Here you can implement token invalidation logic if needed
            res = await self.repository.delete_access_token(username=_username)
            if res.is_err:
                log.error({
                    "event":"USER.LOGOUT.ERROR",
                    "username":_username,
                    "detail":str(res.unwrap_err())
                })
                return Err(res.unwrap_err())
            log.info({
                "event":"USER.LOGOUT",
                "username":_username
            })
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
    async def update_password(self,dto:DTO.UpdateUserPasswordDTO)->Result[DTO.UpdateUserPasswordResponseDTO,EX.XError]:
        try:
            _username   = dto.username.strip()
            maybe_user  = await self.repository.find_by_username(username=_username)
            if maybe_user.is_none:
                return Err(EX.NotFound(raw_detail="User not found"))
            user           = maybe_user.unwrap()
            new_password   = XoloUtils.pbkdf2(password=dto.password)
            updated_result = await self.repository.update_password(username=user.username,password=new_password)
            if updated_result.is_ok:
                return Ok(DTO.UpdateUserPasswordResponseDTO(ok=updated_result.unwrap()))
            return updated_result

        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))

    async def create_user(self,dto:DTO.CreateUserDTO)->Result[DTO.CreatedUserResponseDTO,EX.XError]:
        try:
            start_time = T.time()
            _username   = dto.username.strip()
            _email      = dto.email.strip()
            _first_name = dto.first_name.strip()
            _last_name  = dto.last_name.strip()
            log.debug({
                "event":"CREATE.USER",
                "username":_username,
                "email":_email,
                "first_name":_first_name,
                "last_name":_last_name,
            })
            maybe_user  = await self.repository.find_by_username(username=_username)
            if maybe_user.is_some:
                e = EX.AlreadyExists(raw_detail="Username already exists", metadata={"entity":"user","id":_username})
                print(e.detail)
                log.error({
                    "error":"USER.ALREADY.EXISTS",
                    "detail":e.detail.msg,
                    "status_code":e.status_code
                })
                return Err(e)
            
            _password = XoloUtils.pbkdf2(password=dto.password)
            result       = await self.repository.create(user=
                DTO.CreateUserDTO(
                    username      = _username,
                    first_name    = _first_name,
                    last_name     = _last_name,
                    email         = _email,
                    profile_photo = "https://www.eldersinsurance.com.au/images/person1.png?width=368&height=278&crop=1",
                    password      = _password,
                )
            )
            if result.is_err:
                return Err(result.unwrap_err())
            
            key = result.unwrap()
            log.info({
                "event":"CREATED.USER",
                "username":_username,
                "email":_email,
                "first_name":_first_name,
                "last_name":_last_name,
                "response_time":T.time() - start_time
            })
            return Ok(DTO.CreatedUserResponseDTO(key=key))
                # raise HTTPException(status_code=503, detail="{} already exists".format(_username))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
    async def check_license_and_scope(self,username:str,scope:str)->bool:
        try:
            scope_exists = (await self.scopes_repository.exists_scope(name=scope)).unwrap_or(False)
            if not scope_exists:
                log.error({
                    "event":" UNAUTHORIZED.SCOPE.NOT.FOUND",
                    "scope":scope
                })
                return Err(EX.Unauthorized(raw_detail="Invalid scope") )

            belongs_to     = (await self.scopes_repository.exists_scope_user(name = scope, username=username)).unwrap_or(False)
            license_result = await self.licenses_service.repository.find_by_username_and_scope(username=username, scope=scope)
            if license_result.is_err:
                e = license_result.unwrap_err()
                log.error({
                    "event":"UNAUTHORIZED.INVALID.LICENSE",
                    "username":username,
                    "scope":scope,
                    "detail":str(e)
                })
                return Err(EX.InvalidLicense(raw_detail=e.detail.raw_error))
            license              = license_result.unwrap()
            license_is_valid_res =  self.licenses_service.lm.verify(user_id=username,app_id=scope, license_key=license)
            license_is_valid     = license_is_valid_res.unwrap_or(False)
            return license_is_valid
            
        except Exception as e:
            return Err(e)
    async def auth(self,dto: DTO.AuthDTO)->Result[DTO.AuthenticatedDTO,EX.XError]:
        try:
            start_time   = T.time()
            dto.username = dto.username.strip()
            
            dto.scope    = dto.scope.strip().upper()
            log.debug({
                "event":"AUTH.ATTEMPT",
                "username":dto.username,
                "scope":dto.scope,
            })

            maybe_user = await self.repository.find_by_username(dto.username)
            if maybe_user.is_none:
                return Err(EX.NotFound(raw_detail="User not found"))
            user       = maybe_user.unwrap()


            
            is_auth    = XoloUtils.check_password_hash(password=dto.password, password_hash=user.hash_password)
            
            scope_exists = (await self.scopes_repository.exists_scope(name=dto.scope)).unwrap_or(False)
            if not scope_exists:
                log.error({
                    "event":" UNAUTHORIZED.SCOPE.NOT.FOUND",
                    "username":dto.username,
                    "scope":dto.scope
                })
                return Err(EX.Unauthorized(raw_detail="Invalid scope") )

            belongs_to = (await self.scopes_repository.exists_scope_user(name = dto.scope, username=dto.username)).unwrap_or(False)

            license_result = await self.licenses_service.repository.find_by_username_and_scope(username=dto.username, scope=dto.scope)
            if license_result.is_err:
                e = license_result.unwrap_err()
                log.error({
                    "event":"UNAUTHORIZED.LICENSE.NOT.FOUND",
                    "username":dto.username,
                    "scope":dto.scope,
                    "detail":str(e)
                })
                return Err(EX.InvalidLicense(raw_detail=str(e)))
            license              = license_result.unwrap()
            license_is_valid_res =  self.licenses_service.lm.verify(user_id=dto.username,app_id=dto.scope, license_key=license)
            license_is_valid     = license_is_valid_res.unwrap_or(False)
            
            if not belongs_to and is_auth:
                log.error({
                    "event":"UNAUTHORIZED.SCOPE",
                    "username":dto.username,
                    "scope":dto.scope
                })
                return Err(EX.UnauthorizedScope(raw_detail="User does not belong to the specified scope"))
            elif not license_is_valid:
                log.error({
                    "event":"UNAUTHORIZED.INVALID.LICENSE",
                    "username":dto.username,
                    "scope":dto.scope,
                })
                return Err(EX.InvalidLicense(raw_detail="License is invalid or expired"))
            elif belongs_to and is_auth and license_is_valid:
                if dto.renew_token:
                    await self.repository.delete_access_token(username=dto.username)
                    
                _access_token = await self.repository.get_access_token(username=dto.username)
                # temp_secret_key = 
                if _access_token.is_ok:
                    token_maybe = _access_token.unwrap()
                    if token_maybe.is_some:
                        (access_token, temp_secret_key) = token_maybe.unwrap()
                        log.info({
                            "event":"AUTHENTICATED.CACHED",
                            "username":dto.username,
                            "response_time":T.time() - start_time
                        })
                        return Ok(
                            DTO.AuthenticatedDTO(
                                username        = dto.username,
                                email           = user.email,
                                first_name      = user.first_name,
                                last_name       = user.last_name,
                                profile_photo   = user.profile_photo,
                                access_token    = access_token,
                                temporal_secret = temp_secret_key,
                                metadata        = {},
                                user_id         = user.key
                            )
                        )
                


                temp_secret_key = uuid4().hex
                iat             = datetime.now(timezone.utc)
                exp_in_seconds  = HF.parse_timespan(dto.expiration)
                exp             = iat + timedelta(seconds=exp_in_seconds)
                access_token = Security.create_access_token(
                    # SECRET_KEY= Security.SECRET_KEY,
                    SECRET_KEY = temp_secret_key,
                    ALGORITHM= Security.ALGORITHM,
                    data={
                        "sub": user.key,
                        "exp":exp.timestamp(),
                        "iss": dto.scope,
                        "iat":iat.timestamp(),
                        "uid2":user.username
                    }
                )
                # access_token    = jwt.encode(payload={
                    # },
                    # key= user.hash_password,
                    # key= temp_secret_key,
                    # algorithm="HS256"
                # )
                res = await self.repository.set_access_token(
                    username        = dto.username,
                    access_token    = access_token,
                    temp_secret_key = temp_secret_key,
                    exp             = dto.expiration
                )
                if res.is_err:
                    log.error({
                        "event":"USER.AUTH.SET.TOKEN.ERROR",
                        "username":dto.username,
                        "detail":str(res.unwrap_err())
                    })
                    return Err(res.unwrap_err())

                log.info({
                    "event":"AUTHENTICATED",
                    "username":dto.username,
                    "response_time":T.time() - start_time
                })
                return Ok(
                    DTO.AuthenticatedDTO(
                        username        = user.username,
                        email           = user.email,
                        first_name      = user.first_name,
                        last_name       = user.last_name,
                        profile_photo   = user.profile_photo,
                        access_token    = access_token,
                        temporal_secret = temp_secret_key,
                        metadata        = {},
                        user_id         = user.key
                    )
                )
            else:
                return Err(EX.Unauthorized(raw_detail="Incorrect username or password"))
            # HTTPException(status_code=401,  detail="Incorrect username or password: UNAUTHORIZED")
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    
    async def disabled_user(self,dto:DTO.EnableOrDisableUserDTO)->Result[bool, EX.XError]:  
        try:
            maybe_user = await self.repository.find_by_username(dto.username.strip())
            if maybe_user.is_none:
                return Err(EX.NotFound(entity="User"))
            user       = maybe_user.unwrap()
            res        = await self.repository.disable_user(user_id=user.key)
            if res.is_err:
                return Err(res.unwrap_err())
            return Ok(res.unwrap())
        except Exception as e:
            return Err(EX.ServerError(raw_detail =str(e)))
    async def enable_user(self,dto:DTO.EnableOrDisableUserDTO)->Result[bool, EX.XError]:  
        try:
            maybe_user = await self.repository.find_by_username(dto.username.strip())
            if maybe_user.is_none:
                return Err(EX.NotFound(entity="User"))
            user       = maybe_user.unwrap()
            res        = await self.repository.enable_user(user_id=user.key)
            if res.is_err:
                return Err(res.unwrap_err())
            return Ok(res.unwrap())
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
    # async 
        
    async def verify(self,dto:DTO.VerifyDTO)->Result[bool, EX.XError]:
        try:
                maybe_user = await self.repository.find_by_username(dto.username.strip())
                if maybe_user.is_none:
                    return Err(EX.NotFound(raw_detail="User not found by username", metadata={"entity":"User","id":dto.username}))
                user                = maybe_user.unwrap()
                # is_auth             = True
                access_token_result = await self.repository.get_access_token(username=dto.username.strip())
                if access_token_result.is_err:
                    return Err(EX.Unauthorized(raw_detail=access_token_result.unwrap_err().detail.raw_error))
                
                access_token_maybe = access_token_result.unwrap()
                if access_token_maybe.is_none:
                    return Err(EX.Unauthorized(raw_detail="No access token found"))
                
                (stored_access_token, stored_secret) = access_token_maybe.unwrap()
                if stored_access_token != dto.access_token:
                    return Err(EX.Unauthorized(raw_detail="Invalid access token"))
                

                claims = jwt.decode(
                    jwt=dto.access_token,
                    key=dto.secret,
                    algorithms=["HS256"]
                )

                ct = datetime.now(timezone.utc)
                current_time = ct.timestamp()
                expiration_time = float(claims.get("exp",0))
                if current_time <= expiration_time:
                    return Ok(True)
                else:
                    return Err(EX.TokenExpired(raw_detail="Token has expired."))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))