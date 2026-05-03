import pytest

import commonx.dto.xolo as DTO
from xoloapi.users.domain.aggregates import PasswordResetToken

ACCOUNT_ID = "acc-test"


@pytest.mark.asyncio
async def test_users_repository_crud_and_cache(users_repo):
    created = await users_repo.create(
        ACCOUNT_ID,
        DTO.CreateUserDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="secret",
            profile_photo="",
        )
    )
    assert created.is_ok
    user_id = created.unwrap()

    found = await users_repo.find_by_id(user_id)
    assert found.is_some
    assert found.unwrap().username == "alice"

    found_by_email = await users_repo.find_by_email(ACCOUNT_ID, "alice@example.com")
    assert found_by_email.is_some
    assert found_by_email.unwrap().username == "alice"

    updated = await users_repo.update_password(ACCOUNT_ID, "alice", "new-secret")
    assert updated.is_ok

    disabled = await users_repo.disable_user(ACCOUNT_ID, "alice")
    assert disabled.is_ok
    enabled = await users_repo.enable_user(ACCOUNT_ID, "alice")
    assert enabled.is_ok

    stored = await users_repo.set_access_token(ACCOUNT_ID, "alice", "token", "tmp", "15m")
    assert stored.is_ok
    loaded = await users_repo.get_access_token(ACCOUNT_ID, "alice")
    assert loaded.is_ok
    assert loaded.unwrap().unwrap() == ("token", "tmp")

    deleted = await users_repo.delete_access_token(ACCOUNT_ID, "alice")
    assert deleted.is_ok


@pytest.mark.asyncio
async def test_password_reset_repository_lifecycle(users_password_reset_repo):
    created = await users_password_reset_repo.create(
        PasswordResetToken.new(
            account_id=ACCOUNT_ID,
            user_id="user-1",
            username="alice",
            email="alice@example.com",
            token_hash="hash-1",
            expires_in="15m",
        )
    )
    assert created.is_ok

    found = await users_password_reset_repo.find_active_by_hash("hash-1")
    assert found.is_ok
    assert found.unwrap().is_some

    marked = await users_password_reset_repo.mark_used(created.unwrap().request_id)
    assert marked.is_ok

    found_after = await users_password_reset_repo.find_active_by_hash("hash-1")
    assert found_after.is_ok
    assert found_after.unwrap().is_none
