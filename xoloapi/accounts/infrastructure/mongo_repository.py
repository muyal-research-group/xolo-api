from __future__ import annotations

from option import Err, NONE, Ok, Option, Result, Some
from motor.motor_asyncio import AsyncIOMotorCollection
from xolo.log import Log

import xoloapi.config as Cfg
from xoloapi.accounts.models import Account
from xoloapi.errors.base import (
    AlreadyExistsError,
    DatabaseError,
    NotFoundError,
    XoloException,
)
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoAccountsRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def create(self, account: Account) -> Result[Account, XoloException]:
        try:
            existing = await self.collection.find_one({"account_id": account.account_id}, {"_id": 0})
            if existing is not None:
                return Err(AlreadyExistsError("Account", account.account_id))
            await self.collection.insert_one(account.model_dump())
            return Ok(account)
        except Exception as exc:
            log.error(build_log_payload("accounts.repository.create.error", error=exc, account_id=account.account_id))
            return Err(DatabaseError(f"Failed to create account '{account.account_id}'", cause=exc))

    async def find_by_id(self, account_id: str) -> Result[Option[Account], XoloException]:
        try:
            doc = await self.collection.find_one({"account_id": account_id}, {"_id": 0})
            return Ok(NONE if doc is None else Some(Account(**doc)))
        except Exception as exc:
            log.error(build_log_payload("accounts.repository.find_by_id.error", error=exc, account_id=account_id))
            return Err(DatabaseError(f"Failed to look up account '{account_id}'", cause=exc))

    async def find_all(self) -> Result[list[Account], XoloException]:
        try:
            accounts: list[Account] = []
            async for doc in self.collection.find({}, {"_id": 0}).sort([("account_id", 1)]):
                accounts.append(Account(**doc))
            return Ok(accounts)
        except Exception as exc:
            log.error(build_log_payload("accounts.repository.find_all.error", error=exc))
            return Err(DatabaseError("Failed to list accounts", cause=exc))

    async def delete(self, account_id: str) -> Result[bool, XoloException]:
        try:
            result = await self.collection.delete_one({"account_id": account_id})
            if result.deleted_count == 0:
                return Err(NotFoundError("Account", account_id))
            return Ok(True)
        except Exception as exc:
            log.error(build_log_payload("accounts.repository.delete.error", error=exc, account_id=account_id))
            return Err(DatabaseError(f"Failed to delete account '{account_id}'", cause=exc))

