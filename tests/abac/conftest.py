"""
Shared fixtures for the ABAC test suite.

Requires:
  - MongoDB reachable at mongodb://localhost:27018
  - Redis reachable (for the FastAPI lifespan in controller tests)
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from option import Ok

import commonx.dto.xolo as DTO
from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.accounts.dependencies import get_accounts_service
from xoloapi.accounts.dto import CreateAccountDTO
from xoloapi.accounts.infrastructure.mongo_repository import MongoAccountsRepository
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.abac.evaluator import ABACEvaluator
from xoloapi.abac.repository import ABACRepository
from xoloapi.abac.service import ABACService
from xoloapi.db.constants import CollectionNames

_MONGO_URI  = "mongodb://localhost:27018"
_DB_NAME    = "xolo_test_abac"
_COLLECTION = "abac_policies"
ACCOUNT_ID  = "acc-abac"

FAKE_USER = DTO.UserDTO(
    key           = "u-test-key",
    username      = "testuser",
    first_name    = "Test",
    last_name     = "User",
    email         = "test@test.com",
    profile_photo = "",
)


class _FakeAPIKeyService:
    async def validate(self, raw_key: str, required_scope: str):
        return Ok(APIKey(
            key_id="test-key",
            key_hash="hash",
            key_prefix="test",
            account_id=ACCOUNT_ID,
            name="Test key",
            scopes=[APIKeyScope.ALL, APIKeyScope.ABAC],
            created_by="tests",
        ))


@pytest_asyncio.fixture
async def abac_repo():
    client = AsyncIOMotorClient(_MONGO_URI)
    db     = client[_DB_NAME]
    await db.drop_collection(_COLLECTION)
    await db.drop_collection(CollectionNames.ACCOUNTS_COLLECTION_NAME)
    yield ABACRepository(db=db)
    await db.drop_collection(_COLLECTION)
    await db.drop_collection(CollectionNames.ACCOUNTS_COLLECTION_NAME)
    client.close()


@pytest_asyncio.fixture
async def abac_service(abac_repo):
    yield ABACService(repository=abac_repo, evaluator=ABACEvaluator())


@pytest_asyncio.fixture
async def abac_accounts_service():
    client = AsyncIOMotorClient(_MONGO_URI)
    db = client[_DB_NAME]
    service = AccountsService(
        repository=MongoAccountsRepository(
            collection=db[CollectionNames.ACCOUNTS_COLLECTION_NAME],
        )
    )
    await service.create_account(CreateAccountDTO(account_id=ACCOUNT_ID, name="ABAC Test Account"))
    await service.create_account(CreateAccountDTO(account_id="acc-other", name="Other ABAC Account"))
    yield service
    client.close()


@pytest_asyncio.fixture
async def abac_client(abac_service, abac_accounts_service):
    """AsyncClient with auth and service factory overridden to use the test DB."""
    from xoloapi.abac.controller import get_abac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    from xoloapi.middleware.apikey import _get_apikey_service

    app.dependency_overrides[MX.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_abac_service]    = lambda: abac_service
    app.dependency_overrides[get_accounts_service] = lambda: abac_accounts_service
    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as client:
        yield client

    app.dependency_overrides.pop(MX.get_current_user, None)
    app.dependency_overrides.pop(get_abac_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)
    app.dependency_overrides.pop(_get_apikey_service, None)
