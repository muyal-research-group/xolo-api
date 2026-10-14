from typing import Any, ClassVar

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = "XOLO.ERROR"
    message: str = "Request failed"
    status_code: int = 500
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_error: str | None = None


class XoloError(Exception):
    code: ClassVar[str] = "XOLO.ERROR"
    status_code: ClassVar[int] = 500
    default_message: ClassVar[str] = "Request failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        raw_error: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        resolved_message = message or self.default_message
        super().__init__(resolved_message)
        self.message = resolved_message
        self.metadata = metadata or {}
        self.raw_error = raw_error
        self.headers = headers or {}

    @property
    def detail(self) -> ErrorDetail:
        return ErrorDetail(
            code=self.code,
            message=self.message,
            status_code=self.status_code,
            metadata=self.metadata,
            raw_error=self.raw_error,
        )

    @classmethod
    def from_exception(cls, exc: Exception) -> "XoloError":
        if isinstance(exc, XoloError):
            return exc
        return InternalError(
            str(exc) or InternalError.default_message,
            metadata={"exception_type": exc.__class__.__name__},
            raw_error=str(exc),
        )

    @classmethod
    def from_http_response(
        cls,
        *,
        status_code: int,
        detail: Any,
        headers: dict[str, Any] | None = None,
    ) -> "XoloError":
        if isinstance(detail, dict):
            return cls.from_code(
                code=detail.get("code"),
                message=detail.get("message") or detail.get("msg") or detail.get("detail"),
                metadata=detail.get("metadata"),
                raw_error=detail.get("raw_error"),
                headers=headers,
                status_code=detail.get("status_code") or detail.get("http_status") or status_code,
            )

        message = str(detail) if detail not in (None, "") else None
        return cls.from_status(
            status_code=status_code,
            message=message,
            raw_error=message,
            headers=headers,
        )

    @classmethod
    def from_status(
        cls,
        *,
        status_code: int,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        raw_error: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> "XoloError":
        error_cls = STATUS_TO_ERROR.get(status_code, InternalError)
        return error_cls(
            message,
            metadata=metadata,
            raw_error=raw_error,
            headers=headers,
        )

    @classmethod
    def from_code(
        cls,
        *,
        code: str | int | None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        raw_error: str | None = None,
        headers: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> "XoloError":
        normalized_code = cls._normalize_code(code)
        if normalized_code is not None and normalized_code in CODE_TO_ERROR:
            error_cls = CODE_TO_ERROR[normalized_code]
            return error_cls(
                message,
                metadata=metadata,
                raw_error=raw_error,
                headers=headers,
            )

        if isinstance(code, int):
            return cls.from_status(
                status_code=code,
                message=message,
                metadata=metadata,
                raw_error=raw_error,
                headers=headers,
            )

        if status_code is not None:
            return cls.from_status(
                status_code=status_code,
                message=message,
                metadata=metadata,
                raw_error=raw_error,
                headers=headers,
            )

        return InternalError(
            message,
            metadata=metadata,
            raw_error=raw_error,
            headers=headers,
        )

    @staticmethod
    def _normalize_code(code: str | int | None) -> str | None:
        if code is None or isinstance(code, int):
            return None

        normalized = code.strip().upper()
        alias_map = {
            "X.UNKNOWN": "XOLO.INTERNAL_ERROR",
            "X.ERROR": "XOLO.INTERNAL_ERROR",
            "X.UNAUTHORIZED": "XOLO.UNAUTHORIZED",
            "X.ACCESS_DENIED": "XOLO.ACCESS_DENIED",
            "X.NOT_FOUND": "XOLO.NOT_FOUND",
            "X.ALREADY_EXISTS": "XOLO.ALREADY_EXISTS",
            "X.SERVER_ERROR": "XOLO.INTERNAL_ERROR",
            "X.INVALID_LICENSE": "XOLO.INVALID_LICENSE",
        }
        return alias_map.get(normalized, normalized)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class NotFoundError(XoloError):
    code = "XOLO.NOT_FOUND"
    status_code = 404
    default_message = "Resource not found"


class AlreadyExistsError(XoloError):
    code = "XOLO.ALREADY_EXISTS"
    status_code = 409
    default_message = "Resource already exists"


class ConflictError(XoloError):
    code = "XOLO.CONFLICT"
    status_code = 409
    default_message = "Request conflicts with current state"


class UnauthorizedError(XoloError):
    code = "XOLO.UNAUTHORIZED"
    status_code = 401
    default_message = "Unauthorized"


class AccessDeniedError(XoloError):
    code = "XOLO.ACCESS_DENIED"
    status_code = 403
    default_message = "Access denied"


class ValidationError(XoloError):
    code = "XOLO.VALIDATION_ERROR"
    status_code = 422
    default_message = "Validation failed"


class InvalidLicenseError(XoloError):
    code = "XOLO.INVALID_LICENSE"
    status_code = 401
    default_message = "Invalid license"


class DatabaseError(XoloError):
    code = "XOLO.DATABASE_ERROR"
    status_code = 500
    default_message = "Database operation failed"


class InternalError(XoloError):
    code = "XOLO.INTERNAL_ERROR"
    status_code = 500
    default_message = "Internal server error"


CODE_TO_ERROR = {
    NotFoundError.code: NotFoundError,
    AlreadyExistsError.code: AlreadyExistsError,
    ConflictError.code: ConflictError,
    UnauthorizedError.code: UnauthorizedError,
    AccessDeniedError.code: AccessDeniedError,
    ValidationError.code: ValidationError,
    InvalidLicenseError.code: InvalidLicenseError,
    DatabaseError.code: DatabaseError,
    InternalError.code: InternalError,
}

STATUS_TO_ERROR = {
    400: ValidationError,
    401: UnauthorizedError,
    403: AccessDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    500: InternalError,
}


# Backward-compatible aliases for older imports.
XError = XoloError
NotFound = NotFoundError
AlreadyExists = AlreadyExistsError
Unauthorized = UnauthorizedError
AccessDenied = AccessDeniedError
ServerError = InternalError
InvalidLicense = InvalidLicenseError


__all__ = [
    "ErrorDetail",
    "XoloError",
    "XError",
    "NotFoundError",
    "AlreadyExistsError",
    "ConflictError",
    "UnauthorizedError",
    "AccessDeniedError",
    "ValidationError",
    "InvalidLicenseError",
    "DatabaseError",
    "InternalError",
    "NotFound",
    "AlreadyExists",
    "Unauthorized",
    "AccessDenied",
    "ServerError",
    "InvalidLicense",
]
