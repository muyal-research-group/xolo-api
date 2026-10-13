# Error handling

Every `XoloClient` method returns `Result[T, XoloError]` — a typed container that holds
either a successful value or a typed error, and never raises.

## The `Result` type

```python
from option import Ok, Err, Result
```

| Member | Type | Description |
|--------|------|-------------|
| `.is_ok` | `bool` | `True` when the call succeeded |
| `.is_err` | `bool` | `True` when the call failed |
| `.unwrap()` | `T` | Returns the value; raises if `Err` |
| `.unwrap_err()` | `XoloError` | Returns the error; raises if `Ok` |

## Basic patterns

### Guard clause (recommended)

```python
result = client.get_role(
    role_id="r1",
    token=access_token,
    temporal_secret=temporal_secret,
)

if not result.is_ok:
    err = result.unwrap_err()
    print(err.code, err.message)
else:
    role = result.unwrap()
    print(role.name)
```

### Assert and unwrap (tests / scripts)

```python
result = client.create_role(name="reader", ...)
assert result.is_ok, result.unwrap_err()
role = result.unwrap()
```

### Inline unwrap (when failure is unexpected)

```python
# Raises SomeException if the result is Err
role = client.get_role(...).unwrap()
```

## Error classes

All errors inherit from `XoloError` and live in `xolo.client.errors`.

| Class | Code | HTTP Status | Meaning |
|-------|------|-------------|---------|
| `XoloError` | `XOLO.ERROR` | 500 | Base class / unknown error |
| `NotFoundError` | `XOLO.NOT_FOUND` | 404 | Resource does not exist |
| `AlreadyExistsError` | `XOLO.ALREADY_EXISTS` | 409 | Resource already exists |
| `ConflictError` | `XOLO.CONFLICT` | 409 | Request conflicts with current state |
| `UnauthorizedError` | `XOLO.UNAUTHORIZED` | 401 | Missing or invalid credentials |
| `AccessDeniedError` | `XOLO.ACCESS_DENIED` | 403 | Authenticated but not permitted |
| `ValidationError` | `XOLO.VALIDATION_ERROR` | 422 | Request body failed validation |
| `InvalidLicenseError` | `XOLO.INVALID_LICENSE` | 401 | License missing, expired, or wrong scope |
| `DatabaseError` | `XOLO.DATABASE_ERROR` | 500 | Persistence-layer failure |
| `InternalError` | `XOLO.INTERNAL_ERROR` | 500 | Unexpected server-side failure |

## Error attributes

```python
err = result.unwrap_err()

err.code         # str  — "XOLO.NOT_FOUND"
err.status_code  # int  — 404
err.message      # str  — human-readable description
err.metadata     # dict — extra context from the server (may be empty)
err.raw_error    # str | None — raw response body if JSON parsing failed
```

## Type-specific handling

Use `isinstance` to branch on the concrete error type:

```python
from xolo.client.errors import (
    NotFoundError,
    UnauthorizedError,
    AccessDeniedError,
    ValidationError,
)

result = client.get_role(role_id=role_id, token=token, temporal_secret=ts)

if result.is_err:
    err = result.unwrap_err()

    if isinstance(err, NotFoundError):
        print(f"Role {role_id} does not exist")
    elif isinstance(err, UnauthorizedError):
        print("Token is expired or missing")
    elif isinstance(err, AccessDeniedError):
        print("Insufficient permissions")
    elif isinstance(err, ValidationError):
        print("Bad request:", err.message)
    else:
        print(f"Unexpected error [{err.code}]: {err.message}")
```

You can also match on `.code` if you prefer string comparisons:

```python
err = result.unwrap_err()
match err.code:
    case "XOLO.NOT_FOUND":
        ...
    case "XOLO.UNAUTHORIZED":
        ...
    case _:
        raise RuntimeError(err.message)
```

## Imports

```python
# Namespace import (used internally by the client)
from xolo.client import errors as E
role = client.get_role(...)
if isinstance(result.unwrap_err(), E.NotFoundError): ...

# Named imports
from xolo.client.errors import (
    XoloError,
    NotFoundError,
    AlreadyExistsError,
    ConflictError,
    UnauthorizedError,
    AccessDeniedError,
    ValidationError,
    InvalidLicenseError,
    DatabaseError,
    InternalError,
)
```
