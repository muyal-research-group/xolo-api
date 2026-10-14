import uuid
import datetime
from collections.abc import Awaitable, Callable
from option import Result, Ok, Err

from xoloapi.groups.domain.aggregates import GroupMember, SecurityGroup
from xoloapi.groups.domain.repositories import ISecurityGroupRepository
from xoloapi.errors.base import (
    AccessDeniedError,
    AlreadyExistsError,
    ConflictError,
    NotFoundError,
    XoloException,
)
from xoloapi.users.application.user_resolution import resolve_user_identifier


class GroupService:

    def __init__(
        self,
        repo: ISecurityGroupRepository,
        users_repo=None,
        usage_resolver: Callable[[str, str], Awaitable[dict]] | None = None,
    ):
        self.repo = repo
        self.users_repo = users_repo
        self.usage_resolver = usage_resolver

    async def _add_members(self, account_id: str, group_id: str, user_ids: list[str]):
        """Use the transactional repository API, with a test-double fallback."""
        batch = getattr(self.repo, "add_members_atomic", None)
        if batch is not None:
            return await batch(account_id, group_id, user_ids)
        for user_id in user_ids:
            result = await self.repo.add_member(account_id, group_id, user_id)
            if result.is_err:
                return result
        return Ok(True)

    async def _remove_members(self, account_id: str, group_id: str, user_ids: list[str]):
        """Use the transactional repository API, with a test-double fallback."""
        batch = getattr(self.repo, "remove_members_atomic", None)
        if batch is not None:
            return await batch(account_id, group_id, user_ids)
        for user_id in user_ids:
            result = await self.repo.remove_member(account_id, group_id, user_id)
            if result.is_err:
                return result
        return Ok(True)

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
        for identifier in usernames:
            resolved = await resolve_user_identifier(self.users_repo, account_id, identifier)
            if resolved.is_err:
                return Err(resolved.unwrap_err())
            user_ids.append(resolved.unwrap().user_id)
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
        display_name, normalized_name = SecurityGroup.normalize_name(name)
        if not display_name:
            from xoloapi.errors.base import ValidationError
            return Err(ValidationError("Group name cannot be empty", "name"))
        exists = await self.repo.find_by_name(account_id, display_name)
        if exists.is_err:
            return Err(exists.unwrap_err())
        if exists.unwrap().is_some:
            return Err(AlreadyExistsError("SecurityGroup", name))

        group_id = f"g-{uuid.uuid4().hex}"
        group = SecurityGroup(
            account_id  = account_id,
            group_id    = group_id,
            name        = display_name,
            normalized_name = normalized_name,
            owner_id    = owner_id,
            description = description or None,
        )

        save = await self.repo.save(group)
        if save.is_err:
            return Err(save.unwrap_err())

        return Ok(group_id)

    async def create_group_for_username(
        self, account_id: str, owner_username: str, name: str, description: str = ""
    ) -> Result[str, XoloException]:
        resolved = await self.resolve_usernames(account_id, [owner_username])
        if resolved.is_err:
            return Err(resolved.unwrap_err())
        return await self.create_group(account_id, resolved.unwrap()[0], name, description)

    async def update_group(
        self,
        account_id: str,
        group_id: str,
        caller_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_admin: bool = False,
    ) -> Result[SecurityGroup, XoloException]:
        found = await self.repo.find_by_id(account_id, group_id)
        if found.is_err:
            return Err(found.unwrap_err())
        if found.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        group = found.unwrap().unwrap()
        if not is_admin and not group.is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the group owner or groups.manage may update the group"))
        changes: dict = {}
        if name is not None:
            display_name, normalized = SecurityGroup.normalize_name(name)
            if not display_name:
                from xoloapi.errors.base import ValidationError
                return Err(ValidationError("Group name cannot be empty", "name"))
            duplicate = await self.repo.find_by_name(account_id, display_name)
            if duplicate.is_err:
                return Err(duplicate.unwrap_err())
            if duplicate.unwrap().is_some and duplicate.unwrap().unwrap().group_id != group_id:
                return Err(AlreadyExistsError("SecurityGroup", display_name))
            changes.update(name=display_name, normalized_name=normalized)
        if description is not None:
            changes["description"] = description.strip() or None
        changes["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
        saved = await self.repo.save(group.model_copy(update=changes))
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def set_status(
        self, account_id: str, group_id: str, is_active: bool
    ) -> Result[SecurityGroup, XoloException]:
        found = await self.repo.find_by_id(account_id, group_id)
        if found.is_err:
            return Err(found.unwrap_err())
        if found.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        updated = found.unwrap().unwrap().model_copy(update={
            "is_active": is_active,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        })
        saved = await self.repo.save(updated)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def usage(self, account_id: str, group_id: str) -> Result[dict, XoloException]:
        if self.usage_resolver is None:
            return Ok({"acl_grants": [], "rbac_assignments": []})
        try:
            return Ok(await self.usage_resolver(account_id, group_id))
        except Exception as exc:
            from xoloapi.errors.base import DatabaseError
            return Err(DatabaseError("Failed to inspect group usage", cause=exc))

    async def delete_group(self, account_id: str, caller_id: str, group_id: str) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        group = find.unwrap().unwrap()
        if not group.is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the group owner can delete this group"))
        usage = await self.usage(account_id, group_id)
        if usage.is_err:
            return Err(usage.unwrap_err())
        if usage.unwrap()["acl_grants"] or usage.unwrap()["rbac_assignments"]:
            return Err(ConflictError("Group is still referenced", metadata=usage.unwrap()))
        return await self.repo.delete(account_id, group_id)

    async def delete_group_admin(self, account_id: str, group_id: str) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        usage = await self.usage(account_id, group_id)
        if usage.is_err:
            return Err(usage.unwrap_err())
        if usage.unwrap()["acl_grants"] or usage.unwrap()["rbac_assignments"]:
            return Err(ConflictError("Group is still referenced", metadata=usage.unwrap()))
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

        return await self._add_members(account_id, group_id, user_ids)

    async def add_members_admin(self, account_id: str, group_id: str, user_ids: list[str]) -> Result[bool, XoloException]:
        find = await self.repo.find_by_id(account_id, group_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))

        return await self._add_members(account_id, group_id, user_ids)

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
        return await self._remove_members(account_id, group_id, user_ids)

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

        return await self._remove_members(account_id, group_id, user_ids)

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
        # Ownership and membership are deliberately independent. The legacy
        # keep_previous_as_member argument is ignored by the shared API.
        validated = await self.validate_user_ids(account_id, [new_owner_id])
        if validated.is_err:
            return Err(validated.unwrap_err())
        saved = await self.repo.save(group.model_copy(update={
            "owner_id": new_owner_id,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        }))
        if saved.is_err:
            return Err(saved.unwrap_err())
        return Ok(True)

    async def transfer_owner(
        self,
        account_id: str,
        group_id: str,
        caller_id: str,
        owner_username: str,
        is_admin: bool = False,
    ) -> Result[bool, XoloException]:
        found = await self.repo.find_by_id(account_id, group_id)
        if found.is_err:
            return Err(found.unwrap_err())
        if found.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", group_id))
        if not is_admin and not found.unwrap().unwrap().is_owned_by(caller_id):
            return Err(AccessDeniedError("Only the current owner or groups.manage may transfer ownership"))
        resolved = await self.resolve_usernames(account_id, [owner_username])
        if resolved.is_err:
            return Err(resolved.unwrap_err())
        return await self.transfer_owner_admin(account_id, group_id, resolved.unwrap()[0], True)
