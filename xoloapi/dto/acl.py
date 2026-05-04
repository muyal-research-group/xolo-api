# xoloapi/dto/acl.py
from typing import Dict,Set,Optional,List,Generic,TypeVar
from pydantic import BaseModel

# from xoloapi.models import PaginatedResponseDTO
    
T = TypeVar("T")
class PaginatedResponseDTO(BaseModel, Generic[T]):
    items: List[T]
    total_count: int
    page: int
    page_size: int
    total_pages: int

class DashboardFilterDTO(BaseModel):
    page: int = 1
    page_size: int = 10
    
class CheckDTO(BaseModel):
    resource_id:str
    permissions:List[str]
    
class GrantsDTO(BaseModel):
    grants:Dict[str,Dict[str,Set]]
    role:Optional[str]=""


class GroupDetailDTO(BaseModel):
    id:str
    name:str
    my_role:str

class ResourceDetailDTO(BaseModel):
    resource_id:str
    access_source:str
    permissions:Set[str]
    # Dict[str,Set[str]]  # principal_id -> set of permissions

class UserDashboardViewDTO(BaseModel):
    user_id: str
    groups: List[GroupDetailDTO]
    owned_resources: PaginatedResponseDTO[ResourceDetailDTO] # Updated type
    shared_resources: PaginatedResponseDTO[ResourceDetailDTO] # Updated type

class AddOrDeleteMembersToGroupDTO(BaseModel):
    members:List[str]

class GrantOrRevokePermissionDTO(BaseModel):
    principal_id:str
    principal_type:Optional[str]= None  # "user" | "group"
    resource_id:str
    permissions:List[str]

class ClaimResourceDTO(BaseModel):
    resource_id:str
    # is_owner:bool = False