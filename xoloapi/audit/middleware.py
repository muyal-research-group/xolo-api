from __future__ import annotations

import json
import uuid
from typing import Any
from fastapi import Request

from xoloapi.audit.models import AuthorizationAuditEvent
from xoloapi.audit.repository import AuthorizationAuditRepository
from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames
from xoloapi.notifications.models import NotificationEvent
from xoloapi.notifications.repository import NotificationRepository


_SENSITIVE_KEYS = {"password", "password_hash", "token", "secret", "api_key", "key_hash"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.casefold() in _SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def authorization_model(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    for name in ("groups", "rbac", "acl", "abac", "ngac"):
        if name in parts:
            return name
    return None


def _notification_category(model: str, method: str, path: str) -> str:
    if method == "DELETE" and any(word in path for word in ("policy", "nodes", "groups")):
        return "security"
    if model == "groups":
        return "membership"
    if model in {"acl", "rbac"}:
        return "access"
    return "policy"


def _affected_principal(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in (
        "user_identifier", "principal_identifier", "owner_identifier",
        "owner_username", "principal_username", "subject_username", "user_id",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


async def capture_authorization_audit(request: Request, call_next):
    model = authorization_model(request.url.path)
    mutating = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    payload = None
    audit_collection = get_collection(CollectionNames.AUTHORIZATION_AUDIT_COLLECTION_NAME)
    if model and mutating:
        body = await request.body()
        if body:
            try:
                payload = redact(json.loads(body))
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"body": "[NON_JSON]"}
    response = await call_next(request)
    if model and mutating and response.status_code < 400:
        account_id = request.path_params.get("account_id")
        if account_id:
            actor = getattr(request.state, "platform_user", None)
            if actor is not None:
                actor_type, actor_id = "platform", actor.user_id
            elif getattr(request.state, "current_user", None) is not None:
                current_user = request.state.current_user
                actor_type, actor_id = "tenant", current_user.key
            elif request.headers.get("X-API-Key"):
                actor_type, actor_id = "service", "api-key"
            else:
                actor_type, actor_id = "unknown", "unknown"
            correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
            event = AuthorizationAuditEvent(
                account_id=account_id,
                model=model,
                actor_type=actor_type,
                actor_id=actor_id,
                action=f"{request.method} {request.url.path}",
                target=request.url.path,
                before=redact(getattr(request.state, "authorization_audit_before", None)),
                after=redact(getattr(request.state, "authorization_audit_after", payload)),
                correlation_id=correlation_id,
            )
            if audit_collection is not None:
                repository = AuthorizationAuditRepository(audit_collection)
                await repository.append(event)
                response.headers["X-Correlation-ID"] = correlation_id
            notifications = get_collection(CollectionNames.NOTIFICATIONS_COLLECTION_NAME)
            receipts = get_collection(CollectionNames.NOTIFICATION_RECEIPTS_COLLECTION_NAME)
            if notifications is not None and receipts is not None:
                try:
                    category = _notification_category(model, request.method, request.url.path)
                    await NotificationRepository(notifications, receipts).append(NotificationEvent(
                        category=category,
                        severity="warning" if category == "security" else "success",
                        account_id=account_id,
                        model=model,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        affected_principal=_affected_principal(payload),
                        action=f"{request.method} {request.url.path}",
                        target=request.url.path,
                        safe_detail={"method": request.method, "model": model},
                        link_target=request.url.path,
                    ))
                except Exception:
                    # A notification must never roll back an already committed
                    # authorization mutation; audit remains the source of truth.
                    pass
    return response
