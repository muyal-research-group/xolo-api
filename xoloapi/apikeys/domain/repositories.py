from abc import ABC, abstractmethod
from option import Option, Result
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.errors.base import XoloException


class IAPIKeyRepository(ABC):

    @abstractmethod
    async def find_by_hash(self, key_hash: str) -> Result[Option[APIKey], XoloException]: ...

    @abstractmethod
    async def find_by_id(self, key_id: str) -> Result[Option[APIKey], XoloException]: ...

    @abstractmethod
    async def find_all(self) -> Result[list[APIKey], XoloException]: ...

    @abstractmethod
    async def find_all_for_account(self, account_id: str) -> Result[list[APIKey], XoloException]: ...

    @abstractmethod
    async def save(self, key: APIKey) -> Result[APIKey, XoloException]: ...

    @abstractmethod
    async def delete(self, key_id: str) -> Result[bool, XoloException]: ...

    @abstractmethod
    async def update_last_used(self, key_id: str) -> None:
        """Best-effort touch — callers must not rely on this succeeding."""
        ...
