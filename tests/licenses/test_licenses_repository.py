import pytest

ACCOUNT_ID = "acc-test"


@pytest.mark.asyncio
async def test_licenses_repository_create_find_delete(licenses_repo):
    created = await licenses_repo.create(
        account_id=ACCOUNT_ID,
        username="alice",
        license="signed-license",
        scope="OPS",
        expires_at="2026-01-01 00:00:00 UTC",
    )
    assert created.is_ok

    found = await licenses_repo.find_by_username_and_scope(ACCOUNT_ID, "alice", "ops")
    assert found.is_ok
    assert found.unwrap() == "signed-license"

    deleted = await licenses_repo.delete_by_username_scope(ACCOUNT_ID, "alice", "ops")
    assert deleted.is_ok


@pytest.mark.asyncio
async def test_licenses_repository_list_count_and_delete_by_user(licenses_repo):
    await licenses_repo.create(
        account_id=ACCOUNT_ID,
        username="alice",
        license="signed-license",
        scope="OPS",
        expires_at="2026-01-01 00:00:00 UTC",
    )

    count = await licenses_repo.count_by_scope(ACCOUNT_ID, "ops")
    assert count.is_ok
    assert count.unwrap() == 1

    all_licenses = await licenses_repo.find_all(ACCOUNT_ID)
    assert all_licenses.is_ok
    assert len(all_licenses.unwrap()) == 1

    deleted = await licenses_repo.delete_all_by_username(ACCOUNT_ID, "alice")
    assert deleted.is_ok
    assert deleted.unwrap() == 1
