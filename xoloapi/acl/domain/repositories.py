from abc import ABC, abstractmethod
from option import Option, Result
from xoloapi.acl.domain.aggregates import ResourcePolicy
from xoloapi.errors.base import XoloException


class IResourcePolicyRepository(ABC):

    @abstractmethod
    async def list_all(self, account_id: str) -> Result[list[ResourcePolicy], XoloException]: ...

    @abstractmethod
    async def find_by_resource(
        self, account_id: str, resource_id: str
    ) -> Result[Option[ResourcePolicy], XoloException]: ...

    @abstractmethod
    async def find_owned_by(
        self, account_id: str, user_id: str, page: int, page_size: int
    ) -> Result[tuple[list[ResourcePolicy], int], XoloException]:
        """Returns (policies, total_count)."""
        ...

    @abstractmethod
    async def find_shared_with(
        self,
        account_id:         str,
        principal_ids:      list[str],
        exclude_resource_ids: list[str],
        page:               int,
        page_size:          int,
    ) -> Result[tuple[list[ResourcePolicy], int], XoloException]:
        """Resources where any grant matches principal_ids, excluding owned ones.
        Returns (policies, total_count)."""
        ...

    @abstractmethod
    async def save(
        self, policy: ResourcePolicy
    ) -> Result[ResourcePolicy, XoloException]: ...

    @abstractmethod
    async def delete(
        self, account_id: str, resource_id: str
    ) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def delete_all_by_user(
        self, account_id: str, user_id: str
    ) -> Result[int, XoloException]: ...
