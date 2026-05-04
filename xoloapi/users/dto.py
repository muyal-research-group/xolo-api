from commonx.dto.xolo import (
    AuthDTO,
    AuthenticatedDTO,
    CreateUserDTO,
    CreatedUserResponseDTO,
    EnableOrDisableUserDTO,
    LogoutDTO,
    SignUpDTO,
    UpdateUserPasswordDTO,
    UpdateUserPasswordResponseDTO,
    UserDTO,
    VerifyDTO,
)
from pydantic import BaseModel


class PasswordRecoveryRequestDTO(BaseModel):
    identifier: str


class PasswordRecoveryConfirmDTO(BaseModel):
    token: str
    password: str


class DeleteUserDTO(BaseModel):
    username: str

__all__ = [
    "AuthDTO",
    "AuthenticatedDTO",
    "CreateUserDTO",
    "CreatedUserResponseDTO",
    "EnableOrDisableUserDTO",
    "DeleteUserDTO",
    "LogoutDTO",
    "SignUpDTO",
    "PasswordRecoveryRequestDTO",
    "PasswordRecoveryConfirmDTO",
    "UpdateUserPasswordDTO",
    "UpdateUserPasswordResponseDTO",
    "UserDTO",
    "VerifyDTO",
]
