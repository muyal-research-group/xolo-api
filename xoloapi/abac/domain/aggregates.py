from __future__ import annotations
import datetime as dt
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from xoloapi.abac.domain.value_objects import (
    Action, Effect, GeoPoint, Location, MatcherVersion, Resource, Subject, TimeWindow,
)


class ABACAccessRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject:  str
    resource: str
    location: Optional[GeoPoint] = None
    time:     Optional[str] = None
    action:   str


class ABACDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed:        bool
    matched_policy: Optional[str] = None
    matched_event:  Optional[str] = None
    reason:         str
    matched_policy_ids: list[str] = []
    matched_event_ids: list[str] = []
    request_context: dict = {}
    warnings: list[str] = []


class ABACEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    subject:  Subject
    resource: Resource
    location: Location
    time:     TimeWindow
    action:   Action

    def matches(
        self,
        request: ABACAccessRequest,
        matcher_version: MatcherVersion = MatcherVersion.LEGACY_V1,
        policy_timezone: str = "UTC",
    ) -> bool:
        return (
            self.subject.matches(request.subject, matcher_version)
            and self.resource.matches(request.resource, matcher_version)
            and self.location.matches(request.location)
            and self.time.matches(request.time, policy_timezone)
            and self.action.matches(request.action, matcher_version)
        )


class ABACPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: str
    policy_id: str
    name:      str
    effect:    Effect
    events:    List[ABACEvent]
    matcher_version: MatcherVersion = MatcherVersion.GLOB_V2
    timezone: str = "UTC"
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def evaluate(self, request: ABACAccessRequest) -> Optional[Effect]:
        for event in self.events:
            if event.matches(request, self.matcher_version, self.timezone):
                return self.effect
        return None
