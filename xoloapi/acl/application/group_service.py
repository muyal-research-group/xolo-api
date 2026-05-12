import uuid
from option import Result, Ok, Err

from xoloapi.acl.domain.aggregates import GroupMember, SecurityGroup
from xoloapi.acl.domain.repositories import ISecurityGroupRepository
from xoloapi.errors.base import (
    AccessDeniedError,
    AlreadyExistsError,
    NotFoundError,
    XoloException,
)


class GroupService:

    def __init__(self, repo: ISecurityGroupRepository):
        self.repo = repo

    async def list_groups(self, account_id: str) -> Result[list[SecurityGroup], XoloException]:
        return await self.repo.list_all(account_id)

    async def list_principals(self, account_id: str) -> Result[list[dict], XoloException]:
        """Return a simple list of principals for discovery (users as principals for now)."""
        # In a real implementation, this would return all unique principals in policies
        # For now, return empty list - can be extended to fetch from users service
        return Ok([])

    async def list_members(self, account_id: str, group_id: str) -> Result[list[GroupMember], XoloException]:
        return await self.repo.list_members(account_id, group_id)

    async def create_group(
        self, account_id: str, owner_id: str, name: str, description: str = ""
    ) -> Result[str, XoloException]:
        exists = await self.repo.find_by_name(account_id, name)
        if exists.is_err:
            return Err(exists.unwrap_err())
        if exists.unwrap().is_some:
            return Err(AlreadyExistsError("SecurityGroup", name))

        group_id = f"g-{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        group = SecurityGroup(
            account_id  = account_id,
            group_id    = group_id,
            name        = name,
            owner_id    = owner_id,
            description = description or None,
        )

        save = await self.repo.save(group)
        if save.is_err:
            return Err(save.unwrap_err())

        add = await self.repo.add_member(account_id, group_id, owner_id)
        if add.is_err:
            return Err(add.unwrap_err())

        return Ok(group_id)

    async def delete_group(self, account_id: str, caller_id: str, group_id: str) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        if not group.is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the group owner can delete this group"))

        return await self.repo.delete(account_id, group_id)

    async def delete_group_admin(self, account_id: str, group_id: str) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        return await self.repo.delete(account_id, group_id)

    async def add_members(
        self, account_id: str, caller_id: str, group_id: str, user_ids: list[str]
    ) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        if not group.is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the group owner can add members"))

        for user_id in user_ids:
            r = await self.repo.add_member(account_id, group_id, user_id)
            if r.is_err:
                return Err(r.unwrap_err())
        return Ok(True)

    async def add_members_admin(self, account_id: str, group_id: str, user_ids: list[str]) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        for user_id in user_ids:
            r = await self.repo.add_member(account_id, group_id, user_id)
            if r.is_err:
                return Err(r.unwrap_err())
        return Ok(True)

    async def remove_members(
        self, account_id: str, caller_id: str, group_id: str, user_ids: list[str]
    ) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        for user_id in user_ids:
            if caller_id != user_id and not group.is_owned_by(caller_id):
                return Err(AccessDeniedError(
                    "Only the group owner can remove other members",
                    metadata={"group_id": group_id, "target_user": user_id},
                ))
            r = await self.repo.remove_member(account_id, group_id, user_id)
            if r.is_err:
                return Err(r.unwrap_err())
        return Ok(True)

    async def remove_members_admin(self, account_id: str, group_id: str, user_ids: list[str]) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        for user_id in user_ids:
            r = await self.repo.remove_member(account_id, group_id, user_id)
            if r.is_err:
                return Err(r.unwrap_err())
        return Ok(True)
