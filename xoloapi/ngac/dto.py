import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from xoloapi.ngac.domain.value_objects import NodeType


class CreateNodeDTO(BaseModel):
    name:       str
    node_type:  NodeType
    properties: Dict[str, str] = {}
    user_id: Optional[str] = None
    user_identifier: Optional[str] = None
    resource_id: Optional[str] = None


class UpdateNodeDTO(BaseModel):
    name:       Optional[str] = None
    properties: Optional[Dict[str, str]] = None
    user_id: Optional[str] = None
    user_identifier: Optional[str] = None
    resource_id: Optional[str] = None


class AssignDTO(BaseModel):
    """Assign from_id (child) into to_id (parent)."""
    from_id: str
    to_id:   str


class RemoveAssignmentDTO(BaseModel):
    from_id: str
    to_id:   str


class AssociateDTO(BaseModel):
    """Grant a UserAttribute a set of operations on an ObjectAttribute."""
    user_attribute_id:   str
    object_attribute_id: str
    operations:          List[str]


class UpdateAssociationDTO(BaseModel):
    operations: List[str]


class CheckAccessDTO(BaseModel):
    user_id:   str
    object_id: str
    operation: str


class NGACDecisionDTO(BaseModel):
    allowed:   bool
    reason:    str
    user_id:   str
    object_id: str
    operation: str
    governing_policy_classes: List[dict] = []
    successful_paths: List[dict] = []
    failed_classes: List[dict] = []
    matching_associations: List[dict] = []


# ── Response DTOs ─────────────────────────────────────────────────────────────

class NGACNodeResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id:    str
    node_type:  NodeType
    name:       str
    properties: Dict[str, str] = {}
    owner_id:   str = ""
    user_id: Optional[str] = None
    username: Optional[str] = None
    resource_id: Optional[str] = None
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None


class NGACAssignmentResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: str
    from_id:       str
    to_id:         str
    owner_id:      str = ""
    created_at:    datetime.datetime


class NGACAssociationResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    association_id:      str
    user_attribute_id:   str
    object_attribute_id: str
    operations:          List[str]
    owner_id:            str = ""
    created_at:          datetime.datetime
