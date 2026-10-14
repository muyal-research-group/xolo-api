import json as J
import os
from xolo.client.client import XoloClient
from typing import List
from xolo.utils import Utils
from xolo.log import Log
import time as T

log            = Log(
        name   = "xolo-test",
        console_handler_filter=lambda x: True,
        interval=24,
        when="h",
        path=os.environ.get("LOG_PATH","/log")
)


xolo_client = XoloClient(
    api_url = os.environ.get("XOLO_API_URL","http://localhost:10000/api/v4"),
)

SECRET = os.environ.get("SECRET", "ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2")

def main():
    json_path = "data/xolo_prod_test.json"
    with open(json_path,"rb") as f:
        data = J.load(f)
        start_time = T.time()
        for user in data:
            user_start_time = T.time()
            username = user.get("username")
            scopes:List[str] = user.get("scopes",[])
            expires_in = user.get("expires_in","1h")
            # print(username,scope,expires_in)
            password = user.get("password",Utils.generate_password(length=12) )
            create_start_time = T.time()
            create_result = xolo_client.create_user(
                username=username,
                first_name=user.get("first_name"),
                email=user.get("email"),
                last_name=user.get("last_name"),
                password= password,
                profile_photo="",
                role=username,
            )
            log.info({
                "event":"CREATED.USER",
                "username":username,
                "password":password,
                "ok":create_result.is_ok,
                "response_time":T.time()-create_start_time
            })
            # print("CREATE_RESULT", create_result)
            if create_result.is_ok:
                assign_scope_start_time = T.time()
                for scope in scopes:
                    assign_scope_result = xolo_client.assign_scope(username=username, scope=scope, secret=SECRET)
                    log.info({
                        "event":"ASSIGNED.SCOPE",
                        "username":username,
                        "scope":scope,
                        "ok":assign_scope_result.is_ok,
                        "response_time": T.time()- assign_scope_start_time
                    })
                    if assign_scope_result.is_ok:
                        create_license_start_time = T.time()
                        create_license_result = xolo_client.create_license(username=username, scope=scope, secret=SECRET, expires_in=expires_in)
                        log.info({
                            "event":"CREATED.LICENSE",
                            "username":username,
                            "scope":scope,
                            "ok":create_license_result.is_ok,
                            "response_time": T.time()- create_license_start_time
                        })
            log.info({
                "event":"USER.CREATED",
                "username":username,
                "response_time":T.time()-user_start_time
            })
        log.info({
            "event":"BULK.USER.CREATION",
            "users":len(data),
            "response_time":T.time()-start_time
        })
            # user["password"] = password
            
        # print(data)

if __name__ =="__main__":
    main()