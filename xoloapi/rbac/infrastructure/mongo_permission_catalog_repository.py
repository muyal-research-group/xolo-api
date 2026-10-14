from __future__ import annotations

import datetime as dt
from motor.motor_asyncio import AsyncIOMotorDatabase


class MongoPermissionCatalogRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.collection = db[collection_name]

    async def register(self, account_id: str, permissions: list[str]) -> None:
        for permission in sorted(set(permissions)):
            await self.collection.update_one(
                {"account_id": account_id, "permission": permission},
                {"$setOnInsert": {
                    "account_id": account_id,
                    "permission": permission,
                    "created_at": dt.datetime.now(dt.timezone.utc),
                }},
                upsert=True,
            )

    async def list(self, account_id: str) -> list[str]:
        docs = await self.collection.find({"account_id": account_id}, {"_id": 0, "permission": 1}).sort("permission", 1).to_list(length=None)
        return [doc["permission"] for doc in docs]
