import pytest

from xoloapi.scopes.dto import AssignScopeDTO, CreateScopeDTO

ACCOUNT_ID = "acc-test"


@pytest.mark.asyncio
async def test_scopes_service_create_rejects_duplicates(scopes_service):
    first = await scopes_service.create(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    assert first.is_ok

    second = await scopes_service.create(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    assert second.is_err


@pytest.mark.asyncio
async def test_scopes_service_assign_rejects_duplicates(scopes_service):
    await scopes_service.create(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    first = await scopes_service.assign(ACCOUNT_ID, AssignScopeDTO(name="ops", username="alice"))
    assert first.is_ok

    second = await scopes_service.assign(ACCOUNT_ID, AssignScopeDTO(name="ops", username="alice"))
    assert second.is_err


@pytest.mark.asyncio
async def test_scopes_service_delete_scope(scopes_service):
    await scopes_service.create(ACCOUNT_ID, CreateScopeDTO(name="ops"))

    deleted = await scopes_service.delete(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    assert deleted.is_ok
    assert deleted.unwrap() is True


@pytest.mark.asyncio
async def test_scopes_service_delete_scope_fails_when_assignments_exist(scopes_service):
    await scopes_service.create(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    await scopes_service.assign(ACCOUNT_ID, AssignScopeDTO(name="ops", username="alice"))

    deleted = await scopes_service.delete(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    assert deleted.is_err


@pytest.mark.asyncio
async def test_scopes_service_unassign_scope(scopes_service):
    await scopes_service.create(ACCOUNT_ID, CreateScopeDTO(name="ops"))
    await scopes_service.assign(ACCOUNT_ID, AssignScopeDTO(name="ops", username="alice"))

    unassigned = await scopes_service.unassign(ACCOUNT_ID, AssignScopeDTO(name="ops", username="alice"))
    assert unassigned.is_ok
    assert unassigned.unwrap() is True
