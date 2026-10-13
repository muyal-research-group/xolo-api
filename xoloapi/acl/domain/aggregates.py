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
            permissions= set(Permission),
            is_owner   = True,
        )
        return Ok(self.model_copy(update={"grants": self.grants + [grant]}))

    def claim_principal(self, principal: Principal) -> Result["ResourcePolicy", XoloException]:
        """Claim an unowned resource for a user or group principal."""
        existing = self._find_grant(principal.id)
        if existing and existing.is_owner:
            normalized = existing.model_copy(update={"permissions": set(Permission)})
            return Ok(self.model_copy(update={
                "grants": [normalized if g.grant_id == existing.grant_id else g for g in self.grants]
            }))

        current_owner = next((g for g in self.grants if g.is_owner), None)
        if current_owner:
            return Err(ConflictError(
                "Resource is already owned by another principal",
                metadata={"resource_id": self.resource_id, "owner": current_owner.principal.id},
            ))

        owner_grant = AccessGrant(
            grant_id=f"ag-{generate(size=10)}",
            principal=principal,
            permissions=set(Permission),
            is_owner=True,
        )
        return Ok(self.model_copy(update={"grants": self.grants + [owner_grant]}))

    def transfer_owner(
        self,
        principal: Principal,
        keep_previous_permissions: set[Permission] | None = None,
    ) -> Result["ResourcePolicy", XoloException]:
        """Replace the sole owner while optionally retaining the old grant."""
        current_owner = next((g for g in self.grants if g.is_owner), None)
        if current_owner is None:
            return Err(NotFoundError("Resource owner", self.resource_id))

        new_grants: list[AccessGrant] = []
        for grant in self.grants:
            if grant.grant_id == current_owner.grant_id:
                if grant.principal == principal:
                    new_grants.append(grant.model_copy(update={"permissions": set(Permission), "is_owner": True}))
                elif keep_previous_permissions:
                    new_grants.append(grant.model_copy(update={
                        "permissions": keep_previous_permissions,
                        "is_owner": False,
                    }))
                continue
            if grant.principal == principal:
                continue
            new_grants.append(grant)

        if current_owner.principal != principal:
            new_grants.append(AccessGrant(
                grant_id=f"ag-{generate(size=10)}",
                principal=principal,
                permissions=set(Permission),
                is_owner=True,
            ))
        return Ok(self.model_copy(update={"grants": new_grants}))

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
                granted |= set(Permission) if g.is_owner else g.permissions
        return granted

    def is_owned_by_any(self, principal_ids: list[str]) -> bool:
        return any(g.is_owner and g.principal.id in principal_ids for g in self.grants)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_grant(self, principal_id: str) -> Optional[AccessGrant]:
        return next((g for g in self.grants if g.principal.id == principal_id), None)
