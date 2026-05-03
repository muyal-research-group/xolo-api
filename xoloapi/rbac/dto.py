from typing import Optional
from pydantic import BaseModel


class CreateRoleDTO(BaseModel):
    name:        str
    description: Optional[str] = None
    permissions: list[str] = []


class UpdateRoleDTO(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None


class PermissionDTO(BaseModel):
    permission: str


class ParentRoleDTO(BaseModel):
    parent_role_id: str


class AssignRoleDTO(BaseModel):
    subject_id: str
    role_id:    str


class UnassignRoleDTO(BaseModel):
    subject_id: str
    role_id:    str


class CheckPermissionDTO(BaseModel):
    subject_id:  str
    permission:  str


# ── Response DTOs ─────────────────────────────────────────────────────────────

class RoleDTO(BaseModel):
    role_id:         str
    name:            str
    description:     Optional[str]
    permissions:     list[str]
    parent_role_ids: list[str]


class AssignmentDTO(BaseModel):
    assignment_id: str
    subject_id:    str
    role_id:       str


class CheckResultDTO(BaseModel):
    subject_id:  str
    permission:  str
    has_access:  bool


class EffectivePermissionsDTO(BaseModel):
    subject_id:  str
    permissions: list[str]
