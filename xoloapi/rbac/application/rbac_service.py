from option import Result, Ok, Err

from xoloapi.errors.base import XoloException, NotFoundError, ConflictError, ValidationError
from xoloapi.rbac.domain.aggregates import Role, RoleAssignment
from xoloapi.rbac.domain.repositories import IRoleRepository, IRoleAssignmentRepository
from xoloapi.rbac.domain.services import RBACDomainService


class RBACService:

    def __init__(
        self,
        role_repo:       IRoleRepository,
        assignment_repo: IRoleAssignmentRepository,
    ) -> None:
        self._roles       = role_repo
        self._assignments = assignment_repo
        self._domain      = RBACDomainService()

    # ── Roles ─────────────────────────────────────────────────────────────────

    async def create_role(
        self,
        account_id:  str,
        name:        str,
        description: str | None = None,
        permissions: list[str]  | None = None,
    ) -> Result[Role, XoloException]:
        existing = await self._roles.find_by_name(account_id, name)
        if existing.is_err:
            return existing
        if existing.unwrap().is_some:
            return Err(ConflictError(f"Role '{name}' already exists"))

        role = Role.new(account_id=account_id, name=name, description=description, permissions=permissions)
        saved = await self._roles.save(role)
        if saved.is_err:
            return saved
        return Ok(role)

    async def get_role(self, account_id: str, role_id: str) -> Result[Role, XoloException]:
        result = await self._roles.find_by_id(account_id, role_id)
        if result.is_err:
            return result
        opt = result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("Role", role_id))
        return Ok(opt.unwrap())

    async def list_roles(self, account_id: str) -> Result[list[Role], XoloException]:
        return await self._roles.find_all(account_id)

    async def update_role(
        self,
        account_id:  str,
        role_id:     str,
        name:        str | None = None,
        description: str | None = None,
    ) -> Result[Role, XoloException]:
        role_result = await self.get_role(account_id, role_id)
        if role_result.is_err:
            return role_result
        role = role_result.unwrap()

        updates: dict = {}
        if name and name != role.name:
            existing = await self._roles.find_by_name(account_id, name)
            if existing.is_err:
                return existing
            if existing.unwrap().is_some:
                return Err(ConflictError(f"Role '{name}' already exists"))
            updates["name"] = name
        if description is not None:
            updates["description"] = description

        if not updates:
            return Ok(role)

        import datetime
        updates["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
        updated = role.model_copy(update=updates)
        saved   = await self._roles.save(updated)
        if saved.is_err:
            return saved
        return Ok(updated)

    async def delete_role(self, account_id: str, role_id: str) -> Result[None, XoloException]:
        role_result = await self.get_role(account_id, role_id)
        if role_result.is_err:
            return role_result

        # Remove all assignments for this role first
        cleanup = await self._assignments.delete_by_role(account_id, role_id)
        if cleanup.is_err:
            return cleanup

        return await self._roles.delete(account_id, role_id)

    async def add_permission(self, account_id: str, role_id: str, permission: str) -> Result[Role, XoloException]:
        role_result = await self.get_role(account_id, role_id)
        if role_result.is_err:
            return role_result
        try:
            from xoloapi.rbac.domain.value_objects import RBACPermission
            RBACPermission.from_string(permission)
        except ValueError as e:
            return Err(ValidationError(str(e)))

        updated = role_result.unwrap().add_permission(permission)
        saved   = await self._roles.save(updated)
        if saved.is_err:
            return saved
        return Ok(updated)

    async def remove_permission(self, account_id: str, role_id: str, permission: str) -> Result[Role, XoloException]:
        role_result = await self.get_role(account_id, role_id)
        if role_result.is_err:
            return role_result

        updated = role_result.unwrap().remove_permission(permission)
        saved   = await self._roles.save(updated)
        if saved.is_err:
            return saved
        return Ok(updated)

    async def add_parent(self, account_id: str, role_id: str, parent_role_id: str) -> Result[Role, XoloException]:
        if role_id == parent_role_id:
            return Err(ValidationError("A role cannot be its own parent"))

        role_result = await self.get_role(account_id, role_id)
        if role_result.is_err:
            return role_result
        role = role_result.unwrap()

        if parent_role_id in role.parent_role_ids:
            return Ok(role)

        # Load all roles for cycle detection
        all_result = await self._roles.find_all(account_id)
        if all_result.is_err:
            return all_result
        all_roles = {r.role_id: r for r in all_result.unwrap()}

        if self._domain.would_create_cycle(role_id, parent_role_id, all_roles):
            return Err(ConflictError("Adding this parent would create a role hierarchy cycle"))

        updated = role.model_copy(update={"parent_role_ids": role.parent_role_ids + [parent_role_id]})
        saved   = await self._roles.save(updated)
        if saved.is_err:
            return saved
        return Ok(updated)

    async def remove_parent(self, account_id: str, role_id: str, parent_role_id: str) -> Result[Role, XoloException]:
        role_result = await self.get_role(account_id, role_id)
        if role_result.is_err:
            return role_result
        role    = role_result.unwrap()
        updated = role.model_copy(update={
            "parent_role_ids": [p for p in role.parent_role_ids if p != parent_role_id]
        })
        saved = await self._roles.save(updated)
        if saved.is_err:
            return saved
        return Ok(updated)

    # ── Assignments ───────────────────────────────────────────────────────────

    async def assign_role(self, account_id: str, subject_id: str, role_id: str) -> Result[RoleAssignment, XoloException]:
        role_check = await self.get_role(account_id, role_id)
        if role_check.is_err:
            return role_check

        existing = await self._assignments.find_assignment(account_id, subject_id, role_id)
        if existing.is_err:
            return existing
        if existing.unwrap().is_some:
            return Ok(existing.unwrap().unwrap())   # idempotent

        assignment = RoleAssignment.new(account_id=account_id, subject_id=subject_id, role_id=role_id)
        saved      = await self._assignments.save(assignment)
        if saved.is_err:
            return saved
        return Ok(assignment)

    async def unassign_role(self, account_id: str, subject_id: str, role_id: str) -> Result[None, XoloException]:
        existing = await self._assignments.find_assignment(account_id, subject_id, role_id)
        if existing.is_err:
            return existing
        opt = existing.unwrap()
        if opt.is_none:
            return Ok(None)
        return await self._assignments.delete(account_id, opt.unwrap().assignment_id)

    async def get_subject_roles(self, account_id: str, subject_id: str) -> Result[list[Role], XoloException]:
        assignments = await self._assignments.find_by_subject(account_id, subject_id)
        if assignments.is_err:
            return assignments

        role_ids = [a.role_id for a in assignments.unwrap()]
        if not role_ids:
            return Ok([])
        return await self._roles.find_many(account_id, role_ids)

    async def list_assignments(self, account_id: str) -> Result[list[RoleAssignment], XoloException]:
        return await self._assignments.find_all(account_id)

    # ── Check ─────────────────────────────────────────────────────────────────

    async def check(self, account_id: str, subject_id: str, required_permission: str) -> Result[bool, XoloException]:
        roles_result = await self.get_subject_roles(account_id, subject_id)
        if roles_result.is_err:
            return roles_result

        all_result = await self._roles.find_all(account_id)
        if all_result.is_err:
            return all_result

        all_roles   = {r.role_id: r for r in all_result.unwrap()}
        effective   = self._domain.resolve_effective_permissions(roles_result.unwrap(), all_roles)
        has_access  = self._domain.check(effective, required_permission)
        return Ok(has_access)

    async def get_effective_permissions(self, account_id: str, subject_id: str) -> Result[list[str], XoloException]:
        roles_result = await self.get_subject_roles(account_id, subject_id)
        if roles_result.is_err:
            return roles_result

        all_result = await self._roles.find_all(account_id)
        if all_result.is_err:
            return all_result

        all_roles  = {r.role_id: r for r in all_result.unwrap()}
        effective  = self._domain.resolve_effective_permissions(roles_result.unwrap(), all_roles)
        return Ok(sorted(effective))

    async def list_roles_discovery(self, account_id: str) -> Result[list[dict], XoloException]:
        """List all roles for data discovery."""
        result = await self._roles.find_all(account_id)
        if result.is_err:
            return result
        roles = result.unwrap()
        return Ok([{"id": r.role_id, "name": r.name} for r in roles])
