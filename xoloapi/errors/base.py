from typing import Any
from pydantic import BaseModel
from fastapi import HTTPException


class ErrorDetail(BaseModel):
    code:        str
    message:     str
    status_code: int
    metadata:    dict[str, Any] = {}


class XoloException(Exception):
    """Base exception for all Xolo domain and infrastructure errors.

    Subclasses declare `code` and `status_code` as class-level attributes.
    All service and repository methods must return Result[T, XoloException]
    and never raise. Controllers call .to_http_exception() to convert.

    Example::

        class MyService:
            async def get(self, id: str) -> Result[Thing, XoloException]:
                item = await self.repo.find(id)
                if item.is_none:
                    return Err(NotFoundError("Thing", id))
                return Ok(item.unwrap())

        # In controller:
        result = await service.get(id)
        if result.is_err:
            raise result.unwrap_err().to_http_exception()
        return result.unwrap()
    """

    code:        str = "XOLO.ERROR"
    status_code: int = 500

    def __init__(self, message: str, metadata: dict[str, Any] | None = None):
        super().__init__(message)
        self.message  = message
        self.metadata = metadata or {}

    @property
    def detail(self) -> ErrorDetail:
        return ErrorDetail(
            code        = self.code,
            message     = self.message,
            status_code = self.status_code,
            metadata    = self.metadata,
        )

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code = self.status_code,
            detail      = self.detail.model_dump(),
        )

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, "
            f"message={self.message!r}, "
            f"status_code={self.status_code})"
        )


# ── 4xx client errors ─────────────────────────────────────────────────────────

class NotFoundError(XoloException):
    """Resource was not found (404)."""
    code        = "XOLO.NOT_FOUND"
    status_code = 404

    def __init__(self, resource: str, identifier: str | None = None):
        msg = f"{resource} not found"
        if identifier:
            msg += f": '{identifier}'"
        super().__init__(msg, metadata={"resource": resource, "id": identifier})


class AlreadyExistsError(XoloException):
    """Resource already exists (409)."""
    code        = "XOLO.ALREADY_EXISTS"
    status_code = 409

    def __init__(self, resource: str, identifier: str | None = None):
        msg = f"{resource} already exists"
        if identifier:
            msg += f": '{identifier}'"
        super().__init__(msg, metadata={"resource": resource, "id": identifier})


class ConflictError(XoloException):
    """Generic business-rule conflict (409)."""
    code        = "XOLO.CONFLICT"
    status_code = 409

    def __init__(self, message: str, metadata: dict[str, Any] | None = None):
        super().__init__(message, metadata=metadata)


class UnauthorizedError(XoloException):
    """Missing or invalid credentials (401)."""
    code        = "XOLO.UNAUTHORIZED"
    status_code = 401

    def __init__(self, message: str = "Unauthorized", metadata: dict[str, Any] | None = None):
        super().__init__(message, metadata=metadata)


class AccessDeniedError(XoloException):
    """Authenticated but insufficient permissions (403)."""
    code        = "XOLO.ACCESS_DENIED"
    status_code = 403

    def __init__(self, message: str = "Access denied", metadata: dict[str, Any] | None = None):
        super().__init__(message, metadata=metadata)


class InactiveUserError(AccessDeniedError):
    """Authenticated user is blocked or disabled (403)."""
    code = "XOLO.INACTIVE_USER"

    def __init__(self, user_id: str | None = None):
        super().__init__(
            "Inactive user",
            metadata={"user_id": user_id} if user_id else None,
        )


class ValidationError(XoloException):
    """Input failed domain validation (422)."""
    code        = "XOLO.VALIDATION_ERROR"
    status_code = 422

    def __init__(self, message: str, field: str | None = None):
        meta = {"field": field} if field else {}
        super().__init__(message, metadata=meta)


# ── 5xx server errors ─────────────────────────────────────────────────────────

class DatabaseError(XoloException):
    """MongoDB / persistence layer failure (500)."""
    code        = "XOLO.DATABASE_ERROR"
    status_code = 500

    def __init__(self, message: str = "Database operation failed", cause: Exception | None = None):
        meta = {"cause": str(cause)} if cause else {}
        super().__init__(message, metadata=meta)


class InternalError(XoloException):
    """Unexpected server-side error (500)."""
    code        = "XOLO.INTERNAL_ERROR"
    status_code = 500

    def __init__(self, message: str = "Internal server error", cause: Exception | None = None):
        meta = {"cause": str(cause)} if cause else {}
        super().__init__(message, metadata=meta)


__all__ = [
    "ErrorDetail",
    "XoloException",
    "NotFoundError",
    "AlreadyExistsError",
    "ConflictError",
    "UnauthorizedError",
    "AccessDeniedError",
    "InactiveUserError",
    "ValidationError",
    "DatabaseError",
    "InternalError",
]
