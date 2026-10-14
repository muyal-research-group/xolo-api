from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames
from xoloapi.notifications.models import NotificationPage
from xoloapi.notifications.repository import NotificationRepository
from xoloapi.platform_users.dependencies import get_platform_user
from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole


router = APIRouter(
    prefix="/accounts/{account_id}/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_existing_account)],
)


def get_notification_repository() -> NotificationRepository:
    return NotificationRepository(
        get_collection(CollectionNames.NOTIFICATIONS_COLLECTION_NAME),
        get_collection(CollectionNames.NOTIFICATION_RECEIPTS_COLLECTION_NAME),
    )


def _models_for(user, account_id: str) -> list[str]:
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="Password change required")
    if user.role == PlatformRole.ADMIN:
        return ["groups", "rbac", "acl", "abac", "ngac", "accounts"]
    if account_id not in user.allowed_account_ids:
        raise HTTPException(status_code=403, detail="Account is not assigned to this platform user")
    mapping = {
        "groups": PlatformPermission.GROUPS_READ,
        "rbac": PlatformPermission.RBAC_READ,
        "acl": PlatformPermission.ACL_READ,
        "abac": PlatformPermission.ABAC_READ,
        "ngac": PlatformPermission.NGAC_READ,
        "accounts": PlatformPermission.ACCOUNTS_READ,
    }
    return [model for model, permission in mapping.items() if user.can(permission, account_id)]


@router.get("", response_model=NotificationPage)
async def list_notifications(
    account_id: str,
    category: list[str] | None = Query(default=None),
    unread_only: bool = False,
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    user=Depends(get_platform_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    items, next_cursor = await repository.query(
        account_id, user.user_id, models=_models_for(user, account_id), categories=category,
        unread_only=unread_only, cursor=cursor, limit=limit,
    )
    return NotificationPage(items=items, next_cursor=next_cursor)


@router.get("/unread-count")
async def unread_count(
    account_id: str,
    user=Depends(get_platform_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    return {"count": await repository.unread_count(account_id, user.user_id, _models_for(user, account_id))}


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    account_id: str,
    user=Depends(get_platform_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    await repository.mark_all_read(account_id, user.user_id, _models_for(user, account_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    account_id: str,
    notification_id: str,
    user=Depends(get_platform_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    visible = await repository.events.find_one({
        "_id": notification_id,
        "account_id": account_id,
        "model": {"$in": _models_for(user, account_id)},
    }, {"_id": 1})
    if not visible:
        raise HTTPException(status_code=404, detail="Notification not found")
    await repository.mark_read(account_id, notification_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
