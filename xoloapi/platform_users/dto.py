from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole


class PlatformLoginDTO(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class PlatformUserCreateDTO(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=12, max_length=1024)
    role: PlatformRole = PlatformRole.USER
    permissions: set[PlatformPermission] = Field(default_factory=set)
    allowed_account_ids: set[str] = Field(default_factory=set)
    must_change_password: bool = True


class PlatformUserUpdateDTO(BaseModel):
    role: PlatformRole | None = None
    permissions: set[PlatformPermission] | None = None
    allowed_account_ids: set[str] | None = None
    is_active: bool | None = None


class PlatformPasswordChangeDTO(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class PlatformPasswordResetDTO(BaseModel):
    password: str = Field(min_length=12, max_length=1024)


class PlatformUserDTO(BaseModel):
    user_id: str
    username: str
    role: PlatformRole
    permissions: set[PlatformPermission]
    allowed_account_ids: set[str]
    is_active: bool
    must_change_password: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    last_login_at: dt.datetime | None

    @classmethod
    def from_domain(cls, user: PlatformUser) -> "PlatformUserDTO":
        return cls(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            permissions=user.effective_permissions(),
            allowed_account_ids=user.allowed_account_ids,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )


class PlatformSessionDTO(BaseModel):
    user: PlatformUserDTO
    csrf_token: str


class PlatformOptionsDTO(BaseModel):
    roles: list[PlatformRole]
    permissions: list[PlatformPermission]
