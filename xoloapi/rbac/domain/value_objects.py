"""RBAC value objects.

Permission format: "resource_type:action"  e.g. "document:read", "report:*", "*:*"
Wildcards are supported: "*" in resource_type or action matches any value.
"""
from enum import Enum
from pydantic import BaseModel


class RBACPermission(BaseModel):
    """Immutable permission token with wildcard matching.

    Examples: "document:read", "report:*", "*:*"
    """
    model_config = {"frozen": True}

    resource_type: str
    action: str

    @classmethod
    def from_string(cls, s: str) -> "RBACPermission":
        parts = s.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format '{s}' — expected 'resource_type:action'")
        return cls(resource_type=parts[0], action=parts[1])

    def to_string(self) -> str:
        return f"{self.resource_type}:{self.action}"

    def matches(self, required: "RBACPermission") -> bool:
        """Return True if self grants the required permission (wildcard-aware)."""
        rt_match = self.resource_type == "*" or self.resource_type == required.resource_type
        ac_match = self.action == "*" or self.action == required.action
        return rt_match and ac_match

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"RBACPermission({self.to_string()!r})"
