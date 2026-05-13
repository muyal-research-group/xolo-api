import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Option, Some, NONE, Result, Ok, Err
from xoloapi.log import Log

import xoloapi.config as Cfg
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.repositories import IAPIKeyRepository
from xoloapi.errors.base import DatabaseError, XoloException
from xoloapi.log.format import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoAPIKeyRepository(IAPIKeyRepository):

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.col = db[collection_name]

    async def find_by_hash(self, key_hash: str) -> Result[Option[APIKey], XoloException]:
        try:
            doc = await self.col.find_one({"key_hash": key_hash}, {"_id": 0})
            return Ok(NONE if doc is None else Some(APIKey(**doc)))
        except Exception as e:
            log.error(build_log_payload("apikeys.repository.find_by_hash.error", error=e))
            return Err(DatabaseError("Failed to look up API key by hash", cause=e))

    async def find_by_id(self, key_id: str) -> Result[Option[APIKey], XoloException]:
        try:
            doc = await self.col.find_one({"key_id": key_id}, {"_id": 0})
            return Ok(NONE if doc is None else Some(APIKey(**doc)))
        except Exception as e:
            log.error(build_log_payload("apikeys.repository.find_by_id.error", error=e, key_id=key_id))
            return Err(DatabaseError(f"Failed to look up API key '{key_id}'", cause=e))

    async def find_all(self) -> Result[list[APIKey], XoloException]:
        try:
            docs: list[APIKey] = []
            async for doc in self.col.find({}, {"_id": 0}):
                docs.append(APIKey(**doc))
            return Ok(docs)
        except Exception as e:
            log.error(build_log_payload("apikeys.repository.find_all.error", error=e))
            return Err(DatabaseError("Failed to list API Keys", cause=e))

    async def find_all_for_account(self, account_id: str) -> Result[list[APIKey], XoloException]:
        try:
            docs: list[APIKey] = []
            async for doc in self.col.find({"account_id": account_id}, {"_id": 0}):
                docs.append(APIKey(**doc))
            return Ok(docs)
        except Exception as e:
            log.error(build_log_payload("apikeys.repository.find_all_for_account.error", error=e, account_id=account_id))
            return Err(DatabaseError(f"Failed to list API Keys for account '{account_id}'", cause=e))

    async def save(self, key: APIKey) -> Result[APIKey, XoloException]:
        try:
            await self.col.replace_one(
                {"key_id": key.key_id},
                key.model_dump(),
                upsert=True,
            )
            return Ok(key)
        except Exception as e:
            log.error(build_log_payload("apikeys.repository.save.error", error=e, key_id=key.key_id))
            return Err(DatabaseError(f"Failed to save API key '{key.key_id}'", cause=e))

    async def delete(self, key_id: str) -> Result[bool, XoloException]:
        try:
            result = await self.col.delete_one({"key_id": key_id})
            if result.deleted_count == 0:
                return Err(DatabaseError(f"API key '{key_id}' not found in collection"))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("apikeys.repository.delete.error", error=e, key_id=key_id))
            return Err(DatabaseError(f"Failed to delete API key '{key_id}'", cause=e))

    async def update_last_used(self, key_id: str) -> None:
        try:
            await self.col.update_one(
                {"key_id": key_id},
                {"$set": {"last_used_at": datetime.datetime.now(datetime.timezone.utc)}},
            )
        except Exception as e:
            log.warning(build_log_payload("apikeys.repository.update_last_used.error", error=e, key_id=key_id))
