import math
from option import Result, Ok, Err

from xoloapi.acl.domain.aggregates import ResourcePolicy
from xoloapi.acl.domain.repositories import IResourcePolicyRepository, ISecurityGroupRepository
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType
from xoloapi.acl.dto import (
    GroupDetailDTO,
    PaginatedDTO,
    ResourceDetailDTO,
    UserResourcesDTO,
)
from xoloapi.errors.base import AccessDeniedError, NotFoundError, XoloException


class ACLService:

    def __init__(
        self,
        policy_repo: IResourcePolicyRepository,
        group_repo:  ISecurityGroupRepository,
    ):
        self.policy_repo = policy_repo
        self.group_repo  = group_repo

    # ── Resolve caller context ────────────────────────────────────────────────

    async def _group_ids(self, account_id: str, user_id: str) -> Result[list[str], XoloException]:
        return await self.group_repo.find_group_ids_for_user(account_id, user_id)

    async def _principal_ids(self, account_id: str, user_id: str) -> Result[list[str], XoloException]:
        r = await self._group_ids(account_id, user_id)
        if r.is_err:
            return r
        return Ok([user_id] + r.unwrap())

    @staticmethod
    def _admin_principal_ids(policy: ResourcePolicy) -> list[str]:
        return [grant.principal.id for grant in policy.grants if grant.is_owner]

    # ── Claim ─────────────────────────────────────────────────────────────────

    async def claim_resource(self, account_id: str, user_id: str, resource_id: str) -> Result[bool, XoloException]:
        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())

        policy = find.unwrap().unwrap_or(ResourcePolicy(account_id=account_id, resource_id=resource_id))

        claimed = policy.claim(user_id)
        if claimed.is_err:
            return Err(claimed.unwrap_err())

        save = await self.policy_repo.save(claimed.unwrap())
        if save.is_err:
            return Err(save.unwrap_err())
        return Ok(True)

    # ── Grant ─────────────────────────────────────────────────────────────────

    async def grant(
        self,
        account_id:     str,
        caller_id:      str,
        resource_id:    str,
        principal_id:   str,
        principal_type: PrincipalType,
        permissions:    list[str],
        is_admin:       bool = False,
    ) -> Result[bool, XoloException]:
        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("ResourcePolicy", resource_id))

        policy = find.unwrap().unwrap()
        if is_admin:
            caller_principal_ids = self._admin_principal_ids(policy)
        else:
            caller_pids = await self._principal_ids(account_id, caller_id)
            if caller_pids.is_err:
                return Err(caller_pids.unwrap_err())
            caller_principal_ids = caller_pids.unwrap()
        perms  = {Permission(p) for p in permissions}
        principal = Principal(type=principal_type, id=principal_id)

        updated = policy.grant(principal, perms, caller_principal_ids)
        if updated.is_err:
            return Err(updated.unwrap_err())

        save = await self.policy_repo.save(updated.unwrap())
        if save.is_err:
            return Err(save.unwrap_err())
        return Ok(True)

    # ── Revoke ────────────────────────────────────────────────────────────────

    async def revoke(
        self,
        account_id:   str,
        caller_id:    str,
        resource_id:  str,
        principal_id: str,
        permissions:  list[str],
        is_admin:     bool = False,
    ) -> Result[bool, XoloException]:
        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("ResourcePolicy", resource_id))

        policy = find.unwrap().unwrap()
        if is_admin:
            caller_principal_ids = self._admin_principal_ids(policy)
        else:
            caller_pids = await self._principal_ids(account_id, caller_id)
            if caller_pids.is_err:
                return Err(caller_pids.unwrap_err())
            caller_principal_ids = caller_pids.unwrap()
        perms  = {Permission(p) for p in permissions}

        updated = policy.revoke(principal_id, perms, caller_id, caller_principal_ids)
        if updated.is_err:
            return Err(updated.unwrap_err())

        save = await self.policy_repo.save(updated.unwrap())
        if save.is_err:
            return Err(save.unwrap_err())
        return Ok(True)

    # ── Check ─────────────────────────────────────────────────────────────────

    async def check(
        self,
        account_id:   str,
        user_id:      str,
        resource_id:  str,
        permissions:  list[str],
    ) -> Result[bool, XoloException]:
        pids = await self._principal_ids(account_id, user_id)
        if pids.is_err:
            return Err(pids.unwrap_err())

        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Ok(False)

        policy = find.unwrap().unwrap()
        required = {Permission(p) for p in permissions}
        return Ok(policy.check(pids.unwrap(), required))

    async def list_policies(self, account_id: str) -> Result[list[ResourcePolicy], XoloException]:
        return await self.policy_repo.list_all(account_id)

    async def delete_resource(
        self,
        account_id: str,
        resource_id: str,
        caller_id: str = "",
        is_admin: bool = False,
    ) -> Result[bool, XoloException]:
        if is_admin:
            return await self.policy_repo.delete(account_id, resource_id)

        caller_pids = await self._principal_ids(account_id, caller_id)
        if caller_pids.is_err:
            return Err(caller_pids.unwrap_err())

        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("ResourcePolicy", resource_id))

        policy = find.unwrap().unwrap()
        if Permission.MANAGE not in policy.effective_permissions(caller_pids.unwrap()):
            return Err(AccessDeniedError("You do not have permission to delete this resource policy"))
        return await self.policy_repo.delete(account_id, resource_id)

    # ── Dashboard view ────────────────────────────────────────────────────────

    async def get_user_resources(
        self,
        account_id:       str,
        user_id:          str,
        owned_page:       int = 1,
        owned_page_size:  int = 10,
        shared_page:      int = 1,
        shared_page_size: int = 10,
    ) -> Result[UserResourcesDTO, XoloException]:

        # ── Groups ──
        groups_result = await self.group_repo.find_groups_for_user(account_id, user_id)
        if groups_result.is_err:
            return Err(groups_result.unwrap_err())

        group_ids_result = await self._group_ids(account_id, user_id)
        if group_ids_result.is_err:
            return Err(group_ids_result.unwrap_err())

        all_groups  = groups_result.unwrap()
        group_ids   = group_ids_result.unwrap()
        group_id_to_name = {g.group_id: g.name for g in all_groups}

        group_dtos = [
            GroupDetailDTO(
                id      = g.group_id,
                name    = g.name,
                my_role = "owner" if g.is_owned_by(user_id) else "member",
            )
            for g in all_groups
        ]

        # ── Owned ──
        owned_result = await self.policy_repo.find_owned_by(account_id, user_id, owned_page, owned_page_size)
        if owned_result.is_err:
            return Err(owned_result.unwrap_err())

        owned_policies, owned_total = owned_result.unwrap()
        owned_resource_ids = [p.resource_id for p in owned_policies]
        owned_items = [
            ResourceDetailDTO(
                resource_id   = p.resource_id,
                permissions   = {perm.value for perm in p.effective_permissions([user_id])},
                access_source = "Owner",
            )
            for p in owned_policies
        ]
        owned_pages = math.ceil(owned_total / owned_page_size) if owned_page_size > 0 else 0

        # ── Shared ──
        all_pids = [user_id] + group_ids
        shared_result = await self.policy_repo.find_shared_with(
            account_id, all_pids, owned_resource_ids, shared_page, shared_page_size
        )
        if shared_result.is_err:
            return Err(shared_result.unwrap_err())

        shared_policies, shared_total = shared_result.unwrap()
        shared_items: list[ResourceDetailDTO] = []
        for p in shared_policies:
            source = "Direct"
            for g in p.grants:
                if g.principal.id in group_ids:
                    source = f"Group: {group_id_to_name.get(g.principal.id, g.principal.id)}"
                    break
            shared_items.append(ResourceDetailDTO(
                resource_id   = p.resource_id,
                permissions   = {perm.value for perm in p.effective_permissions(all_pids)},
                access_source = source,
            ))
        shared_pages = math.ceil(shared_total / shared_page_size) if shared_page_size > 0 else 0

        return Ok(UserResourcesDTO(
            user_id          = user_id,
            groups           = group_dtos,
            owned_resources  = PaginatedDTO[ResourceDetailDTO](
                items       = owned_items,
                total_count = owned_total,
                page        = owned_page,
                page_size   = owned_page_size,
                total_pages = owned_pages,
            ),
            shared_resources = PaginatedDTO[ResourceDetailDTO](
                items       = shared_items,
                total_count = shared_total,
                page        = shared_page,
                page_size   = shared_page_size,
                total_pages = shared_pages,
            ),
        ))
