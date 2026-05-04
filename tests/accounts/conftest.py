import pytest_asyncio

from xoloapi.db.constants import CollectionNames

from tests.support import app_client

DB_NAME = "xolo_test_accounts"
COLLECTIONS = [CollectionNames.ACCOUNTS_COLLECTION_NAME]


@pytest_asyncio.fixture
async def accounts_client():
    async with app_client(DB_NAME, COLLECTIONS, admin_token="admin-token") as client:
        yield client
