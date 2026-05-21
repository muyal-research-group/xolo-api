from abc import ABC, abstractmethod
from option import Option, Result

from xoloapi.groups.domain.aggregates import GroupMember, SecurityGroup
from xoloapi.errors.base import XoloException


class ISecurityGroupRepository(ABC):

    @abstractmethod
    async def list_all(self, account_id: str) -> Result[list[SecurityGroup], XoloException]: ...

    @abstractmethod
    async def find_by_id(
        self, account_id: str, group_id: str
    ) -> Result[Option[SecurityGroup], XoloException]: ...

    @abstractmethod
    async def find_by_name(
        self, account_id: str, name: str
    ) -> Result[Option[SecurityGroup], XoloException]: ...

    @abstractmethod
    async def find_groups_for_user(
        self, account_id: str, user_id: str
    ) -> Result[list[SecurityGroup], XoloException]:
        """Groups the user owns OR is a member of."""
        ...

    @abstractmethod
    async def find_group_ids_for_user(
        self, account_id: str, user_id: str
    ) -> Result[list[str], XoloException]: ...

    @abstractmethod
    async def save(
        self, group: SecurityGroup
    ) -> Result[SecurityGroup, XoloException]: ...

    @abstractmethod
    async def delete(
        self, account_id: str, group_id: str
    ) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def add_member(
        self, account_id: str, group_id: str, user_id: str
    ) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def remove_member(
        self, account_id: str, group_id: str, user_id: str
    ) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def list_members(
        self, account_id: str, group_id: str
    ) -> Result[list[GroupMember], XoloException]: ...

    @abstractmethod
    async def is_member(
        self, account_id: str, group_id: str, user_id: str
    ) -> Result[bool, XoloException]: ...
