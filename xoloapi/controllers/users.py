from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from fastapi import status, Depends,HTTPException,Header,Response
from fastapi.encoders import jsonable_encoder
from xoloapi.db import get_collection
from typing import Annotated, Union
import xoloapi.services as S
import xoloapi.repositories as R
import xoloapi.dto as DTO
from option import Some,NONE
import os
from xolo.log import Log
from xolo.acl.acl import Acl

router = APIRouter(prefix="/api/v4/users")
XOLO_ACL_KEY = os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2")
log            = Log(
        name   = "users.controller",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)
XOLO_ACL_OUTPUT_PATH      = os.environ.get("XOLO_ACL_OUTPUT_PATH","/mictlanx/xolo")
XOLO_ACL_FILENAME         = os.environ.get("XOLO_ACL_FILENAME","xolo-acl.enc")
XOLO_ACL_DAEMON_HEARTBEAT = os.environ.get("XOLO_ACL_DAEMON_HEARTBEAT","15min")
XOLO_ACL_KEY = os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2")
acl = Acl.load_or_create(
    key = XOLO_ACL_KEY,
    output_path=XOLO_ACL_OUTPUT_PATH,
    filename=XOLO_ACL_FILENAME,
    heartbeat=XOLO_ACL_DAEMON_HEARTBEAT,
)

def get_users_service()->S.UsersService:
    users_collection = get_collection("users")
    
    service = S.UsersService(
        repository= R.UsersRepository(collection=users_collection ),
        scopes_repository= R.ScopesRepository(
            collection=get_collection("scopes"),
            scope_user_collection=get_collection("scopes_users")
        ),
        licenses_service=S.LicensesService(
            users_repository= R.UsersRepository(collection= users_collection ), 
            repository=R.LicensesRepository(
                collection=get_collection("licenses")
            ),
            secret_key=XOLO_ACL_KEY
        ),
    )
    return service

@router.post("",status_code=status.HTTP_201_CREATED)
async def create_user(
    user_dto:DTO.CreateUserDTO,
    users_service:S.UsersService = Depends(get_users_service)
):
    response = await users_service.create_user(dto = user_dto)
    if response.is_ok:
        return response.unwrap()
    error = response.unwrap_err()
    raise HTTPException(
        detail=error.detail,
        status_code= error.status_code
    )

@router.get("/{username}/resources")
async def get_resources_by_username(username:str,
    users_service:S.UsersService = Depends(get_users_service)
):
    x = acl.show().get(username)
    x = dict(list(map(lambda x:(x[0],list(x[1])),x.items())))
    return {
        "resources": x
    }



@router.post("/verify") 
async def verify(
    verify_dto:DTO.VerifyDTO, 
    users_service:S.UsersService = Depends(get_users_service)
):
  response = await users_service.verify(dto = verify_dto)
  if response.is_ok:
      return Response(status_code=204)
  error = response.unwrap_err()
  raise HTTPException(status_code= error.status_code, detail= error.detail)
  
@router.post("/password-recovery")
async def update_password(
    dto:DTO.UpdateUserPasswordDTO,
    secret: Annotated[Union[str,None], Header()]=None,
    users_service:S.UsersService = Depends(get_users_service)
):

    if secret == None or not secret == XOLO_ACL_KEY:
    # os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"):
        log.error({
            "event":"INVALID.SECRET_KEY"
        })
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    response = await users_service.update_password(dto=dto)
    if response.is_ok:
        return response.unwrap()
    error = response.unwrap_err()
    raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.post("/auth")
async def auth(
    auth_dto:DTO.AuthDTO,
    users_service:S.UsersService = Depends(get_users_service)
)->DTO.AuthenticatedDTO:
    response = await users_service.auth(dto = auth_dto)
    if response.is_ok:
        return response.unwrap()
    error = response.unwrap_err()
    raise HTTPException(status_code= error.status_code, detail= error.detail)

@router.get("/acl",status_code=status.HTTP_200_OK)
def acl_show(
    secret:Annotated[Union[str,None], Header()]= None
):
    if secret == None or not secret == XOLO_ACL_KEY:
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    return acl.show()

@router.post("/grants",status_code=status.HTTP_204_NO_CONTENT)
def grants(
    payload:DTO.GrantsDTO,
    secret:Annotated[Union[str,None], Header()]= None,

):

    if secret == None or not secret == XOLO_ACL_KEY:
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    acl.grants(grants=payload.grants)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/grantx",status_code=status.HTTP_204_NO_CONTENT)
def grants_by_admin(
    payload:DTO.GrantsDTO,
):
    x = acl.check(role=payload.role,resource="$XOLO-API", permission="grant")
    
    print(x)
    if not x:
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    acl.grants(grants=payload.grants)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/check",status_code=status.HTTP_200_OK)
def check(payload:DTO.CheckDTO):
    return {
        "result":acl.check(role=payload.role, resource=payload.resource,permission=payload.permission)
    }

@router.post("/revoke",status_code=status.HTTP_204_NO_CONTENT)
def revoke(payload:DTO.CheckDTO, 
           secret:Annotated[Union[str,None], Header()]= None,
           clear:Annotated[Union[int, None], Header()]=0,
           destroy:Annotated[ Union[int,None], Header()] = 0
    ):

    if secret == None or not secret == XOLO_ACL_KEY:
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    
    
    if destroy == 1:
        acl.revoke_all(role=payload.role, resource= NONE)
    elif clear == 1:
        acl.revoke_all(role=payload.role, resource= Some(payload.resource),)
    else:
        acl.revoke(permission=payload.permission, role=payload.role,resource=payload.resource)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/save")
def save(
    secret: Annotated[Union[str,None], Header()]=None
):
    if secret == None or not secret == XOLO_ACL_KEY: 
    # os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"):
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")

    result = acl.save(key=XOLO_ACL_KEY,output_path=XOLO_ACL_OUTPUT_PATH,filename=XOLO_ACL_FILENAME)
    return JSONResponse(content=jsonable_encoder({"ok": result.is_ok }))
