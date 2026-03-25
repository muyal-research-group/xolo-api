from motor.motor_asyncio import AsyncIOMotorCollection
from option import Result, Err,Ok
# 
from commonx.dto.xolo import CreateScopeDTO,AssignScopeDTO
import commonx.errors as EX
import commonx.models.xolo as MX

class ScopesRepository(object):
    def __init__(self,
        collection:AsyncIOMotorCollection,
        scope_user_collection:AsyncIOMotorCollection
    ):
        self.collection = collection
        self.scope_user_collection = scope_user_collection

    async def exists_scope_user(self,name:str,username:str)->Result[bool, EX.XError]:
        try:
            doc = await self.scope_user_collection.find_one({
                "name":name.strip().upper(),
                "username": username.strip()
            })
            if doc == None:
                return Ok(False)
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))

    async def exists_scope(self,name:str)->Result[bool, EX.XError]:
        try:
            doc = await self.collection.find_one({
                "name":name.upper(),
            })
            if doc == None:
                return Ok(False)
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    async def find_scope_by_name(self, name:str)->Result[MX.ScopeModel, EX.XError]:
        try:
            doc = await self.collection.find_one({
                "name":name
            })
            if doc == None:
                return Err(EX.NotFound(metadata= {"entity":"Scope"}))
            return Ok(MX.ScopeModel(**doc))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
    async def create(self,dto:CreateScopeDTO)->Result[str, EX.XError]:
        try:
            doc = MX.ScopeModel(
                name= dto.name
            )
            result = await self.collection.insert_one(doc.model_dump())
            return Ok(dto.name)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    async def assign(self,dto:AssignScopeDTO)->Result[str,EX.XError]:
        try:
            doc = MX.ScopeUserModel(
                name=dto.name,
                username = dto.username
            )
            result = await self.scope_user_collection.insert_one(doc.model_dump())
            return Ok(dto.name)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
    async def find_all_scopes(self)->Result[list[MX.ScopeModel], EX.XError]:
        try:
            cursor = self.collection.find({})
            scopes = []
            async for doc in cursor:
                scopes.append(MX.ScopeModel(**doc))
            return Ok(scopes)
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))
        
        