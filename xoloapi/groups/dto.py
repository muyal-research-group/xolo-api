from __future__ import annotations

import datetime as dt
from pydantic import BaseModel, Field


class CreateGroupDTO(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    owner_username: str = Field(min_length=1)


class UpdateGroupDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class TransferOwnerDTO(BaseModel):
    owner_username: str = Field(min_length=1)


class GroupStatusDTO(BaseModel):
    is_active: bool


class GroupMembersDTO(BaseModel):
    usernames: list[str] = Field(min_length=1)


class GroupReferenceDTO(BaseModel):
    group_id: str
    name: str
    is_active: bool


class GroupDTO(GroupReferenceDTO):
    description: str | None = None
    owner_id: str
    owner_username: str | None = None
    member_count: int = 0
    acl_usage_count: int = 0
    rbac_usage_count: int = 0
    created_at: dt.datetime
    updated_at: dt.datetime


class GroupMemberDTO(BaseModel):
    user_id: str
    username: str
    joined_at: dt.datetime


class GroupUsageDTO(BaseModel):
    acl_grants: list[dict]
    rbac_assignments: list[dict]


class GroupPageDTO(BaseModel):
    items: list[GroupDTO]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class GroupMemberPageDTO(BaseModel):
    items: list[GroupMemberDTO]
    total_count: int
    page: int
    page_size: int
    total_pages: int
