from pymongo.collection import Collection
from xoloapi.dto.user import CreateScopeDTO,AssignScopeDTO
from pydantic import BaseModel
from option import Result, Err,Ok
import xoloapi.errors as EX

class ScopeModel(BaseModel):
    name: str

class ScopeUserModel(BaseModel):
    name:str
    username:str

class ScopesRepository(object):
    def __init__(self,
        collection:Collection,
        scope_user_collection:Collection
    ):
        self.collection = collection
        self.scope_user_collection = scope_user_collection

    def exists_scope_user(self,name:str,username:str)->Result[bool, EX.XoloError]:
        try:
            doc = self.scope_user_collection.find_one({
                "name":name.strip().upper(),
                "username": username.strip()
            })
            if doc == None:
                return Ok(False)
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))

    def exists_scope(self,name:str)->Result[bool, EX.XoloError]:
        try:
            doc = self.collection.find_one({
                "name":name,
            })
            if doc == None:
                return Ok(False)
            return Ok(True)
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
    def find_scope_by_name(self, name:str)->Result[ScopeModel, EX.XoloError]:
        try:
            doc = self.collection.find_one({
                "name":name
            })
            if doc == None:
                return Err(EX.NotFound(entity="Scope"))
            return Ok(ScopeModel(**doc))
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
        
    def create(self,dto:CreateScopeDTO)->Result[str, EX.XoloError]:
        try:
            doc = ScopeModel(
                name= dto.name
            )
            self.collection.insert_one(doc.model_dump())
            return Ok(dto.name)
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
    def assign(self,dto:AssignScopeDTO)->Result[str,EX.XoloError]:
        try:
            doc = ScopeUserModel(
                name=dto.name,
                username = dto.username
            )
            self.scope_user_collection.insert_one(doc.model_dump())
            return Ok(dto.name)
        except Exception as e:
            return Err(EX.ServerError(message=str(e)))
        