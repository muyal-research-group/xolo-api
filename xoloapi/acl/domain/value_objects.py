from enum import Enum
from pydantic import BaseModel


class PrincipalType(str, Enum):
    USER  = "USER"
    GROUP = "GROUP"


class Permission(str, Enum):
    READ   = "read"
    WRITE  = "write"
    DELETE = "delete"
    MANAGE = "sys:manage"


class Principal(BaseModel):
    """Frozen value object — equality by type + id."""
    type: PrincipalType
    id:   str

    model_config = {"frozen": True}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Principal):
            return False
        return self.type == other.type and self.id == other.id

    def __hash__(self) -> int:
        return hash((self.type, self.id))
