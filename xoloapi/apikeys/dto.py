import datetime
from typing import Optional
from pydantic import BaseModel, Field
from xoloapi.apikeys.domain.value_objects import APIKeyScope


class CreateAPIKeyDTO(BaseModel):
    account_id: str | None = None
    name:       str
    scopes:     list[APIKeyScope]
    expires_at: Optional[datetime.datetime] = None


class CreatedAPIKeyResponseDTO(BaseModel):
    """Returned once at creation time. The `key` field will never be shown again."""
    account_id: str
    key_id:     str
    key:        str = Field(description="Raw API key — store it now, it will not be shown again")
    key_prefix: str
    name:       str
    scopes:     list[APIKeyScope]
    expires_at: Optional[datetime.datetime]
    created_at: datetime.datetime


class APIKeyMetadataDTO(BaseModel):
    """Safe metadata — never exposes the raw key or its hash."""
    account_id:    str
    key_id:       str
    key_prefix:   str
    name:         str
    scopes:       list[APIKeyScope]
    is_active:    bool
    created_at:   datetime.datetime
    expires_at:   Optional[datetime.datetime]
    last_used_at: Optional[datetime.datetime]


class RotatedAPIKeyResponseDTO(BaseModel):
    """Returned once after rotation. The new `key` will never be shown again."""
    account_id: str
    key_id:     str
    key:        str = Field(description="New raw API key — store it now, it will not be shown again")
    key_prefix: str
