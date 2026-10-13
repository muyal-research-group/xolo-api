import datetime as dt

from bson import BSON
import pytest

from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole
from xoloapi.platform_users.infrastructure.mongo_repository import MongoPlatformUserRepository


class MemoryCollection:
    def __init__(self):
        self.document = None

    async def replace_one(self, query, document, *, upsert):
        BSON.encode(document)
        self.document = document

    async def find_one(self, query, projection):
        if self.document is None or self.document["user_id"] != query["user_id"]:
            return None
        return dict(self.document)


@pytest.mark.asyncio
async def test_save_serializes_platform_user_as_bson_and_round_trips():
    collection = MemoryCollection()
    repository = MongoPlatformUserRepository(collection)
    created_at = dt.datetime.now(dt.timezone.utc)
    user = PlatformUser(
        user_id="platform-user-1",
        username="admin",
        password_hash="hash",
        role=PlatformRole.USER,
        permissions={PlatformPermission.ACL_READ, PlatformPermission.USERS_MANAGE},
        allowed_account_ids={"account-b", "account-a"},
        created_at=created_at,
        updated_at=created_at,
    )

    saved = await repository.save(user)

    assert saved.is_ok
    assert collection.document["role"] == "user"
    assert collection.document["permissions"] == ["acl.read", "users.manage"]
    assert collection.document["allowed_account_ids"] == ["account-a", "account-b"]
    assert collection.document["created_at"] == created_at

    found = await repository.find_by_id(user.user_id)
    assert found.is_ok
    assert found.unwrap().unwrap() == user
