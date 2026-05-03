import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.application.licenses_service import LicensesService
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository

from tests.support import MONGO_URI, app_client, reset_database

DB_NAME = "xolo_test_licenses"
ACCOUNT_ID = "acc-licenses"
COLLECTIONS = [
    CollectionNames.USERS_COLLECTION_NAME,
    CollectionNames.LICENSES_COLLECTION_NAME,
]


@pytest_asyncio.fixture
async def licenses_db():
    await reset_database(DB_NAME, COLLECTIONS)
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    yield db
    client.close()
    await reset_database(DB_NAME, COLLECTIONS)


@pytest_asyncio.fixture
async def licenses_repo(licenses_db):
    yield MongoLicensesRepository(licenses_db[CollectionNames.LICENSES_COLLECTION_NAME])


@pytest_asyncio.fixture
async def licenses_service(licenses_db, licenses_repo):
    yield LicensesService(
        repository=licenses_repo,
        users_repository=MongoUsersRepository(licenses_db[CollectionNames.USERS_COLLECTION_NAME]),
        secret_key="TEST",
    )


@pytest_asyncio.fixture
async def licenses_client():
    async with app_client(DB_NAME, COLLECTIONS, admin_token="admin-token", account_ids=[ACCOUNT_ID, "acc-other"]) as client:
        yield client
