import os
import pandas as pd
import json as J
from mictlanx.v4.xolo.api.index import XoloAPI
from option import NONE,Some
from typing import List
from nanoid import generate as nanoid
import string as S
from dotenv import load_dotenv
load_dotenv()

_port = int(os.environ.get("XOLO_PORT","10001"))
xolo_api = XoloAPI(
    port =  NONE if _port == -1 else Some(_port),
    protocol=os.environ.get("XOLO_PROTOCOL","http"),
    hostname= os.environ.get("XOLO_HOSTNAME","localhost"),
)

def get_firstname_and_lastname(x:List[str]):
    if len(x) == 2:
        return x[0],x[1]
    if len(x) ==4:
        return "{} {}".format(x[0], x[1]), "{} {}".format(x[2],x[3])


users = []
with open("./imss_perms_050324.json",'r') as f:
    data = J.loads(f.read())
    for x in data:
        username = x["username"]
        name  =  x["name"]
        firstname, lastname = get_firstname_and_lastname(name.split(" "))
        email = "{}@imss.com".format(username)
        password=  nanoid(alphabet=S.ascii_lowercase+S.digits,size=64)
        result = xolo_api.create_user(
            username= username,
            first_name= firstname,
            last_name=lastname,
            email= email,
            password=password
        )
        print(result)
        user = [username,firstname,lastname,email,password]
        print(*user,result.is_ok)
        users.append(user)
df = pd.DataFrame(users)
df.to_csv("./users_prod.csv",index=False, header=["USERNAME","FIRSTNAME","LASTNAME","EMAIL","PASSWORD"])
        # if result.is_ok:
            # print("CREATE_USER", username, firstname,lastname )
