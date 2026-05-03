import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.scopes.application.scopes_service import ScopesService
from xoloapi.scopes.infrastructure.mongo_repository import MongoScopesRepository

from tests.support import MONGO_URI, app_client, reset_database

DB_NAME = "xolo_test_scopes"
ACCOUNT_ID = "acc-scopes"
COLLECTIONS = [
    CollectionNames.SCOPES_COLLECTION_NAME,
    CollectionNames.SCOPE_USER_COLLECTION_NAME,
    CollectionNames.LICENSES_COLLECTION_NAME,
]


@pytest_asyncio.fixture
async def scopes_db():
    await reset_database(DB_NAME, COLLECTIONS)
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    yield db
    client.close()
    await reset_database(DB_NAME, COLLECTIONS)


@pytest_asyncio.fixture
async def scopes_repo(scopes_db):
    yield MongoScopesRepository(
        collection=scopes_db[CollectionNames.SCOPES_COLLECTION_NAME],
        scope_user_collection=scopes_db[CollectionNames.SCOPE_USER_COLLECTION_NAME],
    )


@pytest_asyncio.fixture
async def scopes_service(scopes_repo):
    client = scopes_repo.collection.database.client
    db = client[DB_NAME]
    yield ScopesService(
        repository=scopes_repo,
        licenses_repository=MongoLicensesRepository(db[CollectionNames.LICENSES_COLLECTION_NAME]),
    )


@pytest_asyncio.fixture
async def scopes_client():
    async with app_client(DB_NAME, COLLECTIONS, admin_token="admin-token", account_ids=[ACCOUNT_ID]) as client:
        yield client
