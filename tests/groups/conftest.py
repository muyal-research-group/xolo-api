import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from xoloapi.db.constants import CollectionNames
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from tests.support import MONGO_URI

DB_NAME = "xolo_test_groups_repo"
ACCOUNT_ID = "acc-groups-repo"


@pytest_asyncio.fixture
async def groups_repo():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    await db.drop_collection(CollectionNames.ACL_GROUPS_COLLECTION_NAME)
    await db.drop_collection(CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME)
    yield MongoSecurityGroupRepository(
        db=db,
        groups_col=CollectionNames.ACL_GROUPS_COLLECTION_NAME,
        members_col=CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
    )
    await db.drop_collection(CollectionNames.ACL_GROUPS_COLLECTION_NAME)
    await db.drop_collection(CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME)
    client.close()
