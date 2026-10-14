from __future__ import annotations

import datetime as dt
from typing import Any, Literal
from nanoid import generate
from pydantic import BaseModel, Field


AuthorizationModel = Literal["groups", "rbac", "acl", "abac", "ngac", "accounts", "migration"]


class AuthorizationAuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"aud-{generate(size=16)}")
    timestamp: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    account_id: str
    model: AuthorizationModel
    actor_type: Literal["platform", "service", "tenant", "migration", "unknown"] = "unknown"
    actor_id: str
    action: str
    target: str
    before: Any | None = None
    after: Any | None = None
    correlation_id: str


class AuditPage(BaseModel):
    items: list[AuthorizationAuditEvent]
    next_cursor: str | None = None
