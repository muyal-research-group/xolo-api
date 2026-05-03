from typing import Tuple
from uuid import uuid4
import humanfriendly as HF
from motor.motor_asyncio import AsyncIOMotorCollection
from option import Err, NONE, Ok, Option, Result, Some
from redis.asyncio import Redis
from xolo.log import Log
from commonx.dto.xolo import CreateUserDTO
from commonx.models.xolo import User
import commonx.errors as EX
import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload
from xoloapi.users.domain.repositories import IUsersRepository

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)

class MongoUsersRepository(IUsersRepository):
    def __init__(self, collection: AsyncIOMotorCollection, cache_redis: Redis = None):
        self.collection = collection
        self.cache_redis = cache_redis

    async def enable_user(self, account_id: str, username: str) -> Result[bool, EX.XError]:
        try:
            doc = await self.collection.update_one(
                filter={"account_id": account_id, "username": username},
                update={"$set": {"disabled": False}},
            )
            if doc.modified_count > 0:
                return Ok(True)
            return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            log.error(build_log_payload("users.repository.enable.error", error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def disable_user(self, account_id: str, username: str) -> Result[bool, EX.XError]:
        try:
            doc = await self.collection.update_one(
                filter={"account_id": account_id, "username": username},
                update={"$set": {"disabled": True}},
            )
            if doc.modified_count > 0:
                return Ok(True)
            return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            log.error(build_log_payload("users.repository.disable.error", error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def set_access_token(
        self,
        account_id: str,
        username: str,
        access_token: str,
        temp_secret_key: str,
        exp: str = "15min",
        ) -> Result[bool, EX.XError]:
        try:
            if self.cache_redis is None:
                log.warning(build_log_payload("users.repository.token_store.error", error=EX.ServerError(raw_detail="Cache is not available"), username=username))
                return Err(EX.ServerError(raw_detail="Cache is not available"))
            await self.cache_redis.set(
                f"account:{account_id}:user:{username}:access_token",
                access_token,
                ex=int(HF.parse_timespan(exp)),
            )
            await self.cache_redis.set(
                f"account:{account_id}:user:{username}:temp_secret_key",
                temp_secret_key,
                ex=int(HF.parse_timespan(exp)),
            )
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.repository.token_store.error", error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def get_access_token(self, account_id: str, username: str) -> Result[Option[Tuple[str, str]], EX.XError]:
        try:
            if self.cache_redis is None:
                log.warning(build_log_payload("users.repository.token_get.error", error=EX.ServerError(raw_detail="Cache is not available"), username=username))
                return Err(EX.ServerError(raw_detail="Cache is not available"))
            token = await self.cache_redis.get(f"account:{account_id}:user:{username}:access_token")
            temp_secret_key = await self.cache_redis.get(f"account:{account_id}:user:{username}:temp_secret_key")

            if (token is None and temp_secret_key is not None) or (token is not None and temp_secret_key is None):
                return Ok(NONE)
            if token is None and temp_secret_key is None:
                return Err(EX.Unauthorized(raw_detail="Access token has expired"))
            return Ok(Some((token, temp_secret_key)))
        except Exception as e:
            log.error(build_log_payload("users.repository.token_get.error", error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def delete_access_token(self, account_id: str, username: str) -> Result[bool, EX.XError]:
        try:
            if self.cache_redis is None:
                log.warning(build_log_payload("users.repository.token_delete.error", error=EX.ServerError(raw_detail="Cache is not available"), username=username))
                return Err(EX.ServerError(raw_detail="Cache is not available"))
            await self.cache_redis.delete(f"account:{account_id}:user:{username}:access_token")
            await self.cache_redis.delete(f"account:{account_id}:user:{username}:temp_secret_key")
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.repository.token_delete.error", error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def update_password(self, account_id: str, username: str, password: str) -> Result[bool, EX.XError]:
        try:
            doc = await self.collection.update_one(
                filter={"account_id": account_id, "username": username},
                update={"$set": {"hash_password": password}},
            )
            if doc.modified_count > 0:
                return Ok(True)
            return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            log.error(build_log_payload("users.repository.password_update.error", error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def create(self, account_id: str, user: CreateUserDTO) -> Result[str, EX.XError]:
        try:
            user_key = uuid4().hex
            doc = User(
                profile_photo=user.profile_photo,
                key=user_key,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                hash_password=user.password,
                username=user.username,
            )
            payload = doc.model_dump()
            payload["account_id"] = account_id
            await self.collection.insert_one(payload)
            return Ok(user_key)
        except Exception as e:
            log.error(build_log_payload("users.repository.create.error", error=e, username=user.username))
            return Err(EX.UnknownError(raw_detail=str(e)))

    async def find_by_id(self, user_id: str, account_id: str | None = None) -> Option[User]:
        try:
            query = {"key": user_id}
            if account_id is not None:
                query["account_id"] = account_id
            doc = await self.collection.find_one(filter=query)
            if doc is None:
                return NONE
            doc.pop("account_id", None)
            return Some(User(**doc))
        except Exception as e:
            log.error(build_log_payload("users.repository.find_by_id.error", error=e, user_id=user_id))
            raise

    async def find_by_username(self, account_id: str, username: str) -> Option[User]:
        try:
            doc = await self.collection.find_one(filter={"account_id": account_id, "username": username})
            if doc is None:
                return NONE
            doc.pop("account_id", None)
            return Some(User(**doc))
        except Exception as e:
            log.error(build_log_payload("users.repository.find_by_username.error", error=e, username=username))
            raise

    async def find_by_email(self, account_id: str, email: str) -> Option[User]:
        try:
            doc = await self.collection.find_one(filter={"account_id": account_id, "email": email})
            if doc is None:
                return NONE
            doc.pop("account_id", None)
            return Some(User(**doc))
        except Exception as e:
            log.error(build_log_payload("users.repository.find_by_email.error", error=e, email=email))
            raise

    async def find_all(self, account_id: str) -> Result[list[User], EX.XError]:
        try:
            users = []
            async for doc in self.collection.find({"account_id": account_id}).sort([("username", 1)]):
                doc.pop("account_id", None)
                users.append(User(**doc))
            return Ok(users)
        except Exception as e:
            log.error(build_log_payload("users.repository.find_all.error", error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def delete_by_id(self, user_id: str, account_id: str | None = None) -> Result[bool, EX.XError]:
        try:
            query = {"key": user_id}
            if account_id is not None:
                query["account_id"] = account_id
            doc = await self.collection.delete_one(filter=query)
            if doc.deleted_count > 0:
                return Ok(True)
            return Err(EX.NotFound(raw_detail="User not found"))
        except Exception as e:
            log.error(build_log_payload("users.repository.delete.error", error=e, user_id=user_id))
            return Err(EX.ServerError(raw_detail=str(e)))
