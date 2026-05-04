import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from option import Err, Ok

import commonx.errors as EX

from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.application.licenses_service import LicensesService
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.scopes.infrastructure.mongo_repository import MongoScopesRepository
from xoloapi.users.application.users_service import UsersService
from xoloapi.users.dependencies import get_users_service
from xoloapi.users.infrastructure.mongo_password_reset_repository import MongoPasswordResetRepository
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository

from tests.support import MONGO_URI, app_client, get_redis_client, reset_database, reset_redis
from xoloapi.server import app

DB_NAME = "xolo_test_users"
API_KEY_ACCOUNT_ID = "acc-users"
COLLECTIONS = [
    CollectionNames.USERS_COLLECTION_NAME,
    CollectionNames.PASSWORD_RESET_TOKENS_COLLECTION_NAME,
    CollectionNames.LICENSES_COLLECTION_NAME,
    CollectionNames.SCOPES_COLLECTION_NAME,
    CollectionNames.SCOPE_USER_COLLECTION_NAME,
]


@pytest_asyncio.fixture
async def users_db():
    await reset_database(DB_NAME, COLLECTIONS)
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    yield db
    client.close()
    await reset_database(DB_NAME, COLLECTIONS)


@pytest_asyncio.fixture
async def users_cache():
    await reset_redis()
    client = await get_redis_client()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def users_repo(users_db, users_cache):
    yield MongoUsersRepository(
        collection=users_db[CollectionNames.USERS_COLLECTION_NAME],
        cache_redis=users_cache,
    )


class RecordingUsersMailer:
    def __init__(self):
        self.password_reset_messages: list[dict] = []
        self.welcome_messages: list[dict] = []
        self.fail_welcome = False

    async def send_password_reset_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        reset_token: str,
        reset_url: str | None,
        expires_in: str,
    ):
        self.password_reset_messages.append(
            {
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
                "reset_token": reset_token,
                "reset_url": reset_url,
                "expires_in": expires_in,
            }
        )
        return Ok(True)

    async def send_welcome_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        username: str,
        scope: str,
    ):
        self.welcome_messages.append(
            {
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
                "username": username,
                "scope": scope,
            }
        )
        if self.fail_welcome:
            return Err(EX.ServerError(raw_detail="welcome mail failed"))
        return Ok(True)


@pytest_asyncio.fixture
async def users_password_reset_repo(users_db):
    yield MongoPasswordResetRepository(
        collection=users_db[CollectionNames.PASSWORD_RESET_TOKENS_COLLECTION_NAME],
    )


@pytest_asyncio.fixture
async def users_mailer():
    yield RecordingUsersMailer()


@pytest_asyncio.fixture
async def users_service(users_db, users_repo, users_password_reset_repo, users_mailer):
    yield UsersService(
        repository=users_repo,
        scopes_repository=MongoScopesRepository(
            collection=users_db[CollectionNames.SCOPES_COLLECTION_NAME],
            scope_user_collection=users_db[CollectionNames.SCOPE_USER_COLLECTION_NAME],
        ),
        licenses_service=LicensesService(
            repository=MongoLicensesRepository(users_db[CollectionNames.LICENSES_COLLECTION_NAME]),
            users_repository=MongoUsersRepository(users_db[CollectionNames.USERS_COLLECTION_NAME]),
            secret_key="TEST",
        ),
        password_reset_repository=users_password_reset_repo,
        users_mailer=users_mailer,
    )


@pytest_asyncio.fixture
async def users_client(users_service):
    app.dependency_overrides[get_users_service] = lambda: users_service
    async with app_client(
        DB_NAME,
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.ALL],
        api_key_account_id=API_KEY_ACCOUNT_ID,
        admin_token="admin-token",
        account_ids=[API_KEY_ACCOUNT_ID, "acc-other"],
    ) as client:
        yield client
    app.dependency_overrides.pop(get_users_service, None)
