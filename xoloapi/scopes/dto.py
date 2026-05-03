from commonx.dto.xolo import (
    AssignScopeDTO,
    AssignedScopeResponseDTO,
    CreateScopeDTO,
    CreatedScopeResponseDTO,
)
from pydantic import BaseModel


class ScopeAssignmentDTO(BaseModel):
    name: str
    username: str

__all__ = [
    "AssignScopeDTO",
    "AssignedScopeResponseDTO",
    "CreateScopeDTO",
    "CreatedScopeResponseDTO",
    "ScopeAssignmentDTO",
]
