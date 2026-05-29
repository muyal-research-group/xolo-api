import math
from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Option, Some, NONE, Result, Ok, Err
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.acl.domain.aggregates import AccessGrant, ResourcePolicy
from xoloapi.acl.domain.repositories import IResourcePolicyRepository
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType
from xoloapi.errors.base import DatabaseError, XoloException
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def _doc_to_policy(doc: dict) -> ResourcePolicy:
    grants = []
    for g in doc.get("grants", []):
        grants.append(AccessGrant(
            grant_id   = g["grant_id"],
            principal  = Principal(type=PrincipalType(g["principal_type"]), id=g["principal_id"]),
            permissions= {Permission(p) for p in g["permissions"]},
            is_owner   = g.get("is_owner", False),
        ))
    return ResourcePolicy(account_id=doc["account_id"], resource_id=doc["resource_id"], grants=grants)


def _policy_to_doc(policy: ResourcePolicy) -> dict:
    return {
        "account_id": policy.account_id,
        "resource_id": policy.resource_id,
        "grants": [
            {
                "grant_id":      g.grant_id,
                "principal_type": g.principal.type.value,
                "principal_id":  g.principal.id,
                "permissions":   [p.value for p in g.permissions],
                "is_owner":      g.is_owner,
            }
            for g in policy.grants
        ],
    }


class MongoResourcePolicyRepository(IResourcePolicyRepository):

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.col = db[collection_name]

    async def list_all(self, account_id: str) -> Result[list[ResourcePolicy], XoloException]:
        try:
            policies: list[ResourcePolicy] = []
            async for doc in self.col.find({"account_id": account_id}, {"_id": 0}).sort([("resource_id", 1)]):
                policies.append(_doc_to_policy(doc))
            return Ok(policies)
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.list_all.error", error=e))
            return Err(DatabaseError("Failed to list resource policies", cause=e))

    async def find_by_resource(self, account_id: str, resource_id: str) -> Result[Option[ResourcePolicy], XoloException]:
        try:
            doc = await self.col.find_one({"account_id": account_id, "resource_id": resource_id}, {"_id": 0})
            return Ok(NONE if doc is None else Some(_doc_to_policy(doc)))
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.find_by_resource.error", error=e, resource_id=resource_id))
            return Err(DatabaseError("Failed to find resource policy", cause=e))

    async def find_owned_by(
        self, account_id: str, user_id: str, page: int, page_size: int
    ) -> Result[tuple[list[ResourcePolicy], int], XoloException]:
        try:
            query = {"account_id": account_id, "grants": {"$elemMatch": {"principal_id": user_id, "is_owner": True}}}
            total = await self.col.count_documents(query)
            skip  = (page - 1) * page_size
            docs: list[ResourcePolicy] = []
            async for doc in self.col.find(query, {"_id": 0}).skip(skip).limit(page_size):
                docs.append(_doc_to_policy(doc))
            return Ok((docs, total))
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.find_owned.error", error=e, actor_user_id=user_id, page=page, page_size=page_size))
            return Err(DatabaseError("Failed to list owned resource policies", cause=e))

    async def find_shared_with(
        self,
        account_id:         str,
        principal_ids:       list[str],
        exclude_resource_ids: list[str],
        page:                int,
        page_size:           int,
    ) -> Result[tuple[list[ResourcePolicy], int], XoloException]:
        try:
            query: dict = {
                "account_id": account_id,
                "grants": {"$elemMatch": {"principal_id": {"$in": principal_ids}}},
            }
            if exclude_resource_ids:
                query["resource_id"] = {"$nin": exclude_resource_ids}

            total = await self.col.count_documents(query)
            skip  = (page - 1) * page_size
            docs: list[ResourcePolicy] = []
            async for doc in self.col.find(query, {"_id": 0}).skip(skip).limit(page_size):
                docs.append(_doc_to_policy(doc))
            return Ok((docs, total))
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.find_shared.error", error=e, principal_ids=principal_ids, page=page, page_size=page_size))
            return Err(DatabaseError("Failed to list shared resource policies", cause=e))

    async def save(self, policy: ResourcePolicy) -> Result[ResourcePolicy, XoloException]:
        try:
            await self.col.replace_one(
                {"account_id": policy.account_id, "resource_id": policy.resource_id},
                _policy_to_doc(policy),
                upsert=True,
            )
            return Ok(policy)
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.save.error", error=e, resource_id=policy.resource_id))
            return Err(DatabaseError(f"Failed to save resource policy '{policy.resource_id}'", cause=e))

    async def delete(self, account_id: str, resource_id: str) -> Result[bool, XoloException]:
        try:
            result = await self.col.delete_one({"account_id": account_id, "resource_id": resource_id})
            if result.deleted_count == 0:
                return Err(DatabaseError(f"Resource policy '{resource_id}' not found"))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.delete.error", error=e, resource_id=resource_id))
            return Err(DatabaseError(f"Failed to delete resource policy '{resource_id}'", cause=e))

    async def delete_all_by_user(self, account_id: str, user_id: str) -> Result[int, XoloException]:
        try:
            result = await self.col.delete_many({
                "account_id": account_id,
                "grants": {"$elemMatch": {"principal_id": user_id}},
            })
            return Ok(result.deleted_count)
        except Exception as e:
            log.error(build_log_payload("acl.resource_policy.delete_all_by_user.error", error=e, user_id=user_id))
            return Err(DatabaseError("Failed to delete resource policies for user", cause=e))
