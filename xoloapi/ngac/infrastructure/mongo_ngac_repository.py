from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Result, Ok, Err, Some, NONE
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.errors.base import DatabaseError, NotFoundError, XoloException, AlreadyExistsError
from xoloapi.ngac.domain.aggregates import NGACAssignment, NGACAssociation, NGACNode
from xoloapi.ngac.domain.repositories import INGACRepository
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoNGACRepository(INGACRepository):

    def __init__(
        self,
        db:                  AsyncIOMotorDatabase,
        nodes_col:           str,
        assignments_col:     str,
        associations_col:    str,
    ) -> None:
        self._nodes        = db[nodes_col]
        self._assignments  = db[assignments_col]
        self._associations = db[associations_col]

    # ── Nodes ─────────────────────────────────────────────────────────────────

    async def create_node(self, node: NGACNode) -> Result[str, XoloException]:
        try:
            existing = await self._nodes.find_one({"account_id": node.account_id, "node_id": node.node_id})
            if existing:
                return Err(AlreadyExistsError("NGACNode", node.node_id))
            await self._nodes.insert_one(node.model_dump())
            return Ok(node.node_id)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.create_node.error", error=e, node_id=node.node_id, node_type=node.node_type))
            return Err(DatabaseError(cause=e))

    async def find_node(self, account_id: str, node_id: str) -> Result[object, XoloException]:
        try:
            doc = await self._nodes.find_one({"account_id": account_id, "node_id": node_id}, {"_id": 0})
            return Ok(Some(NGACNode(**doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.find_node.error", error=e, node_id=node_id))
            return Err(DatabaseError(cause=e))

    async def list_nodes(self, account_id: str, node_type: str | None = None) -> Result[list[NGACNode], XoloException]:
        try:
            query  = {"account_id": account_id, "node_type": node_type} if node_type else {"account_id": account_id}
            cursor = self._nodes.find(query, {"_id": 0})
            docs   = await cursor.to_list(length=None)
            return Ok([NGACNode(**d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("ngac.repository.list_nodes.error", error=e, node_type=node_type))
            return Err(DatabaseError(cause=e))

    async def delete_node(self, account_id: str, node_id: str) -> Result[bool, XoloException]:
        try:
            result = await self._nodes.delete_one({"account_id": account_id, "node_id": node_id})
            if result.deleted_count == 0:
                return Err(NotFoundError("NGACNode", node_id))
            # Cascade: remove all related assignments and associations
            await self._assignments.delete_many(
                {"account_id": account_id, "$or": [{"from_id": node_id}, {"to_id": node_id}]}
            )
            await self._associations.delete_many(
                {"account_id": account_id, "$or": [
                    {"user_attribute_id": node_id},
                    {"object_attribute_id": node_id},
                ]}
            )
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.delete_node.error", error=e, node_id=node_id))
            return Err(DatabaseError(cause=e))

    # ── Assignments ───────────────────────────────────────────────────────────

    async def create_assignment(self, assignment: NGACAssignment) -> Result[str, XoloException]:
        try:
            existing = await self._assignments.find_one(
                {"account_id": assignment.account_id, "from_id": assignment.from_id, "to_id": assignment.to_id}
            )
            if existing:
                return Ok(assignment.assignment_id)  # idempotent
            await self._assignments.insert_one(assignment.model_dump())
            return Ok(assignment.assignment_id)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.create_assignment.error", error=e, assignment_id=assignment.assignment_id, from_id=assignment.from_id, to_id=assignment.to_id))
            return Err(DatabaseError(cause=e))

    async def find_assignment(self, account_id: str, from_id: str, to_id: str) -> Result[object, XoloException]:
        try:
            doc = await self._assignments.find_one(
                {"account_id": account_id, "from_id": from_id, "to_id": to_id}, {"_id": 0}
            )
            return Ok(Some(NGACAssignment(**doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.find_assignment.error", error=e, from_id=from_id, to_id=to_id))
            return Err(DatabaseError(cause=e))

    async def remove_assignment(self, account_id: str, from_id: str, to_id: str) -> Result[bool, XoloException]:
        try:
            result = await self._assignments.delete_one({"account_id": account_id, "from_id": from_id, "to_id": to_id})
            if result.deleted_count == 0:
                return Err(NotFoundError("NGACAssignment", f"{from_id}->{to_id}"))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.remove_assignment.error", error=e, from_id=from_id, to_id=to_id))
            return Err(DatabaseError(cause=e))

    async def list_assignments(self, account_id: str) -> Result[list[NGACAssignment], XoloException]:
        try:
            cursor = self._assignments.find({"account_id": account_id}, {"_id": 0})
            docs   = await cursor.to_list(length=None)
            return Ok([NGACAssignment(**d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("ngac.repository.list_assignments.error", error=e))
            return Err(DatabaseError(cause=e))

    # ── Associations ──────────────────────────────────────────────────────────

    async def create_association(self, assoc: NGACAssociation) -> Result[str, XoloException]:
        try:
            await self._associations.update_one(
                {
                    "account_id":          assoc.account_id,
                    "user_attribute_id":   assoc.user_attribute_id,
                    "object_attribute_id": assoc.object_attribute_id,
                },
                {"$set": assoc.model_dump()},
                upsert=True,
            )
            return Ok(assoc.association_id)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.create_association.error", error=e, association_id=assoc.association_id, user_attribute_id=assoc.user_attribute_id, object_attribute_id=assoc.object_attribute_id))
            return Err(DatabaseError(cause=e))

    async def find_association(self, account_id: str, association_id: str) -> Result[object, XoloException]:
        try:
            doc = await self._associations.find_one(
                {"account_id": account_id, "association_id": association_id}, {"_id": 0}
            )
            return Ok(Some(NGACAssociation(**doc)) if doc else NONE)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.find_association.error", error=e, association_id=association_id))
            return Err(DatabaseError(cause=e))

    async def remove_association(self, account_id: str, association_id: str) -> Result[bool, XoloException]:
        try:
            result = await self._associations.delete_one({"account_id": account_id, "association_id": association_id})
            if result.deleted_count == 0:
                return Err(NotFoundError("NGACAssociation", association_id))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("ngac.repository.remove_association.error", error=e, association_id=association_id))
            return Err(DatabaseError(cause=e))

    async def list_associations(self, account_id: str) -> Result[list[NGACAssociation], XoloException]:
        try:
            cursor = self._associations.find({"account_id": account_id}, {"_id": 0})
            docs   = await cursor.to_list(length=None)
            return Ok([NGACAssociation(**d) for d in docs])
        except Exception as e:
            log.error(build_log_payload("ngac.repository.list_associations.error", error=e))
            return Err(DatabaseError(cause=e))

    # ── Graph snapshot ────────────────────────────────────────────────────────

    async def load_graph_data(self, account_id: str) -> Result[tuple, XoloException]:
        nodes_r = await self.list_nodes(account_id)
        if nodes_r.is_err:
            return nodes_r

        assign_r = await self.list_assignments(account_id)
        if assign_r.is_err:
            return assign_r

        assoc_r = await self.list_associations(account_id)
        if assoc_r.is_err:
            return assoc_r

        return Ok((nodes_r.unwrap(), assign_r.unwrap(), assoc_r.unwrap()))
