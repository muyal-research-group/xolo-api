from option import Ok, Result

from xoloapi.errors.base import XoloException
from xoloapi.ngac.application.ngac_service import NGACService as ApplicationNGACService
from xoloapi.ngac.models import NGACAssignment, NGACAssociation, NGACNode


def _node(node) -> NGACNode:
    return NGACNode(**node.model_dump())


def _assignment(assignment) -> NGACAssignment:
    return NGACAssignment(**assignment.model_dump())


def _association(association) -> NGACAssociation:
    return NGACAssociation(**association.model_dump())


class NGACService:
    def __init__(self, repository) -> None:
        self._service = ApplicationNGACService(repository=repository._repo if hasattr(repository, "_repo") else repository)

    async def create_node(self, account_id: str, dto, owner_id: str = "") -> Result[str, XoloException]:
        return await self._service.create_node(account_id, dto, owner_id=owner_id)

    async def get_node(self, account_id: str, node_id: str) -> Result[NGACNode, XoloException]:
        result = await self._service.get_node(account_id, node_id)
        if result.is_err:
            return result
        return Ok(_node(result.unwrap()))

    async def list_nodes(self, account_id: str, node_type: str | None = None) -> Result[list[NGACNode], XoloException]:
        result = await self._service.list_nodes(account_id, node_type=node_type)
        if result.is_err:
            return result
        return Ok([_node(node) for node in result.unwrap()])

    async def delete_node(self, account_id: str, node_id: str, requester_key: str = "", is_admin: bool = False) -> Result[bool, XoloException]:
        return await self._service.delete_node(account_id, node_id, requester_key=requester_key, is_admin=is_admin)

    async def assign(self, account_id: str, dto, owner_id: str = "", is_admin: bool = False) -> Result[str, XoloException]:
        return await self._service.assign(account_id, dto, owner_id=owner_id, is_admin=is_admin)

    async def remove_assignment(self, account_id: str, dto, requester_key: str = "", is_admin: bool = False) -> Result[bool, XoloException]:
        return await self._service.remove_assignment(account_id, dto, requester_key=requester_key, is_admin=is_admin)

    async def list_assignments(self, account_id: str) -> Result[list[NGACAssignment], XoloException]:
        result = await self._service.list_assignments(account_id)
        if result.is_err:
            return result
        return Ok([_assignment(item) for item in result.unwrap()])

    async def associate(self, account_id: str, dto, owner_id: str = "", is_admin: bool = False) -> Result[str, XoloException]:
        return await self._service.associate(account_id, dto, owner_id=owner_id, is_admin=is_admin)

    async def remove_association(self, account_id: str, association_id: str, requester_key: str = "", is_admin: bool = False) -> Result[bool, XoloException]:
        return await self._service.remove_association(account_id, association_id, requester_key=requester_key, is_admin=is_admin)

    async def list_associations(self, account_id: str) -> Result[list[NGACAssociation], XoloException]:
        result = await self._service.list_associations(account_id)
        if result.is_err:
            return result
        return Ok([_association(item) for item in result.unwrap()])

    async def check_access(self, account_id: str, dto):
        return await self._service.check_access(account_id, dto)


__all__ = ["NGACService"]
