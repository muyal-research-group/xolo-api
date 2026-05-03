"""DTOs for the ACL module.

Response shapes are kept identical to the existing controller so existing
clients require no changes. Request shapes mirror commonx.dto.xolo originals.
"""
from typing import Generic, List, Optional, Set, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


# ── Shared ────────────────────────────────────────────────────────────────────

class PaginatedDTO(BaseModel, Generic[T]):
    items:       List[T]
    total_count: int
    page:        int
    page_size:   int
    total_pages: int


# ── Request DTOs ──────────────────────────────────────────────────────────────

class ClaimResourceDTO(BaseModel):
    resource_id: str


class GrantOrRevokeDTO(BaseModel):
    principal_id:   str
    principal_type: Optional[str] = None   # "USER" | "GROUP"
    resource_id:    str
    permissions:    List[str]


class CheckDTO(BaseModel):
    resource_id: str
    permissions: List[str]


class CreateGroupDTO(BaseModel):
    name:        str
    description: Optional[str] = ""


class MembersDTO(BaseModel):
    members: List[str]


# ── Response DTOs (match existing JSON shapes exactly) ────────────────────────

class GroupDetailDTO(BaseModel):
    id:      str
    name:    str
    my_role: str


class ResourceDetailDTO(BaseModel):
    resource_id:   str
    access_source: str
    permissions:   Set[str]


class UserResourcesDTO(BaseModel):
    user_id:          str
    groups:           List[GroupDetailDTO]
    owned_resources:  PaginatedDTO[ResourceDetailDTO]
    shared_resources: PaginatedDTO[ResourceDetailDTO]
