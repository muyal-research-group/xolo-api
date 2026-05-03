from abc import ABC, abstractmethod
from option import Result, Option

from xoloapi.errors.base import XoloException
from xoloapi.ngac.domain.aggregates import NGACAssignment, NGACAssociation, NGACNode


class INGACRepository(ABC):

    # ── Nodes ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def create_node(self, node: NGACNode) -> Result[str, XoloException]: ...

    @abstractmethod
    async def find_node(self, account_id: str, node_id: str) -> Result[Option[NGACNode], XoloException]: ...

    @abstractmethod
    async def list_nodes(self, account_id: str, node_type: str | None = None) -> Result[list[NGACNode], XoloException]: ...

    @abstractmethod
    async def delete_node(self, account_id: str, node_id: str) -> Result[bool, XoloException]: ...

    # ── Assignments ───────────────────────────────────────────────────────────

    @abstractmethod
    async def create_assignment(self, assignment: NGACAssignment) -> Result[str, XoloException]: ...

    @abstractmethod
    async def find_assignment(self, account_id: str, from_id: str, to_id: str) -> Result[Option[NGACAssignment], XoloException]: ...

    @abstractmethod
    async def remove_assignment(self, account_id: str, from_id: str, to_id: str) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def list_assignments(self, account_id: str) -> Result[list[NGACAssignment], XoloException]: ...

    # ── Associations ──────────────────────────────────────────────────────────

    @abstractmethod
    async def create_association(self, assoc: NGACAssociation) -> Result[str, XoloException]: ...

    @abstractmethod
    async def find_association(self, account_id: str, association_id: str) -> Result[Option[NGACAssociation], XoloException]: ...

    @abstractmethod
    async def remove_association(self, account_id: str, association_id: str) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def list_associations(self, account_id: str) -> Result[list[NGACAssociation], XoloException]: ...

    # ── Graph snapshot ────────────────────────────────────────────────────────

    @abstractmethod
    async def load_graph_data(
        self,
        account_id: str,
    ) -> Result[tuple[list[NGACNode], list[NGACAssignment], list[NGACAssociation]], XoloException]: ...
