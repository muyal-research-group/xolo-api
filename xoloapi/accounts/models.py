from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class Account(BaseModel):
    account_id: str
    name: str
    is_active: bool = True
    created_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )

