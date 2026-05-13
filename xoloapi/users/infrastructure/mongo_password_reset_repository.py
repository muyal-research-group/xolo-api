import datetime

from motor.motor_asyncio import AsyncIOMotorCollection
from option import Err, NONE, Ok, Result, Some
from xoloapi.log import Log

import commonx.errors as EX
import xoloapi.config as Cfg
from xoloapi.log.format import build_log_payload
from xoloapi.users.domain.aggregates import PasswordResetToken
from xoloapi.users.domain.repositories import IPasswordResetRepository

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class MongoPasswordResetRepository(IPasswordResetRepository):
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self.collection.create_index("token_hash", unique=True)
        await self.collection.create_index("user_id")
        await self.collection.create_index("expires_at", expireAfterSeconds=0)
        self._indexes_ready = True

    async def create(self, token: PasswordResetToken) -> Result[PasswordResetToken, EX.XError]:
        try:
            await self._ensure_indexes()
            await self.collection.insert_one(token.model_dump())
            return Ok(token)
        except Exception as e:
            log.error(build_log_payload("users.password_reset_repository.create.error", error=e, request_id=token.request_id, user_id=token.user_id))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def find_active_by_hash(self, token_hash: str):
        try:
            await self._ensure_indexes()
            doc = await self.collection.find_one(
                {
                    "token_hash": token_hash,
                    "used_at": None,
                    "expires_at": {"$gt": datetime.datetime.now(datetime.timezone.utc)},
                }
            )
            if doc is None:
                return Ok(NONE)
            return Ok(Some(PasswordResetToken(**doc)))
        except Exception as e:
            log.error(build_log_payload("users.password_reset_repository.find_active.error", error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def invalidate_for_user(
        self,
        account_id: str,
        user_id: str,
        used_at: datetime.datetime | None = None,
    ) -> Result[bool, EX.XError]:
        try:
            await self._ensure_indexes()
            result = await self.collection.update_many(
                {"account_id": account_id, "user_id": user_id, "used_at": None},
                {"$set": {"used_at": used_at or datetime.datetime.now(datetime.timezone.utc)}},
            )
            return Ok(result.acknowledged)
        except Exception as e:
            log.error(build_log_payload("users.password_reset_repository.invalidate_for_user.error", error=e, user_id=user_id))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def mark_used(
        self,
        request_id: str,
        used_at: datetime.datetime | None = None,
    ) -> Result[bool, EX.XError]:
        try:
            await self._ensure_indexes()
            result = await self.collection.update_one(
                {"request_id": request_id, "used_at": None},
                {"$set": {"used_at": used_at or datetime.datetime.now(datetime.timezone.utc)}},
            )
            if result.modified_count == 0:
                return Err(EX.NotFound(raw_detail="Password reset token not found"))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.password_reset_repository.mark_used.error", error=e, request_id=request_id))
            return Err(EX.ServerError(raw_detail=str(e)))
