from typing import Dict,Union,List
from uuid import uuid4
from pydantic import BaseModel
    
class UserDTO(BaseModel):
    username:str
    first_name:str
    last_name:str
    email:str
    password:str
    profile_photo:str=""
    role:str="user"


class AuthDTO(BaseModel):
    username:str
    password:str
    
class VerifyDTO(BaseModel):
    access_token:str
    username:str
    secret:str
    
class AuthenticatedDTO(BaseModel):
    username:str
    first_name:str
    last_name:str
    email:str
    profile_photo:str
    access_token:str
    metadata:Dict[str,str]
    temporal_secret:str
    role:str
    # key          =  uuid4().hex
    # first_name   =
    # last_name    = last_name
    # email        = email
    # hashed_password = hashed_password 
    # profile_photo = profile_photo
        # self.name         = name
        # self.display_name = display_name
        # self.items        = items