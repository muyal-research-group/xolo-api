from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from nanoid import generate
from pydantic import BaseModel, Field


NotificationCategory = Literal["membership", "access", "policy", "security", "operation"]
NotificationSeverity = Literal["info", "success", "warning", "error"]


class NotificationEvent(BaseModel):
    notification_id: str = Field(default_factory=lambda: f"ntf-{generate(size=16)}")
    category: NotificationCategory
    severity: NotificationSeverity = "info"
    account_id: str
    model: str
    actor_type: str
    actor_id: str
    affected_principal: str | None = None
    action: str
    target: str
    safe_detail: dict[str, Any] = Field(default_factory=dict)
    link_target: str | None = None
    timestamp: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    expires_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=90)
    )


class NotificationItem(NotificationEvent):
    is_read: bool = False


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    next_cursor: str | None = None
