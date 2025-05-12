# from pymongo.collection import Collection
from motor.motor_asyncio import AsyncIOMotorCollection
import xoloapi.errors as EX
import option as OP
import xoloapi.models as M
import xoloapi.dto as DTO

class LicensesRepository(object):
    
    def __init__(self, collection:AsyncIOMotorCollection):
        self.collection = collection

    async def create(self, username:str, license:str, scope:str,expires_at:str)->OP.Result[bool, EX.XoloError]:
        try:
            model = M.LicenseAssignedModel(
                username=username,
                license=license,
                scope=scope,
                expires_at = expires_at
            )
            result = await self.collection.insert_one(document=model.model_dump())
            return OP.Ok(True)
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))
    
    async def find_by_username_and_scope(self,username:str, scope:str)->OP.Result[str, EX.XoloError]:
        try:
            doc = await self.collection.find_one({"username":username, "scope":scope.strip().upper()})
            if doc == None:
                return OP.Err(EX.NotFound(entity="License"))
            return OP.Ok(doc.get("license"))
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))
        
    async def delete_by_username_scope(self,username:str, scope:str)->OP.Result[bool, EX.XoloError]:
        try:
            result = await self.collection.delete_one({"username":username, "scope":scope.strip().upper()})
            if result.deleted_count>0:
                return OP.Ok(True)
            return OP.Err(EX.NotFound(entity="License"))
        except Exception as e:
            return OP.Err(EX.ServerError(message=str(e)))

            