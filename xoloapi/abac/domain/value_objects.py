from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict

WILDCARD = "*"


class ValueObject(BaseModel):
    model_config = ConfigDict(frozen=True)


class Subject(ValueObject):
    value: str

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.lower() == candidate.lower()


class Resource(ValueObject):
    value: str

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.lower() == candidate.lower()


class Location(ValueObject):
    value: str

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.lower() == candidate.lower()


class Action(ValueObject):
    value: str

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.upper() == candidate.upper()


class TimeWindow(ValueObject):
    """Both None means wildcard — matches any time."""
    start: Optional[str] = None
    end:   Optional[str] = None

    @property
    def is_wildcard(self) -> bool:
        return self.start is None and self.end is None

    def matches(self, candidate: Optional[str]) -> bool:
        if self.is_wildcard:
            return True
        if candidate is None:
            return False
        try:
            def _parse(s: str) -> int:
                h, m = s.split(":")
                return int(h) * 60 + int(m)
            t = _parse(candidate)
            return _parse(self.start) <= t <= _parse(self.end)
        except (ValueError, AttributeError):
            return False


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY  = "DENY"
