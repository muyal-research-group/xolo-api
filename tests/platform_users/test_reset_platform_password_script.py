from option import NONE, Ok, Some
import pytest
import pytest_asyncio

from scripts.reset_platform_password import reset_platform_password
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.security import Security


class MemoryPlatformUsers:
    def __init__(self, user: PlatformUser):
        self.user = user

    async def find_by_username(self, username):
        return Ok(Some(self.user) if self.user.username == username else NONE)

    async def find_by_id(self, user_id):
        return Ok(Some(self.user) if self.user.user_id == user_id else NONE)

    async def save(self, user):
        self.user = user
        return Ok(user)


class MemorySessions:
    def __init__(self):
        self.deleted_user_ids = []

    async def delete_user_sessions(self, user_id):
        self.deleted_user_ids.append(user_id)


@pytest_asyncio.fixture
async def platform_user():
    return PlatformUser(
        user_id="platform-user-1",
        username="admin",
        password_hash=await Security.hash_value("original-password"),
    )


@pytest.mark.asyncio
async def test_reset_password_updates_hash_and_invalidates_sessions(platform_user):
    repository = MemoryPlatformUsers(platform_user)
    sessions = MemorySessions()

    result = await reset_platform_password(
        repository, sessions, " Admin ", "replacement-password"
    )

    assert result.is_ok
    assert await Security.verify_password(repository.user.password_hash, "replacement-password")
    assert repository.user.must_change_password is True
    assert sessions.deleted_user_ids == [platform_user.user_id]


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password_without_invalidating_sessions(platform_user):
    repository = MemoryPlatformUsers(platform_user)
    sessions = MemorySessions()

    result = await reset_platform_password(repository, sessions, "admin", "too-short")

    assert result.is_err
    assert result.unwrap_err().status_code == 422
    assert await Security.verify_password(repository.user.password_hash, "original-password")
    assert sessions.deleted_user_ids == []


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_user(platform_user):
    sessions = MemorySessions()

    result = await reset_platform_password(
        MemoryPlatformUsers(platform_user), sessions, "missing", "replacement-password"
    )

    assert result.is_err
    assert result.unwrap_err().status_code == 404
    assert sessions.deleted_user_ids == []
