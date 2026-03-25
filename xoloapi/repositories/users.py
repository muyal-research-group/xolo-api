# xoloapi/respositories/users.py
from typing import Tuple
# 
from motor.motor_asyncio import AsyncIOMotorCollection
from redis.asyncio import Redis
import humanfriendly as HF
from option import Result,Ok,Err
from uuid import uuid4
import json as J
from option import Option,Some,NONE
from bson.json_util import dumps
# 
from commonx.models.xolo import User
from commonx.dto.xolo import CreateUserDTO
import commonx.errors as EX


class UsersRepository(object):
    def __init__(self,
        collection:AsyncIOMotorCollection,
        cache_redis:Redis=None
    ):
        self.collection = collection
        self.cache_redis = cache_redis

    async def enable_user(self, username:str)->Result[bool, EX.XError]:
        try:
            doc = await self.collection.update_one(filter={"username":username},update={"$set":{"disabled":True}} )
            if doc.modified_count >0:
                return Ok(True)
            else: 
                return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))

    async def disable_user(self, username:str)->Result[bool, EX.XError]:
        try:
            doc = await self.collection.update_one(filter={"username":username},update={"$set":{"disabled":False}} )
            if doc.modified_count >0:
                return Ok(True)
            else: 
                return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
    async def set_access_token(self, username:str, access_token:str,temp_secret_key:str,exp:str="15min")->Result[bool, EX.XError]:
        try:
            if self.cache_redis is None:
                return Err(EX.ServerError(raw_detail="Cache is not available"))
            await self.cache_redis.set(f"user:{username}:access_token", access_token, ex=int(HF.parse_timespan(exp)))
            await self.cache_redis.set(f"user:{username}:temp_secret_key", temp_secret_key, ex=int(HF.parse_timespan(exp)))
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
    async def get_access_token(self, username:str)->Result[Option[Tuple[str,str]], EX.XError]:
        try:
            if self.cache_redis is None:
                return Err(EX.ServerError(raw_detail="Cache is not available"))
            token           = await self.cache_redis.get(f"user:{username}:access_token")
            temp_secret_key = await self.cache_redis.get(f"user:{username}:temp_secret_key")

            if token is None or temp_secret_key is None:
                return Err(EX.Unauthorized(raw_detail="Access token has expired"))
            else:
                return Ok(Some((token, temp_secret_key)))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    
    async def delete_access_token(self, username:str)->Result[bool, EX.XError]:
        try:
            if self.cache_redis is None:
                return Err(EX.ServerError(raw_detail="Cache is not available"))
            await self.cache_redis.delete(f"user:{username}:access_token")
            await self.cache_redis.delete(f"user:{username}:temp_secret_key")
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))

    async def update_password(self, username:str, password:str)->Result[bool, EX.XError]:
        try:
            doc = await self.collection.update_one(filter={"username":username},update={"$set":{"hash_password":password}} )
            if doc.modified_count >0:
                return Ok(True)
            else: 
                return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    

    async def create(self,user:CreateUserDTO)->Result[str, EX.XError]:
        try:
            _key =  uuid4().hex
            doc = User(
                profile_photo = user.profile_photo,
                key           = _key, 
                first_name    = user.first_name,
                last_name     = user.last_name,
                email         = user.email,
                hash_password = user.password,
                username      = user.username,
                # role= user.role
            )
            result = await self.collection.insert_one(doc.model_dump())
            return Ok(_key)
        except Exception as e:
            return Err(EX.UnknownError(raw_detail=str(e)))
    
    async def find_by_id(self,user_id:str)->Option[User]:
        x=  await self.collection.find_one(filter={
            "key":user_id
        })
        if x == None:
            return NONE
        else:
            return Some(User(**x))
        
    async def find_by_username(self,username:str)->Option[User]:
        x=  await self.collection.find_one(filter={
            "username":username
        })
        if x == None:
            return NONE
        else:
            return Some(User(**x))
