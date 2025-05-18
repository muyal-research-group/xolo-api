# xoloapi/respositories/users.py
from motor.motor_asyncio import AsyncIOMotorCollection
import xoloapi.errors as EX
from option import Result,Ok,Err
from uuid import uuid4
from xoloapi.dto.user import CreateUserDTO
import json as J
from option import Option,Some,NONE
from bson.json_util import dumps
from xoloapi.models import User


class UsersRepository(object):
    def __init__(self,collection:AsyncIOMotorCollection):
        self.collection = collection
    async def update_password(self, username:str, password:str)->Result[bool, EX.XoloError]:
        try:
            doc = await self.collection.update_one(filter={"username":username},update={"$set":{"hash_password":password}} )
            if doc.modified_count >0:
                return Ok(True)
            else: 
                return Err(EX.UserNotFound())
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
    

    async def create(self,user:CreateUserDTO)->str:
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
        result = await self.collection.insert_one(doc.model_dump())
        return _key
    async def find_by_username(self,username:str)->Option[User]:
        x=  await self.collection.find_one(filter={
            "username":username
        })
        if x == None:
            return NONE
        else:
            return Some(User(**x))
