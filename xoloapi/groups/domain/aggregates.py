import datetime
from typing import Optional
from pydantic import BaseModel, Field
from option import Result, Ok, Err

from xoloapi.errors.base import XoloException, AccessDeniedError


class SecurityGroup(BaseModel):
    account_id:  str
    group_id:    str
    name:        str
    owner_id:    str
    description: Optional[str] = None
    created_at:  datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at:  datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def assert_owner(self, caller_id: str) -> Result[None, XoloException]:
        if self.owner_id != caller_id:
            return Err(AccessDeniedError(
                "Only the group owner can perform this operation",
                metadata={"group_id": self.group_id},
            ))
        return Ok(None)

    def is_owned_by(self, user_id: str) -> bool:
        return self.owner_id == user_id


class GroupMember(BaseModel):
    account_id: str
    group_id:   str
    user_id:    str
    joined_at:  datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
