from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _iana_timezone(value: str) -> str:
    value = value.strip()
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone must be a valid IANA timezone") from exc
    return value


class CreateAccountDTO(BaseModel):
    account_id: str = Field(min_length=3)
    name: str = Field(min_length=1)
    timezone: str = "UTC"

    _validate_timezone = field_validator("timezone")(_iana_timezone)


class UpdateAccountDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    timezone: str | None = None
    is_active: bool | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        return None if value is None else _iana_timezone(value)


class AccountDTO(BaseModel):
    account_id: str
    name: str
    is_active: bool
    timezone: str = "UTC"
    created_at: datetime
    updated_at: datetime

