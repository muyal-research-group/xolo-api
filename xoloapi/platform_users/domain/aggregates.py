from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole


class PlatformUser(BaseModel):
    user_id: str
    username: str
    password_hash: str
    role: PlatformRole = PlatformRole.USER
    permissions: set[PlatformPermission] = Field(default_factory=set)
    allowed_account_ids: set[str] = Field(default_factory=set)
    is_active: bool = True
    must_change_password: bool = False
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    last_login_at: dt.datetime | None = None

    def effective_permissions(self) -> set[PlatformPermission]:
        if self.role == PlatformRole.ADMIN:
            return set(PlatformPermission)
        if self.role == PlatformRole.GUEST:
            return {permission for permission in self.permissions if permission.read_only}
        return set(self.permissions)

    def can(self, permission: PlatformPermission, account_id: str | None = None) -> bool:
        if not self.is_active:
            return False
        if self.role == PlatformRole.ADMIN:
            return True
        if permission not in self.effective_permissions():
            return False
        if account_id is None:
            return True
        return account_id in self.allowed_account_ids
