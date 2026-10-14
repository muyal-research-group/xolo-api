from __future__ import annotations

import datetime as dt
from motor.motor_asyncio import AsyncIOMotorCollection

from xoloapi.audit.models import AuthorizationAuditEvent


class AuthorizationAuditRepository:
    """Append-only authorization event store.

    This repository intentionally exposes no update or delete methods.
    """

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def append(self, event: AuthorizationAuditEvent) -> AuthorizationAuditEvent:
        doc = event.model_dump()
        doc["_id"] = doc.pop("event_id")
        await self.collection.insert_one(doc)
        return event

    async def query(
        self,
        account_id: str,
        *,
        models: list[str] | None = None,
        action: str | None = None,
        actor: str | None = None,
        target: str | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuthorizationAuditEvent], str | None]:
        query: dict = {"account_id": account_id}
        if models:
            query["model"] = {"$in": models}
        if action:
            query["action"] = {"$regex": action, "$options": "i"}
        if actor:
            query["actor_id"] = {"$regex": actor, "$options": "i"}
        if target:
            query["target"] = {"$regex": target, "$options": "i"}
        if start or end:
            query["timestamp"] = {}
            if start:
                query["timestamp"]["$gte"] = start
            if end:
                query["timestamp"]["$lte"] = end
        if cursor:
            cursor_doc = await self.collection.find_one({"_id": cursor, "account_id": account_id})
            if cursor_doc:
                query["$or"] = [
                    {"timestamp": {"$lt": cursor_doc["timestamp"]}},
                    {"timestamp": cursor_doc["timestamp"], "_id": {"$lt": cursor}},
                ]
        docs = await self.collection.find(query).sort([("timestamp", -1), ("_id", -1)]).limit(limit + 1).to_list(length=limit + 1)
        has_more = len(docs) > limit
        docs = docs[:limit]
        items = []
        for doc in docs:
            doc["event_id"] = doc.pop("_id")
            items.append(AuthorizationAuditEvent(**doc))
        return items, items[-1].event_id if has_more and items else None
