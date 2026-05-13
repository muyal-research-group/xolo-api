from nanoid import generate
from option import Result, Ok, Err

from xoloapi.errors.base import XoloException, NotFoundError, AccessDeniedError, ValidationError
from xoloapi.ngac.domain.aggregates import NGACAssignment, NGACAssociation, NGACNode
from xoloapi.ngac.domain.repositories import INGACRepository
from xoloapi.ngac.domain.services import NGACGraph
from xoloapi.ngac.domain.value_objects import NodeType, VALID_ASSIGNMENT_TARGETS
from xoloapi.ngac.dto import (
    AssignDTO, AssociateDTO, CheckAccessDTO,
    CreateNodeDTO, NGACDecisionDTO, RemoveAssignmentDTO,
)


def _owns(owner_id: str, node_owner: str) -> bool:
    return not node_owner or node_owner == owner_id


class NGACService:

    def __init__(self, repository: INGACRepository) -> None:
        self._repo = repository

    # ── Nodes ─────────────────────────────────────────────────────────────────

    async def create_node(self, account_id: str, dto: CreateNodeDTO, owner_id: str = "") -> Result[str, XoloException]:
        node = NGACNode(
            account_id = account_id,
            node_id    = f"n-{generate(size=10)}",
            node_type  = dto.node_type,
            name       = dto.name,
            properties = dto.properties,
            owner_id   = owner_id,
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
        dto:      AssignDTO,
        owner_id: str  = "",
        is_admin: bool = False,
    ) -> Result[str, XoloException]:
        from_result = await self.get_node(account_id, dto.from_id)
        if from_result.is_err:
            return from_result

        to_result = await self.get_node(account_id, dto.to_id)
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
            return Err(AccessDeniedError(f"Target node '{dto.to_id}' is owned by another user"))

        assignment = NGACAssignment(
            account_id    = account_id,
            assignment_id = f"a-{generate(size=10)}",
            from_id       = dto.from_id,
            to_id         = dto.to_id,
            owner_id      = owner_id,
        )
        return await self._repo.create_assignment(assignment)

    async def remove_assignment(
        self,
        account_id:     str,
        dto:           RemoveAssignmentDTO,
        requester_key: str  = "",
        is_admin:      bool = False,
    ) -> Result[bool, XoloException]:
        assign_result = await self._repo.find_assignment(account_id, dto.from_id, dto.to_id)
        if assign_result.is_err:
            return assign_result
        opt = assign_result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("NGACAssignment", f"{dto.from_id}->{dto.to_id}"))
        assignment = opt.unwrap()
        if not is_admin and not _owns(requester_key, assignment.owner_id):
            return Err(AccessDeniedError("Assignment is owned by another user"))
        return await self._repo.remove_assignment(account_id, dto.from_id, dto.to_id)

    async def list_assignments(self, account_id: str) -> Result[list[NGACAssignment], XoloException]:
        return await self._repo.list_assignments(account_id)

    # ── Associations ──────────────────────────────────────────────────────────

    async def associate(
        self,
        account_id: str,
        dto:      AssociateDTO,
        owner_id: str  = "",
        is_admin: bool = False,
    ) -> Result[str, XoloException]:
        ua_result = await self.get_node(account_id, dto.user_attribute_id)
        if ua_result.is_err:
            return ua_result

        oa_result = await self.get_node(account_id, dto.object_attribute_id)
        if oa_result.is_err:
            return oa_result

        ua_node = ua_result.unwrap()
        oa_node = oa_result.unwrap()

        if ua_node.node_type != NodeType.USER_ATTRIBUTE:
            return Err(ValidationError("Source node must be of type 'user_attribute'"))

        if oa_node.node_type != NodeType.OBJECT_ATTRIBUTE:
            return Err(ValidationError("Target node must be of type 'object_attribute'"))

        if not is_admin and not _owns(owner_id, ua_node.owner_id):
            return Err(AccessDeniedError(f"UserAttribute '{dto.user_attribute_id}' is owned by another user"))

        assoc = NGACAssociation(
            account_id           = account_id,
            association_id      = f"as-{generate(size=10)}",
            user_attribute_id   = dto.user_attribute_id,
            object_attribute_id = dto.object_attribute_id,
            operations          = [op.lower() for op in dto.operations],
            owner_id            = owner_id,
        )
        return await self._repo.create_association(assoc)

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

    async def check_access(self, account_id: str, dto: CheckAccessDTO) -> Result[NGACDecisionDTO, XoloException]:
        graph_result = await self._repo.load_graph_data(account_id)
        if graph_result.is_err:
            return graph_result

        nodes, assignments, associations = graph_result.unwrap()
        graph = NGACGraph(nodes=nodes, assignments=assignments, associations=associations)
        allowed, reason = graph.check(
            user_id   = dto.user_id,
            object_id = dto.object_id,
            operation = dto.operation,
        )
        return Ok(NGACDecisionDTO(
            allowed   = allowed,
            reason    = reason,
            user_id   = dto.user_id,
            object_id = dto.object_id,
            operation = dto.operation,
        ))
