from __future__ import annotations

import time as T
from typing import Any


def build_log_payload(
    action: str,
    *,
    started_at: float | None = None,
    error: Any | None = None,
    **context: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"action": action, **context}

    if started_at is not None:
        payload["time_taken_ms"] = round((T.time() - started_at) * 1000, 2)

    if error is not None:
        payload["error"] = str(error)
        detail = getattr(error, "detail", None)

        payload["error_code"] = getattr(detail, "code", getattr(error, "code", None))
        payload["error_message"] = getattr(
            detail,
            "msg",
            getattr(detail, "message", getattr(error, "message", None)),
        )
        payload["error_status_code"] = getattr(
            detail,
            "status_code",
            getattr(error, "status_code", None),
        )

        raw_error = getattr(detail, "raw_error", None)
        if raw_error not in (None, ""):
            payload["raw_error"] = raw_error

        metadata = getattr(detail, "metadata", None)
        if metadata not in (None, {}, []):
            payload["error_metadata"] = metadata

    return {key: value for key, value in payload.items() if value is not None}
