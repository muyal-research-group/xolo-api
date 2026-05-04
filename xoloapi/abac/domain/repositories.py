from abc import ABC, abstractmethod
from option import Result, Option

from xoloapi.errors.base import XoloException
from xoloapi.abac.domain.aggregates import ABACPolicy


class IABACRepository(ABC):

    @abstractmethod
    async def save(self, policy: ABACPolicy, raw_events: list[dict]) -> Result[str, XoloException]: ...

    @abstractmethod
    async def find_by_id(self, account_id: str, policy_id: str) -> Result[Option[ABACPolicy], XoloException]: ...

    @abstractmethod
    async def find_all(self, account_id: str) -> Result[list[ABACPolicy], XoloException]: ...

    @abstractmethod
    async def delete(self, account_id: str, policy_id: str) -> Result[bool, XoloException]: ...
