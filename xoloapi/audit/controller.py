from __future__ import annotations

import datetime as dt
from fastapi import APIRouter, Depends, Query, Request

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.audit.models import AuditPage
from xoloapi.audit.repository import AuthorizationAuditRepository
from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames
from xoloapi.middleware.apikey import require_api_key
from xoloapi.platform_users.domain.value_objects import PlatformPermission


router = APIRouter(
    prefix="/accounts/{account_id}/authorization/audit",
    tags=["authorization-audit"],
    dependencies=[Depends(require_existing_account)],
)


def get_audit_repository() -> AuthorizationAuditRepository:
    return AuthorizationAuditRepository(get_collection(CollectionNames.AUTHORIZATION_AUDIT_COLLECTION_NAME))


@router.get("", response_model=AuditPage)
async def query_audit(
    account_id: str,
    request: Request,
    model: list[str] | None = Query(default=None),
    action: str | None = None,
    actor: str | None = None,
    target: str | None = None,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    _: object = Depends(require_api_key("audit")),
    repository: AuthorizationAuditRepository = Depends(get_audit_repository),
):
    requested = set(model or ["groups", "rbac", "acl", "abac", "ngac"])
    platform_user = getattr(request.state, "platform_user", None)
    if platform_user is not None:
        mapping = {
            "groups": PlatformPermission.GROUPS_READ,
            "rbac": PlatformPermission.RBAC_READ,
            "acl": PlatformPermission.ACL_READ,
            "abac": PlatformPermission.ABAC_READ,
            "ngac": PlatformPermission.NGAC_READ,
        }
        requested = {name for name in requested if name in mapping and platform_user.can(mapping[name], account_id)}
    items, next_cursor = await repository.query(
        account_id, models=sorted(requested), action=action, actor=actor,
        target=target, start=start, end=end, cursor=cursor, limit=limit,
    )
    return AuditPage(items=items, next_cursor=next_cursor)
