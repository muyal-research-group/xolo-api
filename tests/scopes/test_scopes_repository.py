import pytest

from xoloapi.scopes.dto import AssignScopeDTO, CreateScopeDTO

ACCOUNT_ID = "acc-test"


@pytest.mark.asyncio
async def test_scopes_repository_create_and_list(scopes_repo):
    created = await scopes_repo.create(ACCOUNT_ID, CreateScopeDTO(name="health"))
    assert created.is_ok
    assert created.unwrap() == "HEALTH"

    exists = await scopes_repo.exists_scope(ACCOUNT_ID, "health")
    assert exists.is_ok
    assert exists.unwrap() is True

    scopes = await scopes_repo.find_all_scopes(ACCOUNT_ID)
    assert scopes.is_ok
    assert [scope.name for scope in scopes.unwrap()] == ["HEALTH"]


@pytest.mark.asyncio
async def test_scopes_repository_assign_and_check_user(scopes_repo):
    await scopes_repo.create(ACCOUNT_ID, CreateScopeDTO(name="health"))
    assigned = await scopes_repo.assign(ACCOUNT_ID, AssignScopeDTO(name="health", username="alice"))
    assert assigned.is_ok

    exists = await scopes_repo.exists_scope_user(ACCOUNT_ID, name="health", username="alice")
    assert exists.is_ok
    assert exists.unwrap() is True


@pytest.mark.asyncio
async def test_scopes_repository_unassign_and_delete(scopes_repo):
    await scopes_repo.create(ACCOUNT_ID, CreateScopeDTO(name="health"))
    await scopes_repo.assign(ACCOUNT_ID, AssignScopeDTO(name="health", username="alice"))

    unassigned = await scopes_repo.unassign(ACCOUNT_ID, AssignScopeDTO(name="health", username="alice"))
    assert unassigned.is_ok
    assert unassigned.unwrap() is True

    deleted = await scopes_repo.delete(ACCOUNT_ID, "health")
    assert deleted.is_ok
    assert deleted.unwrap() is True

    scope_exists = await scopes_repo.exists_scope(ACCOUNT_ID, "health")
    assert scope_exists.is_ok
    assert scope_exists.unwrap() is False

    assignment_exists = await scopes_repo.exists_scope_user(ACCOUNT_ID, name="health", username="alice")
    assert assignment_exists.is_ok
    assert assignment_exists.unwrap() is False
