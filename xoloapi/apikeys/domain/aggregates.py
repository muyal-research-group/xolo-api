import datetime
from typing import Optional
from pydantic import BaseModel, Field
from xoloapi.apikeys.domain.value_objects import APIKeyScope


class APIKey(BaseModel):
    key_id:       str
    key_hash:     str                    # sha256 of raw key — never the raw key
    key_prefix:   str                    # first 16 chars for display (e.g. "xolo_acl_4xK9mP")
    account_id:   str
    name:         str
    scopes:       list[APIKeyScope]
    created_by:   str                    # sha256 of the admin token that created this key
    is_active:    bool = True
    created_at:   datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    expires_at:   Optional[datetime.datetime] = None
    last_used_at: Optional[datetime.datetime] = None

    # ── Domain behaviour ──────────────────────────────────────────────────────

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at is not None:
            now = datetime.datetime.now(datetime.timezone.utc)
            if self.expires_at.tzinfo is None:
                expires = self.expires_at.replace(tzinfo=datetime.timezone.utc)
            else:
                expires = self.expires_at
            if now > expires:
                return False
        return True

    def allows(self, scope: str) -> bool:
        return (
            APIKeyScope.ALL in self.scopes
            or APIKeyScope(scope) in self.scopes
        )

    def revoke(self) -> "APIKey":
        return self.model_copy(update={"is_active": False})

    def rotate(self, new_hash: str, new_prefix: str) -> "APIKey":
        return self.model_copy(update={
            "key_hash":     new_hash,
            "key_prefix":   new_prefix,
            "last_used_at": None,
        })
