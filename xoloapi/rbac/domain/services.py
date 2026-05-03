"""RBAC domain service — pure, stateless logic for permission resolution."""
from collections import deque

from xoloapi.rbac.domain.aggregates import Role
from xoloapi.rbac.domain.value_objects import RBACPermission


class RBACDomainService:

    def resolve_effective_permissions(self, roles: list[Role], all_roles: dict[str, Role]) -> set[str]:
        """BFS through role hierarchy; return union of all reachable permissions."""
        visited:  set[str]  = set()
        result:   set[str]  = set()
        queue:    deque[str] = deque(r.role_id for r in roles)

        while queue:
            role_id = queue.popleft()
            if role_id in visited:
                continue
            visited.add(role_id)

            role = all_roles.get(role_id)
            if role is None:
                continue

            result.update(role.permissions)
            queue.extend(pid for pid in role.parent_role_ids if pid not in visited)

        return result

    def check(self, effective_permissions: set[str], required: str) -> bool:
        """Return True if any effective permission grants the required one."""
        req = RBACPermission.from_string(required)
        return any(
            RBACPermission.from_string(p).matches(req)
            for p in effective_permissions
        )

    def would_create_cycle(self, role_id: str, new_parent_id: str, all_roles: dict[str, Role]) -> bool:
        """Return True if adding role_id → new_parent_id would introduce a cycle."""
        visited: set[str] = set()
        queue:   deque[str] = deque([new_parent_id])

        while queue:
            current = queue.popleft()
            if current == role_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            role = all_roles.get(current)
            if role:
                queue.extend(role.parent_role_ids)

        return False
