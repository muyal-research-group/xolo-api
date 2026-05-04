from commonx.dto.xolo import (
    AssignLicenseDTO,
    AssignLicenseResponseDTO,
    DeleteLicenseDTO,
    DeletedLicenseResponseDTO,
    SelfDeleteLicenseDTO,
)
from pydantic import BaseModel


class LicenseSummaryDTO(BaseModel):
    username: str
    scope: str
    expires_at: str

__all__ = [
    "AssignLicenseDTO",
    "AssignLicenseResponseDTO",
    "DeleteLicenseDTO",
    "DeletedLicenseResponseDTO",
    "LicenseSummaryDTO",
    "SelfDeleteLicenseDTO",
]
