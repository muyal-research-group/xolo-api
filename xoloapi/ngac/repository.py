from option import Err, Ok, Result

from xoloapi.db.constants import CollectionNames
from xoloapi.errors.base import NotFoundError, XoloException
from xoloapi.ngac.infrastructure.mongo_ngac_repository import MongoNGACRepository
from xoloapi.ngac.models import NGACAssignment, NGACAssociation, NGACNode


def _node(node) -> NGACNode:
    return NGACNode(**node.model_dump())


def _assignment(assignment) -> NGACAssignment:
    return NGACAssignment(**assignment.model_dump())


def _association(association) -> NGACAssociation:
    return NGACAssociation(**association.model_dump())


class NGACRepository:
    def __init__(
        self,
        db,
        nodes_col: str = CollectionNames.NGAC_NODES_COLLECTION_NAME,
        assignments_col: str = CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
        associations_col: str = CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
    ) -> None:
        self._repo = MongoNGACRepository(
            db=db,
            nodes_col=nodes_col,
            assignments_col=assignments_col,
            associations_col=associations_col,
        )

    async def create_node(self, node: NGACNode) -> Result[str, XoloException]:
        return await self._repo.create_node(node)

    async def get_node(self, account_id: str, node_id: str) -> Result[NGACNode, XoloException]:
        result = await self._repo.find_node(account_id, node_id)
        if result.is_err:
            return result
        opt = result.unwrap()
        if opt.is_none:
            return Err(NotFoundError("NGACNode", node_id))
        return Ok(_node(opt.unwrap()))

    async def list_nodes(self, account_id: str, node_type: str | None = None) -> Result[list[NGACNode], XoloException]:
        result = await self._repo.list_nodes(account_id, node_type=node_type)
        if result.is_err:
            return result
        return Ok([_node(node) for node in result.unwrap()])

    async def delete_node(self, account_id: str, node_id: str) -> Result[bool, XoloException]:
        return await self._repo.delete_node(account_id, node_id)

    async def create_assignment(self, assignment: NGACAssignment) -> Result[str, XoloException]:
        return await self._repo.create_assignment(assignment)

    async def remove_assignment(self, account_id: str, from_id: str, to_id: str) -> Result[bool, XoloException]:
        return await self._repo.remove_assignment(account_id, from_id, to_id)

    async def list_assignments(self, account_id: str) -> Result[list[NGACAssignment], XoloException]:
        result = await self._repo.list_assignments(account_id)
        if result.is_err:
            return result
        return Ok([_assignment(item) for item in result.unwrap()])

    async def create_association(self, association: NGACAssociation) -> Result[str, XoloException]:
        return await self._repo.create_association(association)

    async def remove_association(self, account_id: str, association_id: str) -> Result[bool, XoloException]:
        return await self._repo.remove_association(account_id, association_id)

    async def list_associations(self, account_id: str) -> Result[list[NGACAssociation], XoloException]:
        result = await self._repo.list_associations(account_id)
        if result.is_err:
            return result
        return Ok([_association(item) for item in result.unwrap()])

    async def load_graph_data(self, account_id: str):
        result = await self._repo.load_graph_data(account_id)
        if result.is_err:
            return result
        nodes, assignments, associations = result.unwrap()
        return Ok(
            (
                [_node(node) for node in nodes],
                [_assignment(item) for item in assignments],
                [_association(item) for item in associations],
            )
        )


__all__ = ["NGACRepository"]
