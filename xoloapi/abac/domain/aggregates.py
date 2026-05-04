from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from xoloapi.abac.domain.value_objects import (
    Action, Effect, Location, Resource, Subject, TimeWindow, WILDCARD,
)


class ABACAccessRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject:  str
    resource: str
    location: str = WILDCARD
    time:     Optional[str] = None
    action:   str


class ABACDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed:        bool
    matched_policy: Optional[str] = None
    matched_event:  Optional[str] = None
    reason:         str


class ABACEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    subject:  Subject
    resource: Resource
    location: Location
    time:     TimeWindow
    action:   Action

    def matches(self, request: ABACAccessRequest) -> bool:
        return (
            self.subject.matches(request.subject)
            and self.resource.matches(request.resource)
            and self.location.matches(request.location)
            and self.time.matches(request.time)
            and self.action.matches(request.action)
        )


class ABACPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: str
    policy_id: str
    name:      str
    effect:    Effect
    events:    List[ABACEvent]

    def evaluate(self, request: ABACAccessRequest) -> Optional[Effect]:
        for event in self.events:
            if event.matches(request):
                return self.effect
        return None
