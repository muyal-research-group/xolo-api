from abc import ABC, abstractmethod

from option import Option, Result

from xoloapi.errors.base import XoloException
from xoloapi.platform_users.domain.aggregates import PlatformUser


class IPlatformUserRepository(ABC):
    @abstractmethod
    async def ensure_indexes(self) -> Result[None, XoloException]: ...

    @abstractmethod
    async def count(self) -> Result[int, XoloException]: ...

    @abstractmethod
    async def count_active_admins(self) -> Result[int, XoloException]: ...

    @abstractmethod
    async def find_by_id(self, user_id: str) -> Result[Option[PlatformUser], XoloException]: ...

    @abstractmethod
    async def find_by_username(self, username: str) -> Result[Option[PlatformUser], XoloException]: ...

    @abstractmethod
    async def list_all(self) -> Result[list[PlatformUser], XoloException]: ...

    @abstractmethod
    async def save(self, user: PlatformUser) -> Result[PlatformUser, XoloException]: ...

    @abstractmethod
    async def delete(self, user_id: str) -> Result[bool, XoloException]: ...
