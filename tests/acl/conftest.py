import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
from xoloapi.db.constants import CollectionNames
from tests.support import MONGO_URI

DB_NAME = "xolo_test_acl_repo"
ACCOUNT_ID = "acc-acl-repo"


@pytest_asyncio.fixture
async def acl_policy_repo():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    await db.drop_collection(CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME)
    yield MongoResourcePolicyRepository(
        db=db,
        collection_name=CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    )
    await db.drop_collection(CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME)
    client.close()
