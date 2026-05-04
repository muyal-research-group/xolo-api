from __future__ import annotations
import datetime as DT
from typing import Dict, List
from pydantic import BaseModel, Field

from xoloapi.ngac.domain.value_objects import NodeType


class NGACNode(BaseModel):
    account_id: str
    node_id:    str
    node_type:  NodeType
    name:       str
    properties: Dict[str, str] = Field(default_factory=dict)
    owner_id:   str = ""
    created_at: DT.datetime = Field(
        default_factory=lambda: DT.datetime.now(DT.timezone.utc)
    )


class NGACAssignment(BaseModel):
    """Directed edge: from_id (child) → to_id (parent)."""
    account_id:    str
    assignment_id: str
    from_id:       str
    to_id:         str
    owner_id:      str = ""
    created_at:    DT.datetime = Field(
        default_factory=lambda: DT.datetime.now(DT.timezone.utc)
    )


class NGACAssociation(BaseModel):
    """Permission edge: UA grants a set of operations on an OA."""
    account_id:           str
    association_id:      str
    user_attribute_id:   str
    object_attribute_id: str
    operations:          List[str]
    owner_id:            str = ""
    created_at:          DT.datetime = Field(
        default_factory=lambda: DT.datetime.now(DT.timezone.utc)
    )
