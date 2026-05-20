from option import Result, Ok, Err

from xoloapi.acl.domain.aggregates import ResourcePolicy
from xoloapi.acl.domain.repositories import IResourcePolicyRepository
from xoloapi.groups.domain.aggregates import SecurityGroup
from xoloapi.groups.domain.repositories import ISecurityGroupRepository
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType
from xoloapi.errors.base import AccessDeniedError, NotFoundError, XoloException
from xoloapi.shared.pagination import PageResult


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
        r = await self.group_repo.find_groups_for_user(account_id, user_id)
        if r.is_err:
            return r
        return Ok([g.group_id for g in r.unwrap()])

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
        pids_result = await self._principal_ids(account_id, user_id)
        if pids_result.is_err:
            return Err(pids_result.unwrap_err())

        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Ok(False)

        policy = find.unwrap().unwrap()
        required = {Permission(p) for p in permissions}

        pids = pids_result.unwrap()
        return Ok(policy.check(pids, required))

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

    async def get_user_groups(self, account_id: str, user_id: str) -> Result[list[SecurityGroup], XoloException]:
        return await self.group_repo.find_groups_for_user(account_id, user_id)

    async def get_owned_resources_page(
        self,
        account_id: str,
        user_id:    str,
        page:       int = 1,
        size:       int = 10,
    ) -> Result[PageResult[ResourcePolicy], XoloException]:
        result = await self.policy_repo.find_owned_by(account_id, user_id, page, size)
        if result.is_err:
            return result
        policies, total = result.unwrap()
        return Ok(PageResult(items=policies, total=total, page=page, size=size))

    async def get_shared_resources_page(
        self,
        account_id:   str,
        principal_ids: list[str],
        exclude_ids:   list[str],
        page:          int = 1,
        size:          int = 10,
    ) -> Result[PageResult[ResourcePolicy], XoloException]:
        result = await self.policy_repo.find_shared_with(account_id, principal_ids, exclude_ids, page, size)
        if result.is_err:
            return result
        policies, total = result.unwrap()
        return Ok(PageResult(items=policies, total=total, page=page, size=size))

    async def list_resources(self, account_id: str) -> Result[list[dict], XoloException]:
        """List all resources in an account for data discovery."""
        result = await self.policy_repo.list_all(account_id)
        if result.is_err:
            return Err(result.unwrap_err())
        policies = result.unwrap()
        return Ok([{"id": p.resource_id, "name": p.resource_id} for p in policies])
