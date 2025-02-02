
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
    
    def update_password(self,dto:DTO.UpdateUserPasswordDTO)->Result[DTO.UpdateUserPasswordResponseDTO,EX.XoloError]:
        try:
            _username   = dto.username.strip()
            maybe_user  = self.repository.find_by_username(username=_username)
            if maybe_user.is_none:
                return Err(EX.UserNotFound())
            user           = maybe_user.unwrap()
            new_password   = XoloUtils.pbkdf2(password=dto.password)
            updated_result = self.repository.update_password(username=user.username,password=new_password)
            if updated_result.is_ok:
                return Ok(DTO.UpdateUserPasswordResponseDTO(ok=updated_result.unwrap()))
            return updated_result

        except Exception as e:
            return Err(EX.ServerError(message=str(e)))

    def create_user(self,dto:DTO.CreateUserDTO)->Result[DTO.CreatedUserResponseDTO,EX.XoloError]:
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
            maybe_user  = self.repository.find_by_username(username=_username)
            if maybe_user.is_some:
                e = EX.UserAlreadyExists()
                log.error({
                    "error":"USER.ALREADY.EXISTS",
                    "detail":e.detail,
                    "status_code":e.status_code
                })
                return Err(e)
            
            _password = XoloUtils.pbkdf2(password=dto.password)
            key       = self.repository.create(user=
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
    def auth(self,dto: DTO.AuthDTO)->Result[DTO.AuthenticatedDTO,EX.XoloError]:
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
            maybe_user = self.repository.find_by_username(dto.username)
            if maybe_user.is_none:
                return Err(EX.UserNotFound())
            user       = maybe_user.unwrap()
            is_auth    = XoloUtils.check_password_hash(password=dto.password, password_hash=user.hash_password)
            belongs_to = self.scopes_repository.exists_scope_user(name = dto.scope, username=dto.username).unwrap_or(False)

            license_result = self.licenses_service.repository.find_by_username_and_scope(username=dto.username, scope=dto.scope)
            if license_result.is_err:
                e = license_result.unwrap_err()
                log.error({
                    "event":"UNAUTHORIZED.INVALID.LICENSE",
                    "username":dto.username,
                    "scope":dto.scope,
                    "detail":str(e)
                })
                return Err(EX.InvalidLicense())
            license              = license_result.unwrap()
            license_is_valid_res = self.licenses_service.lm.verify(user_id=dto.username,app_id=dto.scope, license_key=license)
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
                    "iat":iat
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
    