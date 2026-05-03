import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Option, Some, NONE, Result, Ok, Err
from xolo.log import Log

import xoloapi.config as Cfg
from xoloapi.acl.domain.aggregates import GroupMember, SecurityGroup
from xoloapi.acl.domain.repositories import ISecurityGroupRepository
from xoloapi.errors.base import DatabaseError, XoloException
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


def _doc_to_group(doc: dict) -> SecurityGroup:
    return SecurityGroup(
        account_id  = doc["account_id"],
        group_id    = doc["group_id"],
        name        = doc["name"],
        owner_id    = doc["owner_id"],
        description = doc.get("description"),
        created_at  = doc.get("created_at", datetime.datetime.now(datetime.timezone.utc)),
        updated_at  = doc.get("updated_at", datetime.datetime.now(datetime.timezone.utc)),
    )


class MongoSecurityGroupRepository(ISecurityGroupRepository):

    def __init__(self, db: AsyncIOMotorDatabase, groups_col: str, members_col: str):
        self.groups  = db[groups_col]
        self.members = db[members_col]

    # ── Groups ────────────────────────────────────────────────────────────────

    async def list_all(self, account_id: str) -> Result[list[SecurityGroup], XoloException]:
        try:
            groups: list[SecurityGroup] = []
            async for doc in self.groups.find({"account_id": account_id}, {"_id": 0}).sort([("name", 1)]):
                groups.append(_doc_to_group(doc))
            return Ok(groups)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.list_all.error", error=e))
            return Err(DatabaseError("Failed to list groups", cause=e))

    async def find_by_id(self, account_id: str, group_id: str) -> Result[Option[SecurityGroup], XoloException]:
        try:
            doc = await self.groups.find_one({"account_id": account_id, "group_id": group_id}, {"_id": 0})
            return Ok(NONE if doc is None else Some(_doc_to_group(doc)))
        except Exception as e:
            log.error(build_log_payload("acl.security_group.find_by_id.error", error=e, group_id=group_id))
            return Err(DatabaseError(f"Failed to find group '{group_id}'", cause=e))

    async def find_by_name(self, account_id: str, name: str) -> Result[Option[SecurityGroup], XoloException]:
        try:
            doc = await self.groups.find_one({"account_id": account_id, "name": name}, {"_id": 0})
            return Ok(NONE if doc is None else Some(_doc_to_group(doc)))
        except Exception as e:
            log.error(build_log_payload("acl.security_group.find_by_name.error", error=e, group_name=name))
            return Err(DatabaseError(f"Failed to find group by name '{name}'", cause=e))

    async def find_groups_for_user(self, account_id: str, user_id: str) -> Result[list[SecurityGroup], XoloException]:
        """Returns all groups where user is owner OR a member."""
        try:
            member_docs = self.members.find({"account_id": account_id, "user_id": user_id}, {"group_id": 1, "_id": 0})
            group_ids: list[str] = []
            async for doc in member_docs:
                group_ids.append(doc["group_id"])

            groups: list[SecurityGroup] = []
            if group_ids:
                async for doc in self.groups.find(
                    {"account_id": account_id, "$or": [{"group_id": {"$in": group_ids}}, {"owner_id": user_id}]},
                    {"_id": 0},
                ):
                    groups.append(_doc_to_group(doc))
            else:
                async for doc in self.groups.find({"account_id": account_id, "owner_id": user_id}, {"_id": 0}):
                    groups.append(_doc_to_group(doc))

            return Ok(groups)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.find_for_user.error", error=e, actor_user_id=user_id))
            return Err(DatabaseError("Failed to list groups for user", cause=e))

    async def find_group_ids_for_user(self, account_id: str, user_id: str) -> Result[list[str], XoloException]:
        try:
            ids: list[str] = []
            async for doc in self.members.find({"account_id": account_id, "user_id": user_id}, {"group_id": 1, "_id": 0}):
                ids.append(doc["group_id"])
            return Ok(ids)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.find_ids_for_user.error", error=e, actor_user_id=user_id))
            return Err(DatabaseError("Failed to resolve group IDs for user", cause=e))

    async def save(self, group: SecurityGroup) -> Result[SecurityGroup, XoloException]:
        try:
            doc = group.model_dump()
            await self.groups.replace_one({"account_id": group.account_id, "group_id": group.group_id}, doc, upsert=True)
            return Ok(group)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.save.error", error=e, group_id=group.group_id, actor_user_id=group.owner_id))
            return Err(DatabaseError(f"Failed to save group '{group.group_id}'", cause=e))

    async def delete(self, account_id: str, group_id: str) -> Result[bool, XoloException]:
        try:
            result = await self.groups.delete_one({"account_id": account_id, "group_id": group_id})
            if result.deleted_count == 0:
                return Err(DatabaseError(f"Group '{group_id}' not found"))
            await self.members.delete_many({"account_id": account_id, "group_id": group_id})
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.delete.error", error=e, group_id=group_id))
            return Err(DatabaseError(f"Failed to delete group '{group_id}'", cause=e))

    # ── Members ───────────────────────────────────────────────────────────────

    async def add_member(self, account_id: str, group_id: str, user_id: str) -> Result[bool, XoloException]:
        try:
            existing = await self.members.find_one({"account_id": account_id, "group_id": group_id, "user_id": user_id})
            if existing:
                return Ok(True)
            member = GroupMember(account_id=account_id, group_id=group_id, user_id=user_id)
            await self.members.insert_one(member.model_dump())
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.add_member.error", error=e, group_id=group_id, user_id=user_id))
            return Err(DatabaseError(f"Failed to add member '{user_id}' to group '{group_id}'", cause=e))

    async def remove_member(self, account_id: str, group_id: str, user_id: str) -> Result[bool, XoloException]:
        try:
            await self.members.delete_one({"account_id": account_id, "group_id": group_id, "user_id": user_id})
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.remove_member.error", error=e, group_id=group_id, user_id=user_id))
            return Err(DatabaseError(f"Failed to remove member '{user_id}' from group '{group_id}'", cause=e))

    async def list_members(self, account_id: str, group_id: str) -> Result[list[GroupMember], XoloException]:
        try:
            members: list[GroupMember] = []
            async for doc in self.members.find({"account_id": account_id, "group_id": group_id}, {"_id": 0}):
                members.append(GroupMember(
                    account_id = doc["account_id"],
                    group_id   = doc["group_id"],
                    user_id    = doc["user_id"],
                    joined_at  = doc.get("joined_at", datetime.datetime.now(datetime.timezone.utc)),
                ))
            return Ok(members)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.list_members.error", error=e, group_id=group_id))
            return Err(DatabaseError(f"Failed to list members of group '{group_id}'", cause=e))

    async def is_member(self, account_id: str, group_id: str, user_id: str) -> Result[bool, XoloException]:
        try:
            doc = await self.members.find_one({"account_id": account_id, "group_id": group_id, "user_id": user_id})
            return Ok(doc is not None)
        except Exception as e:
            log.error(build_log_payload("acl.security_group.is_member.error", error=e, group_id=group_id, user_id=user_id))
            return Err(DatabaseError("Failed to check group membership", cause=e))
