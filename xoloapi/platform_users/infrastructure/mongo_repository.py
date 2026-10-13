from motor.motor_asyncio import AsyncIOMotorCollection
from option import Err, NONE, Ok, Option, Result, Some

from xoloapi.errors.base import DatabaseError, XoloException
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.repositories import IPlatformUserRepository


class MongoPlatformUserRepository(IPlatformUserRepository):
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> Result[None, XoloException]:
        try:
            await self.collection.create_index("username", unique=True)
            return Ok(None)
        except Exception as exc:
            return Err(DatabaseError("Failed to create platform-user indexes", cause=exc))

    async def count(self) -> Result[int, XoloException]:
        try:
            return Ok(await self.collection.count_documents({}))
        except Exception as exc:
            return Err(DatabaseError("Failed to count platform users", cause=exc))

    async def count_active_admins(self) -> Result[int, XoloException]:
        try:
            return Ok(await self.collection.count_documents({"role": "admin", "is_active": True}))
        except Exception as exc:
            return Err(DatabaseError("Failed to count platform administrators", cause=exc))

    async def find_by_id(self, user_id: str) -> Result[Option[PlatformUser], XoloException]:
        try:
            doc = await self.collection.find_one({"user_id": user_id}, {"_id": 0})
            return Ok(NONE if doc is None else Some(PlatformUser(**doc)))
        except Exception as exc:
            return Err(DatabaseError("Failed to find platform user", cause=exc))

    async def find_by_username(self, username: str) -> Result[Option[PlatformUser], XoloException]:
        try:
            doc = await self.collection.find_one({"username": username.lower()}, {"_id": 0})
            return Ok(NONE if doc is None else Some(PlatformUser(**doc)))
        except Exception as exc:
            return Err(DatabaseError("Failed to find platform user", cause=exc))

    async def list_all(self) -> Result[list[PlatformUser], XoloException]:
        try:
            users: list[PlatformUser] = []
            async for doc in self.collection.find({}, {"_id": 0}).sort("username", 1):
                users.append(PlatformUser(**doc))
            return Ok(users)
        except Exception as exc:
            return Err(DatabaseError("Failed to list platform users", cause=exc))

    async def save(self, user: PlatformUser) -> Result[PlatformUser, XoloException]:
        try:
            document = user.model_dump(mode="python")
            # PyMongo cannot encode sets. Keep datetimes in Python mode so MongoDB
            # stores them as BSON dates, while explicitly serializing the domain's
            # collection and enum values.
            document["role"] = user.role.value
            document["permissions"] = sorted(permission.value for permission in user.permissions)
            document["allowed_account_ids"] = sorted(user.allowed_account_ids)
            await self.collection.replace_one(
                {"user_id": user.user_id},
                document,
                upsert=True,
            )
            return Ok(user)
        except Exception as exc:
            return Err(DatabaseError("Failed to save platform user", cause=exc))

    async def delete(self, user_id: str) -> Result[bool, XoloException]:
        try:
            result = await self.collection.delete_one({"user_id": user_id})
            return Ok(result.deleted_count == 1)
        except Exception as exc:
            return Err(DatabaseError("Failed to delete platform user", cause=exc))
