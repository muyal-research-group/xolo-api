"""DTOs for the ACL module.

Response shapes are kept identical to the existing controller so existing
clients require no changes. Request shapes mirror commonx.dto.xolo originals.
"""
from typing import Generic, List, Optional, Set, TypeVar
from pydantic import BaseModel, Field

from xoloapi.acl.domain.value_objects import Permission, PrincipalType

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
    principal_id:   Optional[str] = None
    principal_username: Optional[str] = None
    principal_identifier: Optional[str] = None
    principal_type: Optional[PrincipalType] = None
    resource_id:    str
    permissions:    List[Permission]


class CheckDTO(BaseModel):
    resource_id:    str
    permissions:    List[Permission]
    principal_id:   Optional[str] = None  # if omitted → defaults to the authenticated caller
    principal_username: Optional[str] = None
    principal_identifier: Optional[str] = None
    principal_type: Optional[PrincipalType] = None


class ServiceClaimResourceDTO(BaseModel):
    resource_id: str
    owner_id: str
    owner_type: PrincipalType = PrincipalType.USER


class ServiceCreateGroupDTO(BaseModel):
    name: str
    owner_id: str
    description: Optional[str] = ""


class TransferResourceOwnerDTO(BaseModel):
    principal_id: Optional[str] = None
    owner_identifier: Optional[str] = None
    principal_type: PrincipalType = PrincipalType.USER
    keep_previous_permissions: Optional[List[Permission]] = None


class CreateResourceDTO(BaseModel):
    resource_id: str
    owner_type: PrincipalType = PrincipalType.USER
    owner_identifier: str


class DeleteResourcePolicyDTO(BaseModel):
    confirm_resource_id: str


class UpdateResourceGrantDTO(BaseModel):
    permissions: List[Permission] = Field(min_length=1)


class ACLEffectiveAccessDTO(BaseModel):
    username: str
    user_id: str
    resource_id: str
    direct_permissions: Set[str]
    group_permissions: dict[str, Set[str]]
    ignored_disabled_groups: List[str]
    is_owner: bool
    effective_permissions: Set[str]
    allowed: bool
    denial_reason: Optional[str] = None


class TransferGroupOwnerDTO(BaseModel):
    user_id: str
    keep_previous_as_member: bool = True


class CreateGroupDTO(BaseModel):
    name:        str
    description: Optional[str] = ""


class MembersDTO(BaseModel):
    members: List[str] = Field(default_factory=list)
    usernames: List[str] = Field(default_factory=list)


# ── Response DTOs (match existing JSON shapes exactly) ────────────────────────

class GroupDetailDTO(BaseModel):
    id:      str
    name:    str
    my_role: str


class ResourceDetailDTO(BaseModel):
    resource_id:   str
    access_source: str
    permissions:   Set[str]


class EffectiveAccessDTO(BaseModel):
    user_id: str
    resource_id: str
    is_owner: bool
    permissions: Set[str]
    group_ids: List[str]


class ServiceResourceDetailDTO(BaseModel):
    resource_id: str
    permissions: Set[str]
    is_owner: bool
    access_group_ids: List[str]


class ResourceGrantDTO(BaseModel):
    grant_id: str
    principal_id: str
    principal_type: str
    principal_name: Optional[str] = None
    permissions: Set[str]
    is_owner: bool


class ResourceGrantsDTO(BaseModel):
    resource_id: str
    grants: List[ResourceGrantDTO]


class UserResourcesDTO(BaseModel):
    user_id:          str
    groups:           List[GroupDetailDTO]
    owned_resources:  PaginatedDTO[ResourceDetailDTO]
    shared_resources: PaginatedDTO[ResourceDetailDTO]


class ServiceUserResourcesDTO(BaseModel):
    user_id: str
    groups: List[GroupDetailDTO]
    owned_resources: PaginatedDTO[ServiceResourceDetailDTO]
    shared_resources: PaginatedDTO[ServiceResourceDetailDTO]


class GroupMembershipDTO(BaseModel):
    user_id:   str
    group_id:  str
    is_member: bool
