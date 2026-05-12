from motor.motor_asyncio import AsyncIOMotorCollection
import option as OP
from xoloapi.log import Log

import commonx.errors as EX
import commonx.models.xolo as M
import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoLicensesRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def create(self, account_id: str, username: str, license: str, scope: str, expires_at: str) -> OP.Result[bool, EX.XError]:
        try:
            model = M.LicenseAssignedModel(
                username=username,
                license=license,
                scope=scope,
                expires_at=expires_at,
            )
            payload = model.model_dump()
            payload["account_id"] = account_id
            await self.collection.insert_one(document=payload)
            return OP.Ok(True)
        except Exception as e:
            log.error(build_log_payload("licenses.repository.create.error", error=e, username=username, scope_name=scope))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def find_by_username_and_scope(self, account_id: str, username: str, scope: str) -> OP.Result[str, EX.XError]:
        try:
            doc = await self.collection.find_one({"account_id": account_id, "username": username, "scope": scope.strip().upper()})
            if doc is None:
                return OP.Err(EX.NotFound(metadata={"entity": "License"}))
            return OP.Ok(doc.get("license"))
        except Exception as e:
            log.error(build_log_payload("licenses.repository.find_by_user_scope.error", error=e, username=username, scope_name=scope))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def delete_by_username_scope(self, account_id: str, username: str, scope: str) -> OP.Result[bool, EX.XError]:
        try:
            result = await self.collection.delete_one({"account_id": account_id, "username": username, "scope": scope.strip().upper()})
            if result.deleted_count > 0:
                return OP.Ok(True)
            return OP.Err(EX.NotFound(metadata={"entity": "License"}))
        except Exception as e:
            log.error(build_log_payload("licenses.repository.delete.error", error=e, username=username, scope_name=scope))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def count_by_scope(self, account_id: str, scope: str) -> OP.Result[int, EX.XError]:
        normalized_scope = scope.strip().upper()
        try:
            count = await self.collection.count_documents({"account_id": account_id, "scope": normalized_scope})
            return OP.Ok(count)
        except Exception as e:
            log.error(build_log_payload("licenses.repository.count_scope.error", error=e, scope_name=normalized_scope))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def find_all(self, account_id: str) -> OP.Result[list[M.LicenseAssignedModel], EX.XError]:
        try:
            licenses = []
            async for doc in self.collection.find({"account_id": account_id}).sort([("scope", 1), ("username", 1)]):
                doc.pop("account_id", None)
                licenses.append(M.LicenseAssignedModel(**doc))
            return OP.Ok(licenses)
        except Exception as e:
            log.error(build_log_payload("licenses.repository.find_all.error", error=e))
            return OP.Err(EX.ServerError(raw_detail=str(e)))

    async def delete_all_by_username(self, account_id: str, username: str) -> OP.Result[int, EX.XError]:
        try:
            result = await self.collection.delete_many({"account_id": account_id, "username": username.strip()})
            return OP.Ok(result.deleted_count)
        except Exception as e:
            log.error(build_log_payload("licenses.repository.delete_all_by_user.error", error=e, username=username))
            return OP.Err(EX.ServerError(raw_detail=str(e)))
