import uuid
from option import Result, Ok, Err

from xoloapi.groups.domain.aggregates import GroupMember, SecurityGroup
from xoloapi.groups.domain.repositories import ISecurityGroupRepository
from xoloapi.errors.base import (
    AccessDeniedError,
    AlreadyExistsError,
    NotFoundError,
    XoloException,
)


class GroupService:

    def __init__(self, repo: ISecurityGroupRepository, users_repo=None):
        self.repo = repo
        self.users_repo = users_repo

    async def list_groups(self, account_id: str) -> Result[list[SecurityGroup], XoloException]:
        return await self.repo.list_all(account_id)

    async def list_principals(self, account_id: str) -> Result[list[dict], XoloException]:
        principals: list[dict] = []
        if self.users_repo is not None:
            users = await self.users_repo.find_all(account_id)
            if users.is_err:
                return Err(users.unwrap_err())
            principals.extend({
                "id": user.key,
                "name": user.username,
                "type": "USER",
                "label": f"{user.username} ({user.first_name} {user.last_name})".strip(),
            } for user in users.unwrap())
        groups = await self.repo.list_all(account_id)
        if groups.is_err:
            return Err(groups.unwrap_err())
        principals.extend({
            "id": group.group_id,
            "name": group.name,
            "type": "GROUP",
            "label": group.name,
        } for group in groups.unwrap())
        return Ok(principals)

    async def resolve_usernames(self, account_id: str, usernames: list[str]) -> Result[list[str], XoloException]:
        if not usernames:
            return Ok([])
        if self.users_repo is None:
            return Err(NotFoundError("User", usernames[0]))
        user_ids: list[str] = []
        for username in usernames:
            maybe_user = await self.users_repo.find_by_username(account_id, username.strip())
            if maybe_user.is_none:
                return Err(NotFoundError("User", username))
            user_ids.append(maybe_user.unwrap().key)
        return Ok(user_ids)

    async def validate_user_ids(self, account_id: str, user_ids: list[str]) -> Result[list[str], XoloException]:
        if self.users_repo is None:
            return Ok(user_ids)
        for user_id in user_ids:
            maybe_user = await self.users_repo.find_by_id(user_id, account_id=account_id)
            if maybe_user.is_none:
                return Err(NotFoundError("User", user_id))
        return Ok(user_ids)

    async def list_members(self, account_id: str, group_id: str) -> Result[list[GroupMember], XoloException]:
        return await self.repo.list_members(account_id, group_id)

    async def is_member(self, account_id: str, user_id: str, group_id: str) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        return await self.repo.is_member(account_id, group_id, user_id)

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
        self, account_id: str, caller_id: str, group_id: str, user_ids: list[str], usernames: list[str] | None = None
    ) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        if not group.is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the group owner can add members"))

        resolved = await self.resolve_usernames(account_id, usernames or [])
        if resolved.is_err:
            return Err(resolved.unwrap_err())
        validated = await self.validate_user_ids(account_id, user_ids)
        if validated.is_err:
            return Err(validated.unwrap_err())
        user_ids = list(dict.fromkeys(validated.unwrap() + resolved.unwrap()))

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
        self, account_id: str, caller_id: str, group_id: str, user_ids: list[str], usernames: list[str] | None = None
    ) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        resolved = await self.resolve_usernames(account_id, usernames or [])
        if resolved.is_err:
            return Err(resolved.unwrap_err())
        validated = await self.validate_user_ids(account_id, user_ids)
        if validated.is_err:
            return Err(validated.unwrap_err())
        user_ids = list(dict.fromkeys(validated.unwrap() + resolved.unwrap()))
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

    async def list_members_authorized(
        self,
        account_id: str,
        group_id: str,
        caller_id: str,
        is_admin: bool = False,
    ) -> Result[list[GroupMember], XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        group = find.unwrap().unwrap()
        if not is_admin and not group.is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the group owner can list members"))
        return await self.repo.list_members(account_id, group_id)

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

    async def transfer_owner_admin(
        self,
        account_id: str,
        group_id: str,
        new_owner_id: str,
        keep_previous_as_member: bool = True,
    ) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        previous_owner_id = group.owner_id
        add = await self.repo.add_member(account_id, group_id, new_owner_id)
        if add.is_err:
            return Err(add.unwrap_err())

        # Remove first: if saving the new owner fails, the previous owner still
        # owns the group and therefore retains effective membership. Retrying is
        # safe because member removal is idempotent.
        if not keep_previous_as_member and previous_owner_id != new_owner_id:
            removed = await self.repo.remove_member(account_id, group_id, previous_owner_id)
            if removed.is_err:
                return Err(removed.unwrap_err())

        saved = await self.repo.save(group.model_copy(update={"owner_id": new_owner_id}))
        if saved.is_err:
            return Err(saved.unwrap_err())
        return Ok(True)
