from commonx.dto.xolo import (
    AssignLicenseDTO,
    AssignLicenseResponseDTO,
    DeleteLicenseDTO,
    DeletedLicenseResponseDTO,
    SelfDeleteLicenseDTO,
)
from pydantic import BaseModel, ConfigDict


class LicenseSummaryDTO(BaseModel):
    username: str
    scope: str
    expires_at: str


class RotateLicenseDTO(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    username: str
    scope: str
    expires_in: str


__all__ = [
    "AssignLicenseDTO",
    "AssignLicenseResponseDTO",
    "DeleteLicenseDTO",
    "DeletedLicenseResponseDTO",
    "LicenseSummaryDTO",
    "RotateLicenseDTO",
    "SelfDeleteLicenseDTO",
]
