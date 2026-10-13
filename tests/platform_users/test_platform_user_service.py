from option import NONE, Ok, Some
import pytest

from xoloapi.platform_users.application.platform_user_service import PlatformUserService
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole


class MemoryPlatformUsers:
    def __init__(self):
        self.users: dict[str, PlatformUser] = {}

    async def ensure_indexes(self): return Ok(None)
    async def count(self): return Ok(len(self.users))
    async def count_active_admins(self):
        return Ok(sum(user.role == PlatformRole.ADMIN and user.is_active for user in self.users.values()))
    async def find_by_id(self, user_id): return Ok(Some(self.users[user_id]) if user_id in self.users else NONE)
    async def find_by_username(self, username):
        user = next((item for item in self.users.values() if item.username == username), None)
        return Ok(Some(user) if user else NONE)
    async def list_all(self): return Ok(list(self.users.values()))
    async def save(self, user): self.users[user.user_id] = user; return Ok(user)
    async def delete(self, user_id): return Ok(self.users.pop(user_id, None) is not None)


@pytest.mark.asyncio
async def test_bootstrap_admin_requires_password_change_and_authenticates():
    repo = MemoryPlatformUsers()
    service = PlatformUserService(repo)

    result = await service.bootstrap("Admin", "bootstrap-password")

    assert result.is_ok
    admin = result.unwrap()
    assert admin.role == PlatformRole.ADMIN
    assert admin.must_change_password is True
    authenticated = await service.authenticate("admin", "bootstrap-password")
    assert authenticated.is_ok


@pytest.mark.asyncio
async def test_guest_keeps_only_read_permissions():
    service = PlatformUserService(MemoryPlatformUsers())
    result = await service.create(
        "viewer", "viewer-password",
        PlatformRole.GUEST,
        {PlatformPermission.ACL_READ, PlatformPermission.ACL_MANAGE},
        {"account-a"},
    )

    assert result.is_ok
    guest = result.unwrap()
    assert guest.permissions == {PlatformPermission.ACL_READ}
    assert guest.can(PlatformPermission.ACL_READ, "account-a")
    assert not guest.can(PlatformPermission.ACL_MANAGE, "account-a")
    assert not guest.can(PlatformPermission.ACL_READ, "account-b")


@pytest.mark.asyncio
async def test_last_active_admin_cannot_be_disabled_or_deleted():
    repo = MemoryPlatformUsers()
    service = PlatformUserService(repo)
    admin = (await service.bootstrap("admin", "bootstrap-password")).unwrap()

    disabled = await service.update(admin.user_id, is_active=False)
    deleted = await service.delete(admin.user_id)

    assert disabled.is_err
    assert disabled.unwrap_err().status_code == 409
    assert deleted.is_err
    assert deleted.unwrap_err().status_code == 409
