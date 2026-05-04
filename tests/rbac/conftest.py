import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

import commonx.dto.xolo as DTO
import xoloapi.middleware as MX
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames
from xoloapi.rbac.application.rbac_service import RBACService
from xoloapi.rbac.infrastructure.mongo_role_assignment_repository import MongoRoleAssignmentRepository
from xoloapi.rbac.infrastructure.mongo_role_repository import MongoRoleRepository
from tests.support import MONGO_URI, app, app_client, reset_database

DB_NAME = "xolo_test_rbac"
COLLECTIONS = [
    CollectionNames.RBAC_ROLES_COLLECTION_NAME,
    CollectionNames.RBAC_ASSIGNMENTS_COLLECTION_NAME,
]
ACCOUNT_ID = "acc-rbac"

FAKE_USER = DTO.UserDTO(
    key="u-rbac-test",
    username="rbacuser",
    first_name="RBAC",
    last_name="User",
    email="rbac@test.com",
    profile_photo="",
)


@pytest_asyncio.fixture
async def rbac_db():
    await reset_database(DB_NAME, COLLECTIONS)
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    yield db
    client.close()
    await reset_database(DB_NAME, COLLECTIONS)


@pytest_asyncio.fixture
async def rbac_service(rbac_db):
    yield RBACService(
        role_repo=MongoRoleRepository(
            db=rbac_db,
            collection_name=CollectionNames.RBAC_ROLES_COLLECTION_NAME,
        ),
        assignment_repo=MongoRoleAssignmentRepository(
            db=rbac_db,
            collection_name=CollectionNames.RBAC_ASSIGNMENTS_COLLECTION_NAME,
        ),
    )


@pytest_asyncio.fixture
async def rbac_client():
    app.dependency_overrides[MX.get_current_user] = lambda: FAKE_USER
    async with app_client(
        DB_NAME,
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.ALL, APIKeyScope.RBAC],
        api_key_account_id=ACCOUNT_ID,
        account_ids=[ACCOUNT_ID, "acc-other"],
    ) as client:
        yield client
    app.dependency_overrides.pop(MX.get_current_user, None)
