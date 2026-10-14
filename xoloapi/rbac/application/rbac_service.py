import datetime

from option import Result, Ok, Err

from xoloapi.groups.domain.repositories import ISecurityGroupRepository
from xoloapi.errors.base import XoloException, NotFoundError, ConflictError, ValidationError
from xoloapi.rbac.domain.aggregates import Role, RoleAssignment
from xoloapi.rbac.domain.repositories import IRoleRepository, IRoleAssignmentRepository
from xoloapi.rbac.domain.services import RBACDomainService
from xoloapi.users.application.user_resolution import resolve_user_identifier


class RBACService:

    def __init__(
        self,
        role_repo:       IRoleRepository,
        assignment_repo: IRoleAssignmentRepository,
        group_repo:      ISecurityGroupRepository,
        users_repo = None,
        catalog_repo = None,
    ) -> None:
        self._roles       = role_repo
        self._assignments = assignment_repo
        self._groups      = group_repo
        self._users       = users_repo
        self._catalog     = catalog_repo
        self._domain      = RBACDomainService()

    # ── Roles ─────────────────────────────────────────────────────────────────

    async def create_role(
        self,
        account_id:  str,
        name:        str,
        description: str | None = None,
        permissions: list[str]  | None = None,
    ) -> Result[Role, XoloException]:
        permissions = permissions or []
        for permission in permissions:
            try:
                from xoloapi.rbac.domain.value_objects import RBACPermission
                RBACPermission.from_string(permission)
            except ValueError as exc:
                return Err(ValidationError(str(exc)))
        existing = await self._roles.find_by_name(account_id, name)
        if existing.is_err:
            return existing
        if existing.unwrap().is_some:
            return Err(ConflictError(f"Role '{name}' already exists"))

        role = Role.new(account_id=account_id, name=name, description=description, permissions=permissions)
        saved = await self._roles.save(role)
        if saved.is_err:
            return saved
        if self._catalog is not None:
            await self._catalog.register(account_id, permissions)
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
        description_set: bool = False,
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
        if description_set or description is not None:
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

        all_roles = await self._roles.find_all(account_id)
        if all_roles.is_err:
            return Err(all_roles.unwrap_err())
        for role in all_roles.unwrap():
            if role_id in role.parent_role_ids:
                saved = await self._roles.save(role.model_copy(update={
                    "parent_role_ids": [parent for parent in role.parent_role_ids if parent != role_id]
                }))
                if saved.is_err:
                    return saved
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
        if self._catalog is not None:
            await self._catalog.register(account_id, [permission])
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

        parent_result = await self.get_role(account_id, parent_role_id)
        if parent_result.is_err:
            return Err(parent_result.unwrap_err())

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

    async def assign_role(
        self,
        account_id: str,
        subject_id: str | None,
        role_id: str,
        subject_type: str = "USER",
        subject_username: str | None = None,
        user_identifier: str | None = None,
    ) -> Result[RoleAssignment, XoloException]:
        role_check = await self.get_role(account_id, role_id)
        if role_check.is_err:
            return role_check

        subject_type = subject_type.upper()
        if subject_type not in {"USER", "GROUP"}:
            return Err(ValidationError("subject_type must be USER or GROUP"))
        if subject_type == "USER" and self._users is not None:
            identifier = user_identifier or subject_username or subject_id
            resolved = await resolve_user_identifier(self._users, account_id, identifier or "")
            if resolved.is_err:
                return Err(resolved.unwrap_err())
            subject_id = resolved.unwrap().user_id
        elif subject_type == "GROUP":
            if not subject_id:
                return Err(ValidationError("subject_id is required for GROUP assignments"))
            group = await self._groups.find_by_id(account_id, subject_id)
            if group.is_err:
                return Err(group.unwrap_err())
            if group.unwrap().is_none:
                return Err(NotFoundError("SecurityGroup", subject_id))
            if not group.unwrap().unwrap().is_active:
                return Err(ValidationError("Disabled groups cannot receive RBAC assignments"))
        if not subject_id:
            return Err(ValidationError("subject_id is required"))

        existing = await self._assignments.find_assignment(account_id, subject_id, role_id, subject_type)
        if existing.is_err:
            return existing
        if existing.unwrap().is_some:
            return Err(ConflictError("Role assignment already exists"))

        assignment = RoleAssignment.new(account_id=account_id, subject_id=subject_id, role_id=role_id, subject_type=subject_type)
        saved      = await self._assignments.save(assignment)
        if saved.is_err:
            return saved
        return Ok(assignment)

    async def unassign_role(self, account_id: str, subject_id: str, role_id: str, subject_type: str | None = None) -> Result[None, XoloException]:
        existing = await self._assignments.find_assignment(account_id, subject_id, role_id, subject_type)
        if existing.is_err:
            return existing
        opt = existing.unwrap()
        if opt.is_none:
            return Ok(None)
        return await self._assignments.delete(account_id, opt.unwrap().assignment_id)

    async def get_subject_roles(self, account_id: str, subject_id: str) -> Result[list[Role], XoloException]:
        direct = await self._assignments.find_by_subject(account_id, subject_id, "USER")
        if direct.is_err:
            return direct

        role_ids: set[str] = {a.role_id for a in direct.unwrap()}

        group_ids_result = await self._groups.find_group_ids_for_user(account_id, subject_id)
        if group_ids_result.is_err:
            return group_ids_result

        for gid in group_ids_result.unwrap():
            group_assignments = await self._assignments.find_by_subject(account_id, gid, "GROUP")
            if group_assignments.is_err:
                return group_assignments
            role_ids.update(a.role_id for a in group_assignments.unwrap())

        if not role_ids:
            return Ok([])
        return await self._roles.find_many(account_id, list(role_ids))

    async def has_role(self, account_id: str, subject_id: str, role_id: str) -> Result[bool, XoloException]:
        explained = await self.has_role_explained(account_id, subject_id, role_id)
        return Err(explained.unwrap_err()) if explained.is_err else Ok(explained.unwrap()[0])

    async def has_role_explained(self, account_id: str, subject_id: str, role_id: str) -> Result[tuple[bool, list[str]], XoloException]:
        roots = await self.get_subject_roles(account_id, subject_id)
        if roots.is_err:
            return Err(roots.unwrap_err())
        all_result = await self._roles.find_all(account_id)
        if all_result.is_err:
            return Err(all_result.unwrap_err())
        roles = {role.role_id: role for role in all_result.unwrap()}
        def find(current: str, target: str, path: list[str]) -> list[str] | None:
            if current == target:
                return path + [current]
            role = roles.get(current)
            if role is None:
                return None
            for parent in role.parent_role_ids:
                found = find(parent, target, path + [current])
                if found:
                    return found
            return None
        for root in roots.unwrap():
            path = find(root.role_id, role_id, [])
            if path:
                return Ok((True, path))
        return Ok((False, []))

    async def list_assignments(self, account_id: str) -> Result[list[RoleAssignment], XoloException]:
        return await self._assignments.find_all(account_id)

    async def resolve_user(self, account_id: str, user_identifier: str):
        if self._users is None:
            return Err(ValidationError("User resolution is unavailable"))
        return await resolve_user_identifier(self._users, account_id, user_identifier)

    async def update_assignment(
        self,
        account_id: str,
        assignment_id: str,
        role_id: str,
        subject_type: str,
        user_identifier: str | None = None,
        subject_id: str | None = None,
    ) -> Result[RoleAssignment, XoloException]:
        current = await self._assignments.find_by_id(account_id, assignment_id)
        if current.is_err:
            return Err(current.unwrap_err())
        if current.unwrap().is_none:
            return Err(NotFoundError("RoleAssignment", assignment_id))
        if (await self.get_role(account_id, role_id)).is_err:
            return Err(NotFoundError("Role", role_id))

        normalized_type = subject_type.upper()
        if normalized_type == "USER":
            resolved = await self.resolve_user(account_id, user_identifier or subject_id or "")
            if resolved.is_err:
                return Err(resolved.unwrap_err())
            canonical_subject_id = resolved.unwrap().user_id
        elif normalized_type == "GROUP":
            if not subject_id:
                return Err(ValidationError("subject_id is required for GROUP assignments"))
            group = await self._groups.find_by_id(account_id, subject_id)
            if group.is_err:
                return Err(group.unwrap_err())
            if group.unwrap().is_none:
                return Err(NotFoundError("SecurityGroup", subject_id))
            if not group.unwrap().unwrap().is_active:
                return Err(ValidationError("Disabled groups cannot receive RBAC assignments"))
            canonical_subject_id = subject_id
        else:
            return Err(ValidationError("subject_type must be USER or GROUP"))

        duplicate = await self._assignments.find_assignment(
            account_id, canonical_subject_id, role_id, normalized_type
        )
        if duplicate.is_err:
            return Err(duplicate.unwrap_err())
        if duplicate.unwrap().is_some and duplicate.unwrap().unwrap().assignment_id != assignment_id:
            return Err(ConflictError("Role assignment already exists"))

        updated = current.unwrap().unwrap().model_copy(update={
            "subject_id": canonical_subject_id,
            "subject_type": normalized_type,
            "role_id": role_id,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        })
        saved = await self._assignments.save(updated)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(updated)

    async def delete_assignment(self, account_id: str, assignment_id: str) -> Result[None, XoloException]:
        return await self._assignments.delete(account_id, assignment_id)

    async def list_permission_catalog(self, account_id: str) -> Result[list[str], XoloException]:
        if self._catalog is None:
            roles = await self._roles.find_all(account_id)
            if roles.is_err:
                return Err(roles.unwrap_err())
            return Ok(sorted({permission for role in roles.unwrap() for permission in role.permissions}))
        return Ok(await self._catalog.list(account_id))

    # ── Check ─────────────────────────────────────────────────────────────────

    async def check(self, account_id: str, subject_id: str, required_permission: str) -> Result[bool, XoloException]:
        explained = await self.check_explained(account_id, subject_id, required_permission)
        return Err(explained.unwrap_err()) if explained.is_err else Ok(explained.unwrap()[0])

    async def check_explained(self, account_id: str, subject_id: str, required_permission: str) -> Result[tuple[bool, str | None], XoloException]:
        try:
            from xoloapi.rbac.domain.value_objects import RBACPermission
            required = RBACPermission.from_string(required_permission)
        except ValueError as exc:
            return Err(ValidationError(str(exc)))
        roles_result = await self.get_subject_roles(account_id, subject_id)
        if roles_result.is_err:
            return roles_result

        all_result = await self._roles.find_all(account_id)
        if all_result.is_err:
            return all_result

        all_roles   = {r.role_id: r for r in all_result.unwrap()}
        effective   = self._domain.resolve_effective_permissions(roles_result.unwrap(), all_roles)
        matches = sorted(permission for permission in effective if RBACPermission.from_string(permission).matches(required))
        return Ok((bool(matches), matches[0] if matches else None))

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

    async def get_effective_permissions_explained(self, account_id: str, subject_id: str) -> Result[dict, XoloException]:
        direct_result = await self._assignments.find_by_subject(account_id, subject_id, "USER")
        if direct_result.is_err:
            return Err(direct_result.unwrap_err())
        direct_ids = [assignment.role_id for assignment in direct_result.unwrap()]
        group_roles: dict[str, list[str]] = {}
        groups = await self._groups.find_group_ids_for_user(account_id, subject_id)
        if groups.is_err:
            return Err(groups.unwrap_err())
        for group_id in groups.unwrap():
            assignments = await self._assignments.find_by_subject(account_id, group_id, "GROUP")
            if assignments.is_err:
                return Err(assignments.unwrap_err())
            if assignments.unwrap():
                group_roles[group_id] = [assignment.role_id for assignment in assignments.unwrap()]
        all_result = await self._roles.find_all(account_id)
        if all_result.is_err:
            return Err(all_result.unwrap_err())
        role_map = {role.role_id: role for role in all_result.unwrap()}
        root_ids = list(dict.fromkeys(direct_ids + [role for roles in group_roles.values() for role in roles]))
        inherited_ids: set[str] = set()
        def parents(role_id: str):
            role = role_map.get(role_id)
            if role is None:
                return
            for parent_id in role.parent_role_ids:
                if parent_id not in inherited_ids:
                    inherited_ids.add(parent_id)
                    parents(parent_id)
        for root_id in root_ids:
            parents(root_id)
        own_permissions = sorted({p for role_id in root_ids if role_id in role_map for p in role_map[role_id].permissions})
        inherited_permissions = sorted({p for role_id in inherited_ids if role_id in role_map for p in role_map[role_id].permissions})
        return Ok({
            "permissions": sorted(set(own_permissions) | set(inherited_permissions)),
            "direct_roles": direct_ids,
            "group_roles": group_roles,
            "inherited_roles": sorted(inherited_ids),
            "own_permissions": own_permissions,
            "inherited_permissions": inherited_permissions,
        })

    async def list_roles_discovery(self, account_id: str) -> Result[list[dict], XoloException]:
        """List all roles for data discovery."""
        result = await self._roles.find_all(account_id)
        if result.is_err:
            return result
        roles = result.unwrap()
        return Ok([{"id": r.role_id, "name": r.name} for r in roles])
