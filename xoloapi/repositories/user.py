from pymongo.collection import Collection
# from pymongo.results import DeleteResult
from pydantic import BaseModel
from uuid import uuid4
# from option import Option, NONE, Some
# from typing import Dict,Union,List
from xoloapi.dto.user import UserDTO
# from src.interfaces.dao.user import User
import json as J
from option import Option,Some,NONE
from bson.json_util import dumps

# class CatalogItem(BaseModel):
#     name:str
#     display_name:str
#     code:str
#     description:str
#     metadata:Dict[str,str]

class User(BaseModel):
    profile_photo:str
    key:str
    first_name:str
    last_name:str
    username:str
    email:str
    hash_password:str
    role:str

class UsersRepository(object):
    def __init__(self,collection:Collection):
        self.collection = collection
    def create(self,user:UserDTO)->str:
        _key =  uuid4().hex
        doc = User(
            profile_photo = user.profile_photo,
            key           = _key, 
            first_name    = user.first_name,
            last_name     = user.last_name,
            email         = user.email,
            hash_password = user.password,
            username      = user.username,
            role= user.role
        )
        self.collection.insert_one(doc.model_dump())
        return _key
    def find_by_username(self,username:str)->Option[User]:
        x=  self.collection.find_one(filter={
            "username":username
        })
        if x == None:
            return NONE
        else:
            print(type(x))
            return Some(User(**x))
