from pymongo.collection import Collection
# from pymongo.results import DeleteResult
from pydantic import BaseModel
from uuid import uuid4
# from option import Option, NONE, Some
# from typing import Dict,Union,List
from interfaces.dto.user import UserDTO
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

class UsersDAO(object):
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

#     def find_all(self,skip:int=0, limit:int = 10)->List[CatalogDTO]:
#         cursor      = self.collection.find({}).skip(skip=skip).limit(limit=limit)
#         documents = []
#         for document in cursor:
#             del document["_id"]
#             documents.append(CatalogDTO(
#                 key=document["key"],
#                 name= document["name"],
#                 display_name= document["display_name"],
#                 items= list( map(lambda x: CatalogItemDTO(**x), document["items"]) )
#             ))

#         cursor.close()
#         return documents

#     def find_by_key(self,key:str)->Option[CatalogDTO]:
#         res = self.collection.find_one({"key":key})
#         if res:
#             del res["_id"]
#             return Some(CatalogDTO(**res))
#         else:
#             return NONE

#     def delete(self,key:str)->DeleteResult:
#         return self.collection.delete_one({"key": key})
