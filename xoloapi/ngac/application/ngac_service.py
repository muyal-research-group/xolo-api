import datetime

from nanoid import generate
from option import Result, Ok, Err

from xoloapi.errors.base import XoloException, NotFoundError, AccessDeniedError, ValidationError, ConflictError
from xoloapi.ngac.domain.aggregates import NGACAssignment, NGACAssociation, NGACNode
from xoloapi.ngac.domain.repositories import INGACRepository
from xoloapi.ngac.domain.services import NGACGraph
from xoloapi.ngac.domain.value_objects import NodeType, VALID_ASSIGNMENT_TARGETS
from xoloapi.users.application.user_resolution import resolve_user_identifier


def _owns(owner_id: str, node_owner: str) -> bool:
    return not node_owner or node_owner == owner_id


class NGACService:

    def __init__(self, repository: INGACRepository, users_repo=None, acl_repo=None) -> None:
        self._repo = repository
        self._users = users_repo
        self._acl = acl_repo

    # ── Nodes ─────────────────────────────────────────────────────────────────

    async def create_node(
        self,
        account_id:  str,
        node_type:   NodeType,
        name:        str,
        properties:  dict[str, str] = {},
        owner_id:    str = "",
        user_id:     str | None = None,
        user_identifier: str | None = None,
        resource_id: str | None = None,
    ) -> Result[str, XoloException]:
        if (user_id or user_identifier) and node_type != NodeType.USER:
            return Err(ValidationError("Only USER nodes may bind to tenant users"))
        if resource_id and node_type != NodeType.OBJECT:
            return Err(ValidationError("Only OBJECT nodes may bind to resources"))
        if (user_identifier or user_id) and self._users is not None:
            resolved = await resolve_user_identifier(self._users, account_id, user_identifier or user_id or "")
            if resolved.is_err:
                return Err(resolved.unwrap_err())
            user_id = resolved.unwrap().user_id
        if resource_id and self._acl is not None:
            resource = await self._acl.find_by_resource(account_id, resource_id)
            if resource.is_err:
                return Err(resource.unwrap_err())
            if resource.unwrap().is_none:
                return Err(NotFoundError("ResourcePolicy", resource_id))
        node = NGACNode(
            account_id = account_id,
            node_id    = f"n-{generate(size=10)}",
            node_type  = node_type,
            name       = name,
            properties = properties,
            owner_id   = owner_id,
            user_id    = user_id,
            resource_id= resource_id,
        )
        return await self._repo.create_node(node)

    async def get_node(self, account_id: str, node_id: str) -> Result[NGACNode, XoloException]:
        result = await self._repo.find_node(account_id, node_id)
        if result.is_err:
            return result
        opt = result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("NGACNode", node_id))
        return Ok(opt.unwrap())

    async def list_nodes(self, account_id: str, node_type: str | None = None) -> Result[list[NGACNode], XoloException]:
        return await self._repo.list_nodes(account_id, node_type=node_type)

    async def update_node(
        self,
        account_id:    str,
        node_id:       str,
        name:          str | None = None,
        properties:    dict[str, str] | None = None,
        user_id:       str | None = None,
        user_identifier: str | None = None,
        user_binding_set: bool | None = None,
        resource_id:   str | None = None,
        requester_key: str = "",
        is_admin:      bool = False,
    ) -> Result[NGACNode, XoloException]:
        node_result = await self.get_node(account_id, node_id)
        if node_result.is_err:
            return node_result
        node = node_result.unwrap()
        if not is_admin and not _owns(requester_key, node.owner_id):
            return Err(AccessDeniedError(f"Node '{node_id}' is owned by another user"))
        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                return Err(ValidationError("Node name cannot be empty"))
            node.name = normalized_name
        if properties is not None:
            node.properties = properties
        if user_binding_set is None:
            user_binding_set = user_id is not None or user_identifier is not None
        if user_binding_set:
            if node.node_type != NodeType.USER:
                return Err(ValidationError("Only USER nodes may bind to tenant users"))
            identifier = user_identifier if user_identifier is not None else user_id
            if identifier and self._users is not None:
                resolved = await resolve_user_identifier(self._users, account_id, identifier)
                if resolved.is_err:
                    return Err(resolved.unwrap_err())
                node.user_id = resolved.unwrap().user_id
            else:
                node.user_id = None
        if resource_id is not None:
            if node.node_type != NodeType.OBJECT:
                return Err(ValidationError("Only OBJECT nodes may bind to resources"))
            if resource_id and self._acl is not None:
                resource = await self._acl.find_by_resource(account_id, resource_id)
                if resource.is_err:
                    return Err(resource.unwrap_err())
                if resource.unwrap().is_none:
                    return Err(NotFoundError("ResourcePolicy", resource_id))
            node.resource_id = resource_id or None
        node.updated_at = datetime.datetime.now(datetime.timezone.utc)
        updated = await self._repo.update_node(node)
        if updated.is_err:
            return Err(updated.unwrap_err())
        return Ok(node)

    async def delete_node(
        self,
        account_id:    str,
        node_id:       str,
        requester_key: str  = "",
        is_admin:      bool = False,
    ) -> Result[bool, XoloException]:
        node_result = await self.get_node(account_id, node_id)
        if node_result.is_err:
            return node_result
        node = node_result.unwrap()
        if not is_admin and not _owns(requester_key, node.owner_id):
            return Err(AccessDeniedError(f"Node '{node_id}' is owned by another user"))
        return await self._repo.delete_node(account_id, node_id)

    # ── Assignments ───────────────────────────────────────────────────────────

    async def assign(
        self,
        account_id: str,
        from_id:    str,
        to_id:      str,
        owner_id:   str  = "",
        is_admin:   bool = False,
    ) -> Result[str, XoloException]:
        from_result = await self.get_node(account_id, from_id)
        if from_result.is_err:
            return from_result

        to_result = await self.get_node(account_id, to_id)
        if to_result.is_err:
            return to_result

        from_node = from_result.unwrap()
        to_node   = to_result.unwrap()

        allowed_targets = VALID_ASSIGNMENT_TARGETS.get(from_node.node_type, set())

        if to_node.node_type not in allowed_targets:
            return Err(ValidationError(
                f"Cannot assign {from_node.node_type} → {to_node.node_type}. "
                f"Allowed targets: {[t.value for t in allowed_targets]}"
            ))

        if not is_admin and not _owns(owner_id, to_node.owner_id):
            return Err(AccessDeniedError(f"Target node '{to_id}' is owned by another user"))

        graph_result = await self._repo.load_graph_data(account_id)
        if graph_result.is_err:
            return Err(graph_result.unwrap_err())
        nodes, assignments, associations = graph_result.unwrap()
        graph = NGACGraph(nodes, assignments, associations)
        if from_id in graph.upward_closure(to_id):
            return Err(ConflictError("Assignment would create a cycle"))

        assignment = NGACAssignment(
            account_id    = account_id,
            assignment_id = f"a-{generate(size=10)}",
            from_id       = from_id,
            to_id         = to_id,
            owner_id      = owner_id,
        )
        return await self._repo.create_assignment(assignment)

    async def remove_assignment(
        self,
        account_id:    str,
        from_id:       str,
        to_id:         str,
        requester_key: str  = "",
        is_admin:      bool = False,
    ) -> Result[bool, XoloException]:
        assign_result = await self._repo.find_assignment(account_id, from_id, to_id)
        if assign_result.is_err:
            return assign_result
        opt = assign_result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("NGACAssignment", f"{from_id}->{to_id}"))
        assignment = opt.unwrap()
        if not is_admin and not _owns(requester_key, assignment.owner_id):
            return Err(AccessDeniedError("Assignment is owned by another user"))
        return await self._repo.remove_assignment(account_id, from_id, to_id)

    async def list_assignments(self, account_id: str) -> Result[list[NGACAssignment], XoloException]:
        return await self._repo.list_assignments(account_id)

    # ── Associations ──────────────────────────────────────────────────────────

    async def associate(
        self,
        account_id:          str,
        user_attribute_id:   str,
        object_attribute_id: str,
        operations:          list[str],
        owner_id:            str  = "",
        is_admin:            bool = False,
    ) -> Result[str, XoloException]:
        ua_result = await self.get_node(account_id, user_attribute_id)
        if ua_result.is_err:
            return ua_result

        oa_result = await self.get_node(account_id, object_attribute_id)
        if oa_result.is_err:
            return oa_result

        ua_node = ua_result.unwrap()
        oa_node = oa_result.unwrap()

        if ua_node.node_type != NodeType.USER_ATTRIBUTE:
            return Err(ValidationError("Source node must be of type 'user_attribute'"))

        if oa_node.node_type != NodeType.OBJECT_ATTRIBUTE:
            return Err(ValidationError("Target node must be of type 'object_attribute'"))

        if not is_admin and not _owns(owner_id, ua_node.owner_id):
            return Err(AccessDeniedError(f"UserAttribute '{user_attribute_id}' is owned by another user"))

        normalized_ops = list(dict.fromkeys(op.strip().lower() for op in operations if op.strip()))
        if not normalized_ops:
            return Err(ValidationError("operations must contain at least one non-empty operation"))
        assoc = NGACAssociation(
            account_id          = account_id,
            association_id      = f"as-{generate(size=10)}",
            user_attribute_id   = user_attribute_id,
            object_attribute_id = object_attribute_id,
            operations          = normalized_ops,
            owner_id            = owner_id,
        )
        return await self._repo.create_association(assoc)

    async def update_association(
        self, account_id: str, association_id: str, operations: list[str],
        requester_key: str = "", is_admin: bool = False,
    ) -> Result[NGACAssociation, XoloException]:
        found = await self._repo.find_association(account_id, association_id)
        if found.is_err:
            return Err(found.unwrap_err())
        if found.unwrap().is_none:
            return Err(NotFoundError("NGACAssociation", association_id))
        association = found.unwrap().unwrap()
        if not is_admin and not _owns(requester_key, association.owner_id):
            return Err(AccessDeniedError("Association is owned by another user"))
        normalized = list(dict.fromkeys(op.strip().lower() for op in operations if op.strip()))
        if not normalized:
            return Err(ValidationError("operations must contain at least one non-empty operation"))
        updated = association.model_copy(update={"operations": normalized})
        saved = await self._repo.update_association(updated)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(updated)

    async def deletion_impact(self, account_id: str, node_id: str) -> Result[dict, XoloException]:
        graph = await self._repo.load_graph_data(account_id)
        if graph.is_err:
            return Err(graph.unwrap_err())
        nodes, assignments, associations = graph.unwrap()
        if not any(node.node_id == node_id for node in nodes):
            return Err(NotFoundError("NGACNode", node_id))
        return Ok({
            "assignments": [a.model_dump() for a in assignments if node_id in {a.from_id, a.to_id}],
            "associations": [a.model_dump() for a in associations if node_id in {a.user_attribute_id, a.object_attribute_id}],
        })

    async def resolved_graph(self, account_id: str) -> Result[dict, XoloException]:
        graph = await self._repo.load_graph_data(account_id)
        if graph.is_err:
            return Err(graph.unwrap_err())
        nodes, assignments, associations = graph.unwrap()
        names = {node.node_id: node.name for node in nodes}
        node_rows = []
        for node in nodes:
            row = node.model_dump()
            row["username"] = None
            if node.user_id and self._users is not None:
                user = await self._users.find_by_id(node.user_id, account_id=account_id)
                if user.is_some:
                    row["username"] = user.unwrap().username
            node_rows.append(row)
        return Ok({
            "nodes": node_rows,
            "assignments": [dict(a.model_dump(), from_name=names.get(a.from_id), to_name=names.get(a.to_id)) for a in assignments],
            "associations": [dict(a.model_dump(), user_attribute_name=names.get(a.user_attribute_id), object_attribute_name=names.get(a.object_attribute_id)) for a in associations],
        })

    async def remove_association(
        self,
        account_id:      str,
        association_id: str,
        requester_key:  str  = "",
        is_admin:       bool = False,
    ) -> Result[bool, XoloException]:
        assoc_result = await self._repo.find_association(account_id, association_id)
        if assoc_result.is_err:
            return assoc_result
        opt = assoc_result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("NGACAssociation", association_id))
        assoc = opt.unwrap()
        if not is_admin and not _owns(requester_key, assoc.owner_id):
            return Err(AccessDeniedError("Association is owned by another user"))
        return await self._repo.remove_association(account_id, association_id)

    async def list_associations(self, account_id: str) -> Result[list[NGACAssociation], XoloException]:
        return await self._repo.list_associations(account_id)

    # ── Access check ──────────────────────────────────────────────────────────

    async def check_access(
        self,
        account_id: str,
        user_id:    str,
        object_id:  str,
        operation:  str,
    ) -> Result[tuple[bool, str], XoloException]:
        graph_result = await self._repo.load_graph_data(account_id)
        if graph_result.is_err:
            return graph_result

        nodes, assignments, associations = graph_result.unwrap()
        graph = NGACGraph(nodes=nodes, assignments=assignments, associations=associations)
        allowed, reason = graph.check(user_id=user_id, object_id=object_id, operation=operation)
        return Ok((allowed, reason))

    async def check_access_detailed(self, account_id: str, user_id: str, object_id: str, operation: str) -> Result[dict, XoloException]:
        graph_result = await self._repo.load_graph_data(account_id)
        if graph_result.is_err:
            return Err(graph_result.unwrap_err())
        nodes, assignments, associations = graph_result.unwrap()
        return Ok(NGACGraph(nodes, assignments, associations).explain(user_id, object_id, operation))
