import datetime
from nanoid import generate
from typing import Optional
from pydantic import BaseModel, Field
from option import Result, Ok, Err

from xoloapi.acl.domain.value_objects import Permission, PrincipalType, Principal
from xoloapi.errors.base import (
    XoloException,
    AccessDeniedError,
    ConflictError,
    NotFoundError,
)


# ── Child entity (embedded inside ResourcePolicy) ─────────────────────────────

class AccessGrant(BaseModel):
    grant_id:       str
    principal:      Principal
    permissions:    set[Permission]
    is_owner:       bool = False


# ── Aggregate root — one document per protected resource ──────────────────────

class ResourcePolicy(BaseModel):
    account_id:  str
    resource_id: str
    grants:      list[AccessGrant] = Field(default_factory=list)

    # ── Domain behaviour ──────────────────────────────────────────────────────

    def claim(self, user_id: str) -> Result["ResourcePolicy", XoloException]:
        """Attempt to become exclusive owner.
        Idempotent if the caller is already the owner."""
        owner = self._find_grant(user_id)
        if owner and owner.is_owner:
            return Ok(self)

        existing_owner = next((g for g in self.grants if g.is_owner), None)
        if existing_owner:
            return Err(ConflictError(
                "Resource is already owned by another principal",
                metadata={"resource_id": self.resource_id, "owner": existing_owner.principal.id},
            ))

        grant = AccessGrant(
            grant_id   = f"ag-{generate(size=10)}",
            principal  = Principal(type=PrincipalType.USER, id=user_id),
            permissions= {Permission.MANAGE, Permission.READ, Permission.WRITE, Permission.DELETE},
            is_owner   = True,
        )
        return Ok(self.model_copy(update={"grants": self.grants + [grant]}))

    def grant(
        self,
        principal:           Principal,
        permissions:         set[Permission],
        caller_principal_ids: list[str],
    ) -> Result["ResourcePolicy", XoloException]:
        """Grant permissions to a principal. Caller must hold MANAGE."""
        caller_perms = self.effective_permissions(caller_principal_ids)
        if Permission.MANAGE not in caller_perms:
            return Err(AccessDeniedError("You do not have permission to share this resource"))

        existing = self._find_grant(principal.id)
        if existing:
            merged = existing.model_copy(update={"permissions": existing.permissions | permissions})
            new_grants = [merged if g.grant_id == existing.grant_id else g for g in self.grants]
        else:
            new_grant = AccessGrant(
                grant_id   = f"ag-{generate(size=10)}",
                principal  = principal,
                permissions= permissions,
                is_owner   = False,
            )
            new_grants = self.grants + [new_grant]

        return Ok(self.model_copy(update={"grants": new_grants}))

    def revoke(
        self,
        principal_id:        str,
        permissions:         set[Permission],
        caller_id:           str,
        caller_principal_ids: list[str],
    ) -> Result["ResourcePolicy", XoloException]:
        """Remove permissions from a principal.
        Caller may self-revoke or must hold MANAGE.
        The last owner's MANAGE permission cannot be removed."""
        is_self = caller_id == principal_id
        if not is_self:
            caller_perms = self.effective_permissions(caller_principal_ids)
            if Permission.MANAGE not in caller_perms:
                return Err(AccessDeniedError("You do not have permission to revoke this access"))

        existing = self._find_grant(principal_id)
        if not existing:
            return Ok(self)

        if Permission.MANAGE in permissions and existing.is_owner:
            owner_count = sum(1 for g in self.grants if g.is_owner)
            if owner_count <= 1:
                return Err(ConflictError(
                    "Cannot remove the last owner of the resource",
                    metadata={"resource_id": self.resource_id},
                ))

        remaining = existing.permissions - permissions
        if remaining:
            updated = existing.model_copy(update={"permissions": remaining})
            new_grants = [updated if g.grant_id == existing.grant_id else g for g in self.grants]
        else:
            new_grants = [g for g in self.grants if g.grant_id != existing.grant_id]

        return Ok(self.model_copy(update={"grants": new_grants}))

    def check(self, principal_ids: list[str], required: set[Permission]) -> bool:
        """Return True only if required ⊆ union of all matching grants' permissions."""
        return required.issubset(self.effective_permissions(principal_ids))

    def effective_permissions(self, principal_ids: list[str]) -> set[Permission]:
        granted: set[Permission] = set()
        for g in self.grants:
            if g.principal.id in principal_ids:
                granted |= g.permissions
        return granted

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_grant(self, principal_id: str) -> Optional[AccessGrant]:
        return next((g for g in self.grants if g.principal.id == principal_id), None)


# ── Aggregate root — security group ──────────────────────────────────────────

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


# ── Group membership record (kept in separate collection for scalability) ─────

class GroupMember(BaseModel):
    account_id: str
    group_id:   str
    user_id:    str
    joined_at:  datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
