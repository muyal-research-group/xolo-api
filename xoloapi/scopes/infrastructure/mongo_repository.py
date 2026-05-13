from motor.motor_asyncio import AsyncIOMotorCollection
from option import Err, Ok, Result
from xoloapi.log import Log

import commonx.errors as EX
import commonx.models.xolo as MX
import xoloapi.config as Cfg
from xoloapi.log.format import build_log_payload

from xoloapi.scopes.dto import AssignScopeDTO, CreateScopeDTO

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoScopesRepository:
    def __init__(
        self,
        collection: AsyncIOMotorCollection,
        scope_user_collection: AsyncIOMotorCollection,
    ):
        self.collection = collection
        self.scope_user_collection = scope_user_collection

    async def exists_scope_user(self, account_id: str, name: str, username: str) -> Result[bool, EX.XError]:
        try:
            doc = await self.scope_user_collection.find_one(
                {"account_id": account_id, "name": name.strip().upper(), "username": username.strip()}
            )
            return Ok(doc is not None)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.exists_user.error", error=e, scope_name=name, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def count_scope_users(self, account_id: str, name: str) -> Result[int, EX.XError]:
        normalized_name = name.strip().upper()
        try:
            count = await self.scope_user_collection.count_documents({"account_id": account_id, "name": normalized_name})
            return Ok(count)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.count_users.error", error=e, scope_name=normalized_name))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def exists_scope(self, account_id: str, name: str) -> Result[bool, EX.XError]:
        try:
            doc = await self.collection.find_one({"account_id": account_id, "name": name.strip().upper()})
            return Ok(doc is not None)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.exists.error", error=e, scope_name=name))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def find_scope_by_name(self, account_id: str, name: str) -> Result[MX.ScopeModel, EX.XError]:
        try:
            doc = await self.collection.find_one({"account_id": account_id, "name": name.strip().upper()})
            if doc is None:
                return Err(EX.NotFound(metadata={"entity": "Scope"}))
            doc.pop("account_id", None)
            return Ok(MX.ScopeModel(**doc))
        except Exception as e:
            log.error(build_log_payload("scopes.repository.find_by_name.error", error=e, scope_name=name))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def create(self, account_id: str, dto: CreateScopeDTO) -> Result[str, EX.XError]:
        try:
            doc = MX.ScopeModel(name=dto.name.strip().upper())
            payload = doc.model_dump()
            payload["account_id"] = account_id
            await self.collection.insert_one(payload)
            return Ok(doc.name)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.create.error", error=e, scope_name=dto.name))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def delete(self, account_id: str, name: str) -> Result[bool, EX.XError]:
        normalized_name = name.strip().upper()
        try:
            result = await self.collection.delete_one({"account_id": account_id, "name": normalized_name})
            if result.deleted_count == 0:
                return Err(EX.NotFound(raw_detail="Scope not found", metadata={"entity": "Scope", "id": normalized_name}))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.delete.error", error=e, scope_name=normalized_name))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def assign(self, account_id: str, dto: AssignScopeDTO) -> Result[str, EX.XError]:
        try:
            doc = MX.ScopeUserModel(name=dto.name.strip().upper(), username=dto.username.strip())
            payload = doc.model_dump()
            payload["account_id"] = account_id
            await self.scope_user_collection.insert_one(payload)
            return Ok(doc.name)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.assign.error", error=e, scope_name=dto.name, username=dto.username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def unassign(self, account_id: str, dto: AssignScopeDTO) -> Result[bool, EX.XError]:
        normalized_name = dto.name.strip().upper()
        normalized_username = dto.username.strip()
        try:
            result = await self.scope_user_collection.delete_one({"account_id": account_id, "name": normalized_name, "username": normalized_username})
            if result.deleted_count == 0:
                return Err(EX.NotFound(raw_detail="Scope assignment not found"))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.unassign.error", error=e, scope_name=normalized_name, username=normalized_username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def find_all_scopes(self, account_id: str) -> Result[list[MX.ScopeModel], EX.XError]:
        try:
            scopes = []
            async for doc in self.collection.find({"account_id": account_id}):
                doc.pop("account_id", None)
                scopes.append(MX.ScopeModel(**doc))
            return Ok(scopes)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.find_all.error", error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def find_all_scope_users(self, account_id: str) -> Result[list[MX.ScopeUserModel], EX.XError]:
        try:
            assignments = []
            async for doc in self.scope_user_collection.find({"account_id": account_id}).sort([("name", 1), ("username", 1)]):
                doc.pop("account_id", None)
                assignments.append(MX.ScopeUserModel(**doc))
            return Ok(assignments)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.find_all_users.error", error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def delete_assignments_for_username(self, account_id: str, username: str) -> Result[int, EX.XError]:
        normalized_username = username.strip()
        try:
            result = await self.scope_user_collection.delete_many({"account_id": account_id, "username": normalized_username})
            return Ok(result.deleted_count)
        except Exception as e:
            log.error(build_log_payload("scopes.repository.delete_user_assignments.error", error=e, username=normalized_username))
            return Err(EX.ServerError(raw_detail=str(e)))
