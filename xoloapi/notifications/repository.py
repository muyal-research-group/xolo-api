from __future__ import annotations

import datetime as dt

from motor.motor_asyncio import AsyncIOMotorCollection

from xoloapi.notifications.models import NotificationEvent, NotificationItem


class NotificationRepository:
    """Append-only events with recipient-specific read receipts."""

    def __init__(self, events: AsyncIOMotorCollection, receipts: AsyncIOMotorCollection):
        self.events = events
        self.receipts = receipts

    async def append(self, event: NotificationEvent) -> NotificationEvent:
        document = event.model_dump()
        document["_id"] = document.pop("notification_id")
        await self.events.insert_one(document)
        return event

    async def query(
        self,
        account_id: str,
        recipient_id: str,
        *,
        models: list[str],
        categories: list[str] | None = None,
        unread_only: bool = False,
        cursor: str | None = None,
        limit: int = 30,
    ) -> tuple[list[NotificationItem], str | None]:
        query: dict = {"account_id": account_id, "model": {"$in": models}}
        if categories:
            query["category"] = {"$in": categories}
        if cursor:
            cursor_doc = await self.events.find_one({"_id": cursor, "account_id": account_id})
            if cursor_doc:
                query["$or"] = [
                    {"timestamp": {"$lt": cursor_doc["timestamp"]}},
                    {"timestamp": cursor_doc["timestamp"], "_id": {"$lt": cursor}},
                ]
        # Read filtering is intentionally performed after joining receipts.
        # Fetching a bounded window keeps cursor pagination deterministic.
        cursor_query = self.events.find(query).sort([("timestamp", -1), ("_id", -1)])
        documents = await cursor_query.to_list(length=None if unread_only else limit + 1)
        ids = [document["_id"] for document in documents]
        read_ids = {
            receipt["notification_id"]
            async for receipt in self.receipts.find({
                "account_id": account_id,
                "recipient_id": recipient_id,
                "notification_id": {"$in": ids},
            }, {"notification_id": 1})
        }
        items: list[NotificationItem] = []
        for document in documents:
            notification_id = document.pop("_id")
            is_read = notification_id in read_ids
            if unread_only and is_read:
                continue
            items.append(NotificationItem(**document, notification_id=notification_id, is_read=is_read))
            if len(items) > limit:
                break
        has_more = len(items) > limit
        items = items[:limit]
        return items, items[-1].notification_id if has_more and items else None

    async def unread_count(self, account_id: str, recipient_id: str, models: list[str]) -> int:
        event_ids = [
            document["_id"]
            async for document in self.events.find(
                {"account_id": account_id, "model": {"$in": models}}, {"_id": 1}
            )
        ]
        if not event_ids:
            return 0
        read = await self.receipts.count_documents({
            "account_id": account_id,
            "recipient_id": recipient_id,
            "notification_id": {"$in": event_ids},
        })
        return max(0, len(event_ids) - read)

    async def mark_read(self, account_id: str, notification_id: str, recipient_id: str) -> bool:
        exists = await self.events.find_one({"_id": notification_id, "account_id": account_id}, {"_id": 1})
        if not exists:
            return False
        await self.receipts.update_one(
            {"account_id": account_id, "notification_id": notification_id, "recipient_id": recipient_id},
            {"$setOnInsert": {"read_at": dt.datetime.now(dt.timezone.utc)}},
            upsert=True,
        )
        return True

    async def mark_all_read(self, account_id: str, recipient_id: str, models: list[str]) -> int:
        count = 0
        async for event in self.events.find({"account_id": account_id, "model": {"$in": models}}, {"_id": 1}):
            await self.mark_read(account_id, event["_id"], recipient_id)
            count += 1
        return count
