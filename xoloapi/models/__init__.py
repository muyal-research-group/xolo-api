#xoloapi/models/__init__.py
from pydantic import BaseModel,EmailStr,Field
from typing import Optional,List,TypeVar,Generic,Dict
import datetime as DateTime
import xoloapi.enums as Enums
# from enum import Enum
class TimestampMixin(BaseModel):
    """
    A reusable helper. Any class that inherits from this
    will automatically get 'created_at' and 'updated_at' fields.
    """
    created_at:DateTime.datetime = Field(default_factory=lambda: DateTime.datetime.now(DateTime.timezone.utc))
    updated_at:DateTime.datetime = Field(default_factory=lambda: DateTime.datetime.now(DateTime.timezone.utc))



class LicenseAssignedModel(BaseModel):
    username: str
    license: str
    scope: str 
    expires_at:str



class User(BaseModel):
    profile_photo:Optional[str] =  None
    key:str
    first_name:str
    last_name:str
    username:str
    email:EmailStr
    hash_password:str
    # role:str
    disabled:Optional[bool] = False

class SecurityGroup(TimestampMixin):
    """
    Represents the Group entity itself (Metadata).
    """
    # id: str = Field(alias="_id", default_factory=str)
    group_id: str
    name: str
    owner_id: str # The user who owns/manages this group
    description: Optional[str] = None

class GroupMember(TimestampMixin):
    """
    The Join Table / Link Collection.
    Maps User <-> Group.
    """
    # id: Optional[str] = Field(alias="_id", default=None)
    group_id: str
    user_id: str
    
    # Optional: Role *within* the group (e.g., "Member" vs "Moderator")
    role_in_group: str = "member" 

    # class Config:
        # populate_by_name = True

class AccessPolicy(BaseModel):
    """
    The permission assignment.
    """
    # id: Optional[str] = Field(alias="_id", default=None)
    resource_id: str
    principal_id: str # Can be UserID or GroupID
    principal_type: Enums.PrincipalType 
    permissions: List[Enums.Permission]
    is_owner: bool = False


class ScopeModel(BaseModel):
    name: str

class ScopeUserModel(BaseModel):
    name:str
    username:str
