from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Result, Ok, Err, Some, NONE
from xolo.log import Log

import xoloapi.config as Cfg
from xoloapi.errors.base import DatabaseError, XoloException
from xoloapi.rbac.domain.aggregates import RoleAssignment
from xoloapi.rbac.domain.repositories import IRoleAssignmentRepository
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoRoleAssignmentRepository(IRoleAssignmentRepository):

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str) -> None:
        self._col = db[collection_name]

    # ── Serialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_doc(ra: RoleAssignment) -> dict:
        d = ra.model_dump()
        d["_id"] = d.pop("assignment_id")
        return d

    @staticmethod
    def _from_doc(doc: dict) -> RoleAssignment:
        doc = dict(doc)
        doc["assignment_id"] = doc.pop("_id")
        return RoleAssignment(**doc)

    # ── IRoleAssignmentRepository ─────────────────────────────────────────────

    async def find_all(self, account_id: str) -> Result[list[RoleAssignment], XoloException]:
        try:
            cursor = self._col.find({"account_id": account_id})
            docs = await cursor.to_list(length=None)
            return Ok([self._from_doc(d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.find_all.error", error=e))
            return Err(DatabaseError(cause=e))

    async def find_by_subject(self, account_id: str, subject_id: str) -> Result[list[RoleAssignment], XoloException]:
        try:
            cursor = self._col.find({"account_id": account_id, "subject_id": subject_id})
            docs   = await cursor.to_list(length=None)
            return Ok([self._from_doc(d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.find_by_subject.error", error=e, subject_id=subject_id))
            return Err(DatabaseError(cause=e))

    async def find_by_role(self, account_id: str, role_id: str) -> Result[list[RoleAssignment], XoloException]:
        try:
            cursor = self._col.find({"account_id": account_id, "role_id": role_id})
            docs   = await cursor.to_list(length=None)
            return Ok([self._from_doc(d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.find_by_role.error", error=e, role_id=role_id))
            return Err(DatabaseError(cause=e))

    async def find_assignment(self, account_id: str, subject_id: str, role_id: str) -> Result[object, XoloException]:
        try:
            doc = await self._col.find_one({"account_id": account_id, "subject_id": subject_id, "role_id": role_id})
            return Ok(Some(self._from_doc(doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.find_assignment.error", error=e, subject_id=subject_id, role_id=role_id))
            return Err(DatabaseError(cause=e))

    async def save(self, assignment: RoleAssignment) -> Result[None, XoloException]:
        try:
            doc = self._to_doc(assignment)
            await self._col.replace_one({"_id": assignment.assignment_id}, doc, upsert=True)
            return Ok(None)
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.save.error", error=e, assignment_id=assignment.assignment_id, subject_id=assignment.subject_id, role_id=assignment.role_id))
            return Err(DatabaseError(cause=e))

    async def delete(self, account_id: str, assignment_id: str) -> Result[None, XoloException]:
        try:
            await self._col.delete_one({"_id": assignment_id, "account_id": account_id})
            return Ok(None)
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.delete.error", error=e, assignment_id=assignment_id))
            return Err(DatabaseError(cause=e))

    async def delete_by_subject(self, account_id: str, subject_id: str) -> Result[None, XoloException]:
        try:
            await self._col.delete_many({"account_id": account_id, "subject_id": subject_id})
            return Ok(None)
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.delete_by_subject.error", error=e, subject_id=subject_id))
            return Err(DatabaseError(cause=e))

    async def delete_by_role(self, account_id: str, role_id: str) -> Result[None, XoloException]:
        try:
            await self._col.delete_many({"account_id": account_id, "role_id": role_id})
            return Ok(None)
        except Exception as e:
            log.error(build_log_payload("rbac.role_assignment_repository.delete_by_role.error", error=e, role_id=role_id))
            return Err(DatabaseError(cause=e))
