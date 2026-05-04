from typing import List, Optional
from pydantic import BaseModel
from xoloapi.abac.domain.value_objects import Effect, WILDCARD


class CreateABACEventDTO(BaseModel):
    subject:    str
    resource:   str
    location:   str = WILDCARD
    time_start: Optional[str] = None  # "HH:MM"
    time_end:   Optional[str] = None  # "HH:MM"
    action:     str


class CreateABACPolicyDTO(BaseModel):
    name:   str
    effect: Effect = Effect.ALLOW
    events: List[CreateABACEventDTO]


class ABACEvaluateDTO(BaseModel):
    subject:  str
    resource: str
    location: str = WILDCARD
    time:     Optional[str] = None  # "HH:MM"
    action:   str


class ABACDecisionDTO(BaseModel):
    allowed:        bool
    matched_policy: Optional[str] = None
    matched_event:  Optional[str] = None
    reason:         str
