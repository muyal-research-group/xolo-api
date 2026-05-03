from abc import ABC, abstractmethod
from option import Result, Option

from xoloapi.errors.base import XoloException
from xoloapi.rbac.domain.aggregates import Role, RoleAssignment


class IRoleRepository(ABC):

    @abstractmethod
    async def find_by_id(self, account_id: str, role_id: str) -> Result[Option[Role], XoloException]: ...

    @abstractmethod
    async def find_by_name(self, account_id: str, name: str) -> Result[Option[Role], XoloException]: ...

    @abstractmethod
    async def find_many(self, account_id: str, role_ids: list[str]) -> Result[list[Role], XoloException]: ...

    @abstractmethod
    async def find_all(self, account_id: str) -> Result[list[Role], XoloException]: ...

    @abstractmethod
    async def save(self, role: Role) -> Result[None, XoloException]: ...

    @abstractmethod
    async def delete(self, account_id: str, role_id: str) -> Result[None, XoloException]: ...


class IRoleAssignmentRepository(ABC):

    @abstractmethod
    async def find_all(self, account_id: str) -> Result[list[RoleAssignment], XoloException]: ...

    @abstractmethod
    async def find_by_subject(self, account_id: str, subject_id: str) -> Result[list[RoleAssignment], XoloException]: ...

    @abstractmethod
    async def find_by_role(self, account_id: str, role_id: str) -> Result[list[RoleAssignment], XoloException]: ...

    @abstractmethod
    async def find_assignment(self, account_id: str, subject_id: str, role_id: str) -> Result[Option[RoleAssignment], XoloException]: ...

    @abstractmethod
    async def save(self, assignment: RoleAssignment) -> Result[None, XoloException]: ...

    @abstractmethod
    async def delete(self, account_id: str, assignment_id: str) -> Result[None, XoloException]: ...

    @abstractmethod
    async def delete_by_subject(self, account_id: str, subject_id: str) -> Result[None, XoloException]: ...

    @abstractmethod
    async def delete_by_role(self, account_id: str, role_id: str) -> Result[None, XoloException]: ...
