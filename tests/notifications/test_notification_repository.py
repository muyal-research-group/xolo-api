import datetime as dt

import pytest
from mongomock_motor import AsyncMongoMockClient

from xoloapi.notifications.models import NotificationEvent
from xoloapi.notifications.repository import NotificationRepository
from xoloapi.notifications.controller import router


@pytest.mark.asyncio
async def test_notifications_are_account_scoped_cursor_paginated_and_recipient_read():
    db = AsyncMongoMockClient().db
    repository = NotificationRepository(db.notifications, db.notification_receipts)
    for index in range(3):
        await repository.append(NotificationEvent(
            account_id="a", category="access", model="rbac", actor_type="platform",
            actor_id="operator", action=f"change-{index}", target=f"role-{index}",
            timestamp=dt.datetime(2026, 1, 1, index, tzinfo=dt.timezone.utc),
        ))
    await repository.append(NotificationEvent(
        account_id="b", category="access", model="rbac", actor_type="platform",
        actor_id="operator", action="other-account", target="role",
    ))

    first, cursor = await repository.query("a", "one", models=["rbac"], limit=2)
    assert [item.action for item in first] == ["change-2", "change-1"]
    assert cursor
    second, _ = await repository.query("a", "one", models=["rbac"], cursor=cursor, limit=2)
    assert [item.action for item in second] == ["change-0"]

    await repository.mark_read("a", first[0].notification_id, "one")
    assert await repository.unread_count("a", "one", ["rbac"]) == 2
    assert await repository.unread_count("a", "two", ["rbac"]) == 3
    unread, _ = await repository.query("a", "one", models=["rbac"], unread_only=True)
    assert all(not item.is_read for item in unread)


def test_read_all_static_route_precedes_dynamic_notification_route():
    post_paths = [route.path for route in router.routes if "POST" in route.methods]
    assert post_paths.index("/accounts/{account_id}/notifications/read-all") < post_paths.index(
        "/accounts/{account_id}/notifications/{notification_id}/read"
    )
