from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Result, Ok, Err, Some, NONE
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.errors.base import DatabaseError, XoloException
from xoloapi.rbac.domain.aggregates import Role
from xoloapi.rbac.domain.repositories import IRoleRepository
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoRoleRepository(IRoleRepository):

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str) -> None:
        self._col = db[collection_name]

    # ── Serialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_doc(role: Role) -> dict:
        d = role.model_dump()
        d["_id"] = d.pop("role_id")
        return d

    @staticmethod
    def _from_doc(doc: dict) -> Role:
        doc = dict(doc)
        doc["role_id"] = doc.pop("_id")
        return Role(**doc)

    # ── IRoleRepository ───────────────────────────────────────────────────────

    async def find_by_id(self, account_id: str, role_id: str) -> Result[object, XoloException]:
        try:
            doc = await self._col.find_one({"_id": role_id, "account_id": account_id})
            return Ok(Some(self._from_doc(doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("rbac.role_repository.find_by_id.error", error=e, role_id=role_id))
            return Err(DatabaseError(cause=e))

    async def find_by_name(self, account_id: str, name: str) -> Result[object, XoloException]:
        try:
            doc = await self._col.find_one({"account_id": account_id, "name": name})
            return Ok(Some(self._from_doc(doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("rbac.role_repository.find_by_name.error", error=e, role_name=name))
            return Err(DatabaseError(cause=e))

    async def find_many(self, account_id: str, role_ids: list[str]) -> Result[list[Role], XoloException]:
        try:
            cursor = self._col.find({"account_id": account_id, "_id": {"$in": role_ids}})
            docs   = await cursor.to_list(length=None)
            return Ok([self._from_doc(d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("rbac.role_repository.find_many.error", error=e, role_ids=role_ids))
            return Err(DatabaseError(cause=e))

    async def find_all(self, account_id: str) -> Result[list[Role], XoloException]:
        try:
            cursor = self._col.find({"account_id": account_id})
            docs   = await cursor.to_list(length=None)
            return Ok([self._from_doc(d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("rbac.role_repository.find_all.error", error=e))
            return Err(DatabaseError(cause=e))

    async def save(self, role: Role) -> Result[None, XoloException]:
        try:
            doc = self._to_doc(role)
            await self._col.replace_one({"_id": role.role_id}, doc, upsert=True)
            return Ok(None)
        except Exception as e:
            log.error(build_log_payload("rbac.role_repository.save.error", error=e, role_id=role.role_id, role_name=role.name))
            return Err(DatabaseError(cause=e))

    async def delete(self, account_id: str, role_id: str) -> Result[None, XoloException]:
        try:
            await self._col.delete_one({"_id": role_id, "account_id": account_id})
            return Ok(None)
        except Exception as e:
            log.error(build_log_payload("rbac.role_repository.delete.error", error=e, role_id=role_id))
            return Err(DatabaseError(cause=e))
