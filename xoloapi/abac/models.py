from typing import Optional
from pydantic import BaseModel

from xoloapi.abac.domain.value_objects import Effect


class _CompatModel(BaseModel):
    def __getitem__(self, key: str):
        return getattr(self, key)


class ABACEventRecord(_CompatModel):
    event_id:           str
    subject:            str
    resource:           str
    location_lat:       Optional[float] = None
    location_lng:       Optional[float] = None
    location_radius_km: float = 1.0
    time_mode:          str   = "wildcard"
    time_start:         Optional[str] = None
    time_end:           Optional[str] = None
    action:             str


class ABACPolicyRecord(_CompatModel):
    account_id: str
    policy_id:  str
    name:       str
    effect:     Effect
    events:     list[ABACEventRecord]


__all__ = ["ABACEventRecord", "ABACPolicyRecord"]
