import os
import time as T
from fastapi import FastAPI,Response,HTTPException,status,Header
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from pymongo import MongoClient
from xoloapi.repositories.user import UsersRepository
from xoloapi.dto.user import UserDTO,AuthDTO,AuthenticatedDTO,VerifyDTO
from xoloapi.dto.acl import GrantsDTO,CheckDTO
from uuid import uuid4
import jwt
from datetime import datetime, timedelta
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from xolo.utils.utils import Utils as XoloUtils
from xolo.acl.acl import Acl
from xolo.log import Log
from option import Some,NONE
from typing import Union
from typing_extensions import Annotated

log            = Log(
        name   = "xolo-api",
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





app = FastAPI(
    root_path=os.environ.get("OPENAPI_PREFIX","/xoloapi"),
    title= os.environ.get("OPENAPI_TITLE","Xolo: Identity & Accesss Management")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def generate_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Xolo - API",
        version="0.0.1",
        summary="This API enable the manipulation of observatories and catalogs",
        description="",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": os.environ.get("OPENAPI_LOGO","")
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema
app.openapi = generate_openapi
# .openapi()

ip_addr                  = os.environ.get("MONGO_IP_ADDR","localhost")
port                     = os.environ.get("MONGO_PORT",27017)
client                   = MongoClient(os.environ.get("MONGO_URI","mongodb://{}:{}/".format(ip_addr, port)))
MONGO_DATABASE_NAME      = os.environ.get("MONGO_DATABASE_NAME","mictlanx")
db                       = client[MONGO_DATABASE_NAME]
users_dao              = UsersRepository(collection=db["users"])




@app.post("/api/v4/users/grants",status_code=status.HTTP_204_NO_CONTENT)
def grants(
    payload:GrantsDTO,
    secret:Annotated[Union[str,None], Header()]= None,

):

    if secret == None or not secret == os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"):
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    acl.grants(grants=payload.grants)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v4/users/check",status_code=status.HTTP_200_OK)
def check(payload:CheckDTO):
    return {
        "result":acl.check(role=payload.role, resource=payload.resource,permission=payload.permission)
    }

@app.post("/api/v4/users/revoke",status_code=status.HTTP_204_NO_CONTENT)
def revoke(payload:CheckDTO, 
           secret:Annotated[Union[str,None], Header()]= None,
           clear:Annotated[Union[int, None], Header()]=0,
           destroy:Annotated[ Union[int,None], Header()] = 0
    ):

    if secret == None or not secret == os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"):
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    
    
    if destroy == 1:
        acl.revoke_all(role=payload.role, resource= NONE)
    elif clear == 1:
        acl.revoke_all(role=payload.role, resource= Some(payload.resource),)
    else:
        acl.revoke(permission=payload.permission, role=payload.role,resource=payload.resource)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/api/v4/users/acl",status_code=status.HTTP_200_OK)
def acl_show(
    secret:Annotated[Union[str,None], Header()]= None
):
    if secret == None or not secret == os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"):
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")
    return acl.show()


@app.post("/api/v4/users",status_code=status.HTTP_201_CREATED)
def create_user(user_dto:UserDTO):
    _username = user_dto.username.strip()
    _email    = user_dto.email.strip()
    _first_name = user_dto.first_name.strip()
    _last_name  = user_dto.last_name.strip()
    _role       = user_dto.role.strip()
    
    maybe_user = users_dao.find_by_username(username=_username)
    if maybe_user.is_some:
        raise HTTPException(status_code=503, detail="{} already exists".format(_username))
    _password = XoloUtils.pbkdf2(password=user_dto.password)
    key= users_dao.create(user=UserDTO(
        username=_username,
        first_name=_first_name,
        last_name=_last_name,
        email=_email,
        profile_photo="https://www.eldersinsurance.com.au/images/person1.png?width=368&height=278&crop=1",
        password= _password,
        role=_role
    ))
    return {"key": key}
    # return "CREATE_USER"


@app.post("/api/v4/users/verify") 
def verify(verify_dto:VerifyDTO):
    try:
        maybe_user = users_dao.find_by_username(verify_dto.username.strip())
        if maybe_user.is_none:
            raise HTTPException(status_code=403, detail="User not found")

        user    = maybe_user.unwrap()
        # is_auth = XoloUtils.check_password_hash(password=verify_dto.password, password_hash=user.hash_password)
        # Check the secret in redis (now it's not important)
        is_auth=True
        # print("IS_AUTH",is_auth)
        if is_auth:
            claims = jwt.decode(
                jwt=verify_dto.access_token,
                key=verify_dto.secret,
                algorithms=["HS256"]
            )

            current_time = datetime.utcnow().timestamp()
            expiration_time = float(claims.get("exp",0))
            if current_time <= expiration_time:
                return Response(status_code=204)
            else:
                raise HTTPException(status_code=503, detail="Token has expired: TOKEN_EXPIRED")
        else:
            raise HTTPException(status_code=401, detail="Unauthorized")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v4/save")
def save(
    secret: Annotated[Union[str,None], Header()]=None
):
    if secret == None or not secret == os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"):
        raise HTTPException(status_code=403, detail="You are not authorized, please stop trying or you will be reported and blacklisted.")

    result = acl.save(key=XOLO_ACL_KEY,output_path=XOLO_ACL_OUTPUT_PATH,filename=XOLO_ACL_FILENAME)
    return JSONResponse(content=jsonable_encoder({"ok": result.is_ok }))
@app.post("/api/v4/users/auth")
def auth(auth_dto:AuthDTO)->AuthenticatedDTO:
    _username = auth_dto.username.strip()
    log.debug({
        "event":"AUTH.STARTED",
        "username":_username,
    })
    maybe_user = users_dao.find_by_username(_username)
    if maybe_user.is_none:
        raise HTTPException(status_code=403, detail="User not found")
    user = maybe_user.unwrap()
    is_auth = XoloUtils.check_password_hash(password=auth_dto.password, password_hash=user.hash_password)
    temp_secret_key = uuid4().hex
    if is_auth:
        iat = datetime.utcnow()
        exp = iat + timedelta(minutes=60) 
        access_token = jwt.encode(payload={
            "uid": user.key,
            "exp":exp.timestamp(),
            "iss": "MictlanX",
            "iat":iat
            },
            # key= user.hash_password,
            key= temp_secret_key,
            algorithm="HS256"
        )
        # token = 
        return AuthenticatedDTO(
            username      = user.username,
            email         = user.email,
            first_name    = user.first_name,
            last_name     = user.last_name,
            profile_photo = user.profile_photo,
            access_token  = access_token,
            temporal_secret = temp_secret_key,
            role=user.role,
            metadata      = {}
        )
    else:
        raise HTTPException(status_code=401,  detail="Incorrect username or password: UNAUTHORIZED")
    # users_dao.create(user=user_dto)

    # return "CREATE_USER"

if __name__ =="__main__":
    try:
        uvicorn.run(
            host=os.environ.get("IP_ADDR","0.0.0.0"), 
            port=int(os.environ.get("PORT","10001")),
            reload=bool(int(os.environ.get("REALOAD","1"))),
            app="server:app"
        )
    except Exception as e:
        log.error({
            "msg":str(e)
        })
    finally:
        start_time = T.time()
        result = acl.save(key=XOLO_ACL_KEY,output_path=XOLO_ACL_OUTPUT_PATH,filename=XOLO_ACL_FILENAME)
        if result.is_ok:
            log.debug({
                "event":"ACL.SAVE.COMPLETED",
                "service_time": T.time() - start_time
            })
        else:
            error = result.unwrap_err()
            log.error({
                "msg":str(error)
            })
        