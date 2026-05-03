import datetime
from typing import Optional
from nanoid import generate
from pydantic import BaseModel, Field

from xoloapi.rbac.domain.value_objects import RBACPermission


class Role(BaseModel):
    """Aggregate root — one document per role."""
    account_id:      str
    role_id:         str
    name:            str
    description:     Optional[str] = None
    permissions:     list[str] = Field(default_factory=list)   # "resource_type:action" strings
    parent_role_ids: list[str] = Field(default_factory=list)   # role IDs this role inherits from
    created_at:      datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at:      datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def add_permission(self, perm: str) -> "Role":
        if perm in self.permissions:
            return self
        return self.model_copy(update={
            "permissions": self.permissions + [perm],
            "updated_at":  datetime.datetime.now(datetime.timezone.utc),
        })

    def remove_permission(self, perm: str) -> "Role":
        if perm not in self.permissions:
            return self
        return self.model_copy(update={
            "permissions": [p for p in self.permissions if p != perm],
            "updated_at":  datetime.datetime.now(datetime.timezone.utc),
        })

    def own_permissions(self) -> list[RBACPermission]:
        return [RBACPermission.from_string(p) for p in self.permissions]

    @staticmethod
    def new(account_id: str, name: str, description: Optional[str] = None, permissions: Optional[list[str]] = None) -> "Role":
        return Role(
            account_id  = account_id,
            role_id     = f"role-{generate(size=10)}",
            name        = name,
            description = description,
            permissions = permissions or [],
        )


class RoleAssignment(BaseModel):
    """Assigns a role to a subject (user or other entity)."""
    account_id:    str
    assignment_id: str
    subject_id:    str
    role_id:       str
    assigned_at:   datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @staticmethod
    def new(account_id: str, subject_id: str, role_id: str) -> "RoleAssignment":
        return RoleAssignment(
            account_id    = account_id,
            assignment_id = f"ra-{generate(size=10)}",
            subject_id    = subject_id,
            role_id       = role_id,
        )
