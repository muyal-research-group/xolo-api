"""
Shared fixtures for the NGAC test suite.

Requires:
  - MongoDB reachable at mongodb://localhost:27018
  - Redis reachable (for the FastAPI lifespan in controller tests)
"""
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from option import Ok

import commonx.dto.xolo as DTO
from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.accounts.dependencies import get_accounts_service
from xoloapi.accounts.dto import CreateAccountDTO
from xoloapi.accounts.infrastructure.mongo_repository import MongoAccountsRepository
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames
from xoloapi.ngac.infrastructure.mongo_ngac_repository import MongoNGACRepository
from xoloapi.ngac.application.ngac_service import NGACService

_MONGO_URI = "mongodb://localhost:27018"
_DB_NAME   = "xolo_test_ngac"
_COLS      = ["ngac_nodes", "ngac_assignments", "ngac_associations"]
ACCOUNT_ID = "acc-ngac"

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
            scopes=[APIKeyScope.ALL, APIKeyScope.NGAC],
            created_by="tests",
        ))


@pytest_asyncio.fixture
async def ngac_repo():
    client = AsyncIOMotorClient(_MONGO_URI)
    db     = client[_DB_NAME]
    for col in _COLS:
        await db.drop_collection(col)
    await db.drop_collection(CollectionNames.ACCOUNTS_COLLECTION_NAME)
    
    yield MongoNGACRepository(
        db=db,
        nodes_col=CollectionNames.NGAC_NODES_COLLECTION_NAME,
        assignments_col=CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
        associations_col=CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
    )
    for col in _COLS:
        await db.drop_collection(col)
    await db.drop_collection(CollectionNames.ACCOUNTS_COLLECTION_NAME)
    client.close()


@pytest_asyncio.fixture
async def ngac_service(ngac_repo):
    yield NGACService(repository=ngac_repo)


@pytest_asyncio.fixture
async def ngac_accounts_service():
    client = AsyncIOMotorClient(_MONGO_URI)
    db = client[_DB_NAME]
    service = AccountsService(
        repository=MongoAccountsRepository(
            collection=db[CollectionNames.ACCOUNTS_COLLECTION_NAME],
        )
    )
    await service.create_account(CreateAccountDTO(account_id=ACCOUNT_ID, name="NGAC Test Account"))
    yield service
    client.close()

@pytest_asyncio.fixture
async def unauthenticated_ngac_client(ngac_service, ngac_accounts_service):
    """AsyncClient with auth and service factory overridden to use the test DB."""
    from xoloapi.ngac.controller import get_ngac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    from xoloapi.middleware.apikey import _get_apikey_service

    app.dependency_overrides[get_ngac_service]    = lambda: ngac_service
    app.dependency_overrides[get_accounts_service] = lambda: ngac_accounts_service
    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as client:
        yield client

    app.dependency_overrides.pop(MX.get_current_user, None)
    app.dependency_overrides.pop(get_ngac_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)
    app.dependency_overrides.pop(_get_apikey_service, None)

@pytest_asyncio.fixture
async def ngac_client(ngac_service, ngac_accounts_service):
    """AsyncClient with auth and service factory overridden to use the test DB."""
    from xoloapi.ngac.controller import get_ngac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    from xoloapi.middleware.apikey import _get_apikey_service

    app.dependency_overrides[MX.get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_ngac_service]    = lambda: ngac_service
    app.dependency_overrides[get_accounts_service] = lambda: ngac_accounts_service
    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as client:
        yield client

    app.dependency_overrides.pop(MX.get_current_user, None)
    app.dependency_overrides.pop(get_ngac_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)
    app.dependency_overrides.pop(_get_apikey_service, None)
