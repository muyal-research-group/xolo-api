# xoloapi/controllers/users.py
import time as T
from fastapi.routing import APIRouter
from fastapi import status, Depends,HTTPException,Header,Response
from xoloapi.db import get_collection
from typing import Annotated, Union
import xoloapi.services as S
import xoloapi.repositories as R
from xolo.log import Log
import xoloapi.config as Cfg
import xoloapi.middleware as MX
# 
import commonx.dto.xolo as DTO
import commonx.errors as EX

router = APIRouter(prefix="/users")
# XOLO_ACL_KEY = CX.XOLO_ACL_KEY
log            = Log(
        name                   = "users.controller",
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)



def get_cache_redis():
    from xoloapi.db.cache import get_redis_client
    x= get_redis_client()
    if x is None:
        raise HTTPException(status_code=500, detail="Cache is not available")
    return x

def get_users_service(cache= Depends(get_cache_redis))->S.UsersService:
    users_collection = get_collection("users")
    
    service = S.UsersService(
        repository= R.UsersRepository(collection=users_collection, cache_redis=cache),
        scopes_repository= R.ScopesRepository(
            collection=get_collection("scopes"),
            scope_user_collection=get_collection("scopes_users")
        ),
        licenses_service=S.LicensesService(
            users_repository= R.UsersRepository(collection= users_collection ), 
            repository=R.LicensesRepository(
                collection=get_collection("licenses")
            ),
            secret_key=Cfg.XOLO_ACL_KEY
        ),
    )
    return service

@router.post("",status_code=status.HTTP_201_CREATED)
async def create_user(
    user_dto:DTO.CreateUserDTO,
    users_service:S.UsersService = Depends(get_users_service)
):
    t1 = T.time()
    response = await users_service.create_user(dto = user_dto)
    if response.is_ok:
        log.info(
            {
                "event":"USER_CREATED",
                "username": user_dto.username,
                "response_time": T.time() - t1
            }
        )
        return response.unwrap()
    error = response.unwrap_err()
    log.error({
        "code": error.detail.code,
        "detail":error.detail.msg,
        "username": user_dto.username,
        "response_time": T.time() - t1
    })
    raise error.to_http_exception()



@router.post("/verify") 
async def verify(
    verify_dto:DTO.VerifyDTO, 
    users_service:S.UsersService = Depends(get_users_service)
):
  response = await users_service.verify(dto = verify_dto)
  if response.is_ok:
      log.info({
            "event":"USER.VERIFY.SUCCESS",
            "username": verify_dto.username
      })

      return Response(status_code=204)
  error = response.unwrap_err()
  log.error({
            "code": error.detail.code,
            "username": verify_dto.username,
            "reason": error.detail.msg,
            "error":error.detail.raw_error
    })
  raise error.to_http_exception()
#   raise HTTPException(status_code= error.status_code, detail= error.detail)
  
@router.post("/password-recovery")
async def update_password(
    dto:DTO.UpdateUserPasswordDTO,
    secret: Annotated[Union[str,None], Header()]=None,
    users_service:S.UsersService = Depends(get_users_service)
):

    t1 = T.time()
    if secret == None or not secret == Cfg.XOLO_ACL_KEY:
        log.error({
            "event":"INVALID.SECRET_KEY",
            "response_time": T.time() - t1
        })
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await users_service.update_password(dto=dto)
    
    if response.is_ok:
        log.info({
            "event":"USER.PASSWORD_UPDATE", 
            "username": dto.username,
            "response_time": T.time() - t1
        })  
        return response.unwrap()
    error = response.unwrap_err()
    log.error({
        "code": error.detail.code,
        "username": dto.username,
        "reason": error.detail.detail,
        "response_time": T.time() - t1
    })
    raise error.to_http_exception()
    # raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.post("/logout",status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    dto:DTO.LogoutDTO,
    users_service:S.UsersService = Depends(get_users_service)
):
    t1 = T.time()
    response = await users_service.logout(dto = dto)
    if response.is_ok:
        log.info({
            "event":"USER.LOGOUT.SUCCESS",
            "username": dto.username,
            "response_time": T.time() - t1
        })  
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    
    error = response.unwrap_err()
    log.error({
        "code":error.detail.code,
        "username": dto.username,
        "reason": error.detail.detail,
        "response_time": T.time() - t1
    })
    raise error.to_http_exception()
    # raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.post("/auth")
async def auth(
    auth_dto:DTO.AuthDTO,
    users_service:S.UsersService = Depends(get_users_service)
)->DTO.AuthenticatedDTO:
    
    t1       = T.time()
    response = await users_service.auth(dto = auth_dto)
    if response.is_ok:
        log.info({
            "event":"USER.AUTH.SUCCESS",
            "username": auth_dto.username,
            "response_time": T.time() -t1
        })  
        return response.unwrap()
    
    error = response.unwrap_err()
    log.error({
        "code":error.detail.code,
        "code_int":error.detail.code_int,
        "reason": error.detail.msg,
        "username": auth_dto.username,
    })
    raise error.to_http_exception()
# HTTPException(status_code= error.status_code, detail= error.detail)


@router.get("")
async def me(
    current_user: Annotated[DTO.UserDTO, Depends(MX.get_current_user)]
):
    return current_user

@router.post("/{username}/enable",status_code=status.HTTP_204_NO_CONTENT)
async def enable_user(
    dto:DTO.EnableOrDisableUserDTO,
    users_service:S.UsersService = Depends(get_users_service),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    if me.username != dto.username:
        raise EX.AccessDenied(raw_detail="You can only enable your own user account.").to_http_exception()

    username = me.username
    response = await users_service.enable_user(dto=dto)
    if response.is_ok:
        log.info({
            "event":"USER.ENABLED",
            "username": username,
            "response_time": T.time() - t1
        })  
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    
    error = response.unwrap_err()
    log.error({
        "code":error.detail.code,
        "username": username,
        "reason": error.detail.detail,
        "response_time": T.time() - t1
    })
    raise error.to_http_exception()
    # raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.post("/{username}/disable",status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    dto:DTO.EnableOrDisableUserDTO,
    users_service:S.UsersService = Depends(get_users_service),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    if me.username != dto.username:
        raise EX.AccessDenied(raw_detail="You can only disable your own user account.").to_http_exception()

    username = me.username
    response = await users_service.disable_user(dto=dto)
    if response.is_ok:
        log.info({
            "event":"USER.DISABLED",
            "username": username,
            "response_time": T.time() - t1
        })  
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    
    error = response.unwrap_err()
    log.error({
        "code":error.detail.code,
        "code_int":error.detail.code_int,
        "username": username,
        "reason": error.detail,
        "response_time": T.time() - t1
    })
    raise error.to_http_exception()
    # raise HTTPException(status_code= error.status_code, detail= error.detail)