from option import Result, Ok, Err

from xoloapi.acl.domain.aggregates import AccessGrant, ResourcePolicy
from xoloapi.acl.domain.repositories import IResourcePolicyRepository
from xoloapi.groups.domain.aggregates import SecurityGroup
from xoloapi.groups.domain.repositories import ISecurityGroupRepository
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType
from xoloapi.errors.base import AccessDeniedError, ConflictError, NotFoundError, ValidationError, XoloException
from xoloapi.shared.pagination import PageResult
from xoloapi.users.application.user_resolution import resolve_user_identifier


class ACLService:

    def __init__(
        self,
        policy_repo: IResourcePolicyRepository,
        group_repo:  ISecurityGroupRepository,
        users_repo = None,
    ):
        self.policy_repo = policy_repo
        self.group_repo  = group_repo
        self.users_repo  = users_repo

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

    async def resolve_principal(
        self,
        account_id: str,
        principal_type: PrincipalType,
        principal_id: str | None = None,
        principal_username: str | None = None,
        principal_identifier: str | None = None,
    ) -> Result[Principal, XoloException]:
        if principal_type == PrincipalType.USER:
            if self.users_repo is None:
                if principal_id:
                    return Ok(Principal(type=PrincipalType.USER, id=principal_id.strip()))
                return Err(NotFoundError("User", principal_username or principal_id or ""))
            resolved = await resolve_user_identifier(
                self.users_repo, account_id,
                principal_identifier or principal_username or principal_id or "",
            )
            if resolved.is_err:
                return Err(resolved.unwrap_err())
            return Ok(Principal(type=PrincipalType.USER, id=resolved.unwrap().user_id))

        if not principal_id:
            return Err(NotFoundError("SecurityGroup", ""))
        group_result = await self.group_repo.find_by_id(account_id, principal_id.strip())
        if group_result.is_err:
            return Err(group_result.unwrap_err())
        if group_result.unwrap().is_none:
            return Err(NotFoundError("SecurityGroup", principal_id))
        if not group_result.unwrap().unwrap().is_active:
            return Err(ValidationError("Disabled groups cannot own or receive ACL grants"))
        return Ok(Principal(type=PrincipalType.GROUP, id=principal_id.strip()))

    async def create_resource(
        self, account_id: str, resource_id: str, owner_type: PrincipalType, owner_identifier: str
    ) -> Result[ResourcePolicy, XoloException]:
        normalized_resource = resource_id.strip()
        if not normalized_resource:
            return Err(ValidationError("resource_id is required"))
        owner = await self.resolve_principal(
            account_id, owner_type,
            principal_identifier=owner_identifier if owner_type == PrincipalType.USER else None,
            principal_id=owner_identifier if owner_type == PrincipalType.GROUP else None,
        )
        if owner.is_err:
            return Err(owner.unwrap_err())
        claimed = ResourcePolicy(
            account_id=account_id, resource_id=normalized_resource
        ).claim_principal(owner.unwrap())
        if claimed.is_err:
            return Err(claimed.unwrap_err())
        if hasattr(self.policy_repo, "create"):
            return await self.policy_repo.create(claimed.unwrap())
        existing = await self.policy_repo.find_by_resource(account_id, normalized_resource)
        if existing.is_err:
            return Err(existing.unwrap_err())
        if existing.unwrap().is_some:
            return Err(ConflictError("Resource policy already exists"))
        saved = await self.policy_repo.save(claimed.unwrap())
        return Err(saved.unwrap_err()) if saved.is_err else Ok(claimed.unwrap())

    async def revoke_grant(
        self, account_id: str, resource_id: str, grant_id: str, caller_id: str, is_admin: bool = False
    ) -> Result[bool, XoloException]:
        policy_result = await self.get_policy(account_id, resource_id)
        if policy_result.is_err:
            return Err(policy_result.unwrap_err())
        policy = policy_result.unwrap()
        grant = next((item for item in policy.grants if item.grant_id == grant_id), None)
        if grant is None:
            return Err(NotFoundError("AccessGrant", grant_id))
        if grant.is_owner:
            return Err(ConflictError("The protected owner grant cannot be revoked"))
        if is_admin:
            caller_ids = self._admin_principal_ids(policy)
        else:
            caller_result = await self._principal_ids(account_id, caller_id)
            if caller_result.is_err:
                return Err(caller_result.unwrap_err())
            caller_ids = caller_result.unwrap()
        updated = policy.revoke(grant.principal.id, set(grant.permissions), caller_id, caller_ids)
        if updated.is_err:
            return Err(updated.unwrap_err())
        saved = await self.policy_repo.save(updated.unwrap())
        return Err(saved.unwrap_err()) if saved.is_err else Ok(True)

    async def update_grant_permissions(
        self,
        account_id: str,
        resource_id: str,
        grant_id: str,
        permissions: list[str],
        caller_id: str,
        is_admin: bool = False,
    ) -> Result[AccessGrant, XoloException]:
        policy_result = await self.get_policy(account_id, resource_id)
        if policy_result.is_err:
            return Err(policy_result.unwrap_err())
        policy = policy_result.unwrap()
        if is_admin:
            caller_ids = self._admin_principal_ids(policy)
        else:
            caller_result = await self._principal_ids(account_id, caller_id)
            if caller_result.is_err:
                return Err(caller_result.unwrap_err())
            caller_ids = caller_result.unwrap()

        updated = policy.update_grant_permissions(
            grant_id,
            {Permission(permission) for permission in permissions},
            caller_ids,
        )
        if updated.is_err:
            return Err(updated.unwrap_err())
        saved = await self.policy_repo.save(updated.unwrap())
        if saved.is_err:
            return Err(saved.unwrap_err())
        return Ok(next(grant for grant in updated.unwrap().grants if grant.grant_id == grant_id))

    async def principal_name(self, account_id: str, principal: Principal) -> str:
        if principal.type == PrincipalType.USER and self.users_repo is not None:
            maybe_user = await self.users_repo.find_by_id(principal.id, account_id=account_id)
            if maybe_user.is_some:
                return maybe_user.unwrap().username
        if principal.type == PrincipalType.GROUP:
            group_result = await self.group_repo.find_by_id(account_id, principal.id)
            if group_result.is_ok and group_result.unwrap().is_some:
                return group_result.unwrap().unwrap().name
        return principal.id

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

    async def claim_resource_for_principal(
        self,
        account_id: str,
        principal_id: str,
        principal_type: PrincipalType,
        resource_id: str,
    ) -> Result[bool, XoloException]:
        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        policy = find.unwrap().unwrap_or(ResourcePolicy(account_id=account_id, resource_id=resource_id))
        claimed = policy.claim_principal(Principal(type=principal_type, id=principal_id))
        if claimed.is_err:
            return Err(claimed.unwrap_err())
        saved = await self.policy_repo.save(claimed.unwrap())
        return Err(saved.unwrap_err()) if saved.is_err else Ok(True)

    # ── Grant ─────────────────────────────────────────────────────────────────

    async def grant(
        self,
        account_id:     str,
        caller_id:      str,
        resource_id:    str,
        principal_id:   str | None,
        principal_type: PrincipalType,
        permissions:    list[str],
        principal_username: str | None = None,
        principal_identifier: str | None = None,
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
        principal_result = await self.resolve_principal(
            account_id, principal_type, principal_id, principal_username, principal_identifier
        )
        if principal_result.is_err:
            return Err(principal_result.unwrap_err())
        principal = principal_result.unwrap()

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
        principal_id: str | None,
        permissions:  list[str],
        principal_type: PrincipalType = PrincipalType.USER,
        principal_username: str | None = None,
        principal_identifier: str | None = None,
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

        principal_result = await self.resolve_principal(
            account_id, principal_type, principal_id, principal_username, principal_identifier
        )
        if principal_result.is_err:
            # Revocation is also the cleanup path for legacy/dangling grants.
            # A concrete stored ID can therefore be removed even when its user
            # or group no longer exists. New grants are always validated.
            if not principal_id:
                return Err(principal_result.unwrap_err())
            resolved_id = principal_id.strip()
        else:
            resolved_id = principal_result.unwrap().id
        updated = policy.revoke(resolved_id, perms, caller_id, caller_principal_ids)
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
        principal_type: PrincipalType = PrincipalType.USER,
    ) -> Result[bool, XoloException]:
        if principal_type == PrincipalType.GROUP:
            principal_ids = [user_id]
        else:
            pids_result = await self._principal_ids(account_id, user_id)
            if pids_result.is_err:
                return Err(pids_result.unwrap_err())
            principal_ids = pids_result.unwrap()

        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Ok(False)

        policy = find.unwrap().unwrap()
        required = {Permission(p) for p in permissions}

        return Ok(policy.check(principal_ids, required))

    async def effective_access(
        self, account_id: str, user_id: str, resource_id: str
    ) -> Result[tuple[set[Permission], bool, list[str]], XoloException]:
        groups_result = await self._group_ids(account_id, user_id)
        if groups_result.is_err:
            return Err(groups_result.unwrap_err())
        group_ids = groups_result.unwrap()
        principal_ids = [user_id] + group_ids

        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Ok((set(), False, group_ids))

        policy = find.unwrap().unwrap()
        return Ok((
            policy.effective_permissions(principal_ids),
            policy.is_owned_by_any(principal_ids),
            group_ids,
        ))

    async def get_policy(self, account_id: str, resource_id: str) -> Result[ResourcePolicy, XoloException]:
        find = await self.policy_repo.find_by_resource(account_id, resource_id)
        if find.is_err:
            return Err(find.unwrap_err())
        if find.unwrap().is_none:
            return Err(NotFoundError("ResourcePolicy", resource_id))
        return Ok(find.unwrap().unwrap())

    async def get_policy_for_caller(
        self,
        account_id: str,
        resource_id: str,
        caller_id: str,
        is_admin: bool = False,
    ) -> Result[ResourcePolicy, XoloException]:
        policy_result = await self.get_policy(account_id, resource_id)
        if policy_result.is_err:
            return policy_result
        policy = policy_result.unwrap()
        if is_admin:
            return Ok(policy)
        caller_pids = await self._principal_ids(account_id, caller_id)
        if caller_pids.is_err:
            return Err(caller_pids.unwrap_err())
        if Permission.MANAGE not in policy.effective_permissions(caller_pids.unwrap()):
            return Err(AccessDeniedError("You do not have permission to inspect this resource policy"))
        return Ok(policy)

    async def transfer_owner(
        self,
        account_id: str,
        resource_id: str,
        principal_id: str,
        principal_type: PrincipalType,
        keep_previous_permissions: list[str] | None = None,
    ) -> Result[bool, XoloException]:
        policy_result = await self.get_policy(account_id, resource_id)
        if policy_result.is_err:
            return Err(policy_result.unwrap_err())
        keep = None if keep_previous_permissions is None else {Permission(p) for p in keep_previous_permissions}
        updated = policy_result.unwrap().transfer_owner(
            Principal(type=principal_type, id=principal_id),
            keep_previous_permissions=keep,
        )
        if updated.is_err:
            return Err(updated.unwrap_err())
        saved = await self.policy_repo.save(updated.unwrap())
        return Err(saved.unwrap_err()) if saved.is_err else Ok(True)

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
