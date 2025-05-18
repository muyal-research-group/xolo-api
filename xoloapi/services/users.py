
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
import os

log            = Log(
        name   = "xolo.usersservice",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
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
    
    async def update_password(self,dto:DTO.UpdateUserPasswordDTO)->Result[DTO.UpdateUserPasswordResponseDTO,EX.XoloError]:
        try:
            _username   = dto.username.strip()
            maybe_user  = await self.repository.find_by_username(username=_username)
            if maybe_user.is_none:
                return Err(EX.UserNotFound())
            user           = maybe_user.unwrap()
            new_password   = XoloUtils.pbkdf2(password=dto.password)
            updated_result = await self.repository.update_password(username=user.username,password=new_password)
            if updated_result.is_ok:
                return Ok(DTO.UpdateUserPasswordResponseDTO(ok=updated_result.unwrap()))
            return updated_result

        except Exception as e:
            return Err(EX.ServerError(message=str(e)))

    async def create_user(self,dto:DTO.CreateUserDTO)->Result[DTO.CreatedUserResponseDTO,EX.XoloError]:
        try:
            start_time = T.time()
            _username   = dto.username.strip()
            _email      = dto.email.strip()
            _first_name = dto.first_name.strip()
            _last_name  = dto.last_name.strip()
            _role       = dto.role.strip()
            log.debug({
                "event":"CREATE.USER",
                "username":_username,
                "email":_email,
                "first_name":_first_name,
                "last_name":_last_name,
                "role":_role
            })
            maybe_user  = await self.repository.find_by_username(username=_username)
            if maybe_user.is_some:
                e = EX.UserAlreadyExists()
                log.error({
                    "error":"USER.ALREADY.EXISTS",
                    "detail":e.detail,
                    "status_code":e.status_code
                })
                return Err(e)
            
            _password = XoloUtils.pbkdf2(password=dto.password)
            key       = await self.repository.create(user=
                DTO.CreateUserDTO(
                    username      = _username,
                    first_name    = _first_name,
                    last_name     = _last_name,
                    email         = _email,
                    profile_photo = "https://www.eldersinsurance.com.au/images/person1.png?width=368&height=278&crop=1",
                    password      = _password,
                    role          = _role
                )
            )
            log.info({
                "event":"CREATED.USER",
                "username":_username,
                "email":_email,
                "first_name":_first_name,
                "last_name":_last_name,
                "role":_role,
                "response_time":T.time() - start_time
            })
            return Ok(DTO.CreatedUserResponseDTO(key=key))
                # raise HTTPException(status_code=503, detail="{} already exists".format(_username))
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
    async def check_license_and_scope(self,username:str,scope:str)->bool:
        try:
            scope_exists = (await self.scopes_repository.exists_scope(name=scope)).unwrap_or(False)
            if not scope_exists:
                log.error({
                    "event":" UNAUTHORIZED.SCOPE.NOT.FOUND",
                    "scope":scope
                })
                return Err(EX.Unauthorized(message="Invalid scope") )

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
                return Err(EX.InvalidLicense())
            license              = license_result.unwrap()
            license_is_valid_res =  self.licenses_service.lm.verify(user_id=username,app_id=scope, license_key=license)
            license_is_valid     = license_is_valid_res.unwrap_or(False)
            return license_is_valid
            
        except Exception as e:
            return Err(e)
    async def auth(self,dto: DTO.AuthDTO)->Result[DTO.AuthenticatedDTO,EX.XoloError]:
        try:
            start_time = T.time()
            # _username = dto.username.strip()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            log.debug({
                "event":"AUTH.ATTEMPT",
                "username":dto.username,
                "scope":dto.scope,
            })
            maybe_user = await self.repository.find_by_username(dto.username)
            if maybe_user.is_none:
                return Err(EX.UserNotFound())
            user       = maybe_user.unwrap()
            is_auth    = XoloUtils.check_password_hash(password=dto.password, password_hash=user.hash_password)
            scope_exists = (await self.scopes_repository.exists_scope(name=dto.scope)).unwrap_or(False)
            if not scope_exists:
                log.error({
                    "event":" UNAUTHORIZED.SCOPE.NOT.FOUND",
                    "username":dto.username,
                    "scope":dto.scope
                })
                return Err(EX.Unauthorized(message="Invalid scope") )

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
                return Err(EX.InvalidLicense())
            license              = license_result.unwrap()
            license_is_valid_res =  self.licenses_service.lm.verify(user_id=dto.username,app_id=dto.scope, license_key=license)
            license_is_valid     = license_is_valid_res.unwrap_or(False)
            
            if not belongs_to and is_auth:
                log.error({
                    "event":"UNAUTHORIZED.SCOPE",
                    "username":dto.username,
                    "scope":dto.scope
                })
                return Err(EX.UnauthorizedScope())
            elif not license_is_valid:
                log.error({
                    "event":"UNAUTHORIZED.INVALID.LICENSE",
                    "username":dto.username,
                    "scope":dto.scope,
                })
                return Err(EX.InvalidLicense())
            elif belongs_to and is_auth and license_is_valid:
                temp_secret_key = uuid4().hex
                iat = datetime.now(timezone.utc)
                exp = iat + timedelta(minutes=60) 
                access_token = jwt.encode(payload={
                        "uid": user.key,
                        "exp":exp.timestamp(),
                        "iss": dto.scope,
                        "iat":iat,
                        "uid2":user.username
                    },
                    # key= user.hash_password,
                    key= temp_secret_key,
                    algorithm="HS256"
                )
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
                        role            = user.role,
                        metadata        = {}
                    )
                )
            else:
                return Err(EX.Unauthorized())
            # HTTPException(status_code=401,  detail="Incorrect username or password: UNAUTHORIZED")
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
    

    async def verify(self,dto:DTO.VerifyDTO)->Result[bool, EX.XoloError]:
        try:
                maybe_user = await self.repository.find_by_username(dto.username.strip())
                if maybe_user.is_none:
                    return Err(EX.NotFound("User"))
                user    = maybe_user.unwrap()
                is_auth=True
                if is_auth:
                    claims = jwt.decode(
                        jwt=dto.access_token,
                        key=dto.secret,
                        algorithms=["HS256"]
                    )

                    ct = datetime.now(timezone.utc)
                    current_time = ct.timestamp()
                    expiration_time = float(claims.get("exp",0))
                    if current_time <= expiration_time:
                        return Ok(bool)
                    else:
                        return Err(EX.TokenExpired())
                        # raise HTTPException(status_code=503, detail="Token has expired: TOKEN_EXPIRED")
                else:
                    return Err(EX.Unauthorized())
                    # raise HTTPException(status_code=401, detail="Unauthorized")
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
                # raise HTTPException(status_code=500, detail=str(e))