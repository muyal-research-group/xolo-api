import pytest
import pytest_asyncio
import xoloapi.services as SX
import xoloapi.repositories as RX 
import xoloapi.db as DX
import xoloapi.db.cache as CacheX
from xoloapi.db.constants import CollectionNames
import xoloapi.dto as DTO   
import xoloapi.middleware as MX
from motor.motor_asyncio import AsyncIOMotorClient
from option import Ok
from starlette.requests import Request

from xoloapi.users.infrastructure.mongo_password_reset_repository import MongoPasswordResetRepository


class _RecordingUsersMailer:
    async def send_password_reset_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        reset_token: str,
        reset_url: str | None,
        expires_in: str,
    ):
        return Ok(True)

    async def send_welcome_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        username: str,
        scope: str,
    ):
        return Ok(True)


@pytest_asyncio.fixture
async def user_service():
    client  = AsyncIOMotorClient("mongodb://localhost:27018")
    database_name = "test_mictlan_db"
    db      = client[database_name]
    client.drop_database(name_or_database=database_name)
    for col_name in [CollectionNames.USERS_COLLECTION_NAME,
                     CollectionNames.LICENSES_COLLECTION_NAME,
                     CollectionNames.SCOPES_COLLECTION_NAME,
                     CollectionNames.SCOPE_USER_COLLECTION_NAME]:
        await db.drop_collection(col_name)

    await CacheX.connect_to_redis()
    cache_redis = CacheX.get_redis_client()
    await cache_redis.flushall(asynchronous=True)

    users_collection = db[CollectionNames.USERS_COLLECTION_NAME]
    # users_collection.
    # DX.get_collection(CollectionNames.USERS_COLLECTION_NAME)

    service = SX.UsersService(
        repository = RX.UsersRepository( 
            collection = users_collection,
            cache_redis = cache_redis

        ),
        licenses_service  = SX.LicensesService(
            repository = RX.LicensesRepository(
                collection = db[CollectionNames.LICENSES_COLLECTION_NAME]
            ),
            secret_key = "TEST",
            users_repository = RX.UsersRepository(
                collection = users_collection,
                cache_redis = None
            )
        ),
        scopes_repository =RX.ScopesRepository(
            collection= db[CollectionNames.SCOPES_COLLECTION_NAME],
            scope_user_collection= db[CollectionNames.SCOPE_USER_COLLECTION_NAME]
        ),
        password_reset_repository=MongoPasswordResetRepository(
            collection=db[CollectionNames.PASSWORD_RESET_TOKENS_COLLECTION_NAME],
        ),
        users_mailer=_RecordingUsersMailer(),
    )
    yield service

    # C. Cleanup
    await CacheX.close_redis_connection()
    client.close()

@pytest_asyncio.fixture
async def scope_service():
    client  = AsyncIOMotorClient("mongodb://localhost:27018")
    db      = client["test_mictlan_db"]
    # client.drop_database()
    # for col_name in [CollectionNames.SCOPES_COLLECTION_NAME,
                    #  CollectionNames.SCOPE_USER_COLLECTION_NAME]:
        # await db.drop_collection(col_name)


    scopes_collection = db[CollectionNames.SCOPES_COLLECTION_NAME]
    scope_user_collection = db[CollectionNames.SCOPE_USER_COLLECTION_NAME]

    service = SX.ScopesService(
        repository = RX.ScopesRepository( 
            collection = scopes_collection,
            scope_user_collection= scope_user_collection
        ),
        licenses_repository = RX.LicensesRepository(
            collection = db[CollectionNames.LICENSES_COLLECTION_NAME]
        ),
    )
    yield service

    # C. Cleanup
    client.close()

@pytest_asyncio.fixture
async def license_service():
    client  = AsyncIOMotorClient("mongodb://localhost:27018")
    db      = client["test_mictlan_db"]
    # client.drop_database()
    # for col_name in [CollectionNames.LICENSES_COLLECTION_NAME]:
        # await db.drop_collection(col_name)


    licenses_collection = db[CollectionNames.LICENSES_COLLECTION_NAME]

    service = SX.LicensesService(
        repository = RX.LicensesRepository( 
            collection = licenses_collection
        ),
        secret_key = "TEST",
        users_repository = RX.UsersRepository(
            collection = db[CollectionNames.USERS_COLLECTION_NAME],
            cache_redis = None
        )
    )
    yield service

    # C. Cleanup
    client.close()


@pytest.mark.asyncio
async def test_main_logic(
    user_service: SX.UsersService,
    scope_service: SX.ScopesService,
    license_service: SX.LicensesService
):
    account_id = "acc-test"
    user_data = DTO.CreateUserDTO(
        username="testuser",
        first_name="Test",
        last_name="User",
        email="t@t.com",
        password="securepassword",
        profile_photo=""
    )
    scope_name = "testscope"

    created_user_result = await user_service.create_user(account_id, user_data)
    assert created_user_result.is_ok , f"User creation failed: {created_user_result.unwrap_err()}"
    user_id = created_user_result.unwrap().key
    user = await user_service.get_by_id(user_id=user_id)
    assert user.is_ok, f"Fetching created user failed: {user.unwrap_err()}"
    user = user.unwrap()
    assert user.username == user_data.username
    assert user.email == user_data.email

    # create scope
    scope_dto = DTO.CreateScopeDTO(
        name=scope_name
    )
    created_scope_result = await scope_service.create(account_id, scope_dto)
    assert created_scope_result.is_ok, f"Scope creation failed: {created_scope_result.unwrap_err()}"

    assigned_scope_result = await scope_service.assign(
        account_id=account_id,
        dto = DTO.AssignScopeDTO(
            name=scope_name,
            username=user_data.username
        )
    )
    assert assigned_scope_result.is_ok, f"Assigning scope failed: {assigned_scope_result.unwrap_err()}"

    create_license_result = await license_service.assign_license(
        account_id=account_id,
        dto = DTO.AssignLicenseDTO(
            username   = user_data.username,
            scope      = scope_name,
            expires_in = "1d"
        )
    )
    assert create_license_result.is_ok, f"Creating license failed: {create_license_result.unwrap_err()}"

    x = await user_service.auth(
        account_id=account_id,
        dto = DTO.AuthDTO(
            username = user_data.username,
            password = user_data.password,
            scope    = scope_name
        )
    )
    assert x.is_ok, f"Authentication failed: {x.unwrap_err()}"
    auth_data    = x.unwrap()
    access_token = auth_data.access_token
    # auth_data.temporal_secret
    
    request = Request({"type": "http", "headers": [], "path_params": {"account_id": account_id}})
    is_authenticated = await MX.__get_current_user(
        request             = request,
        token               = access_token,
        temporal_secret_key = auth_data.temporal_secret,
        users_service       = user_service
    )
    assert is_authenticated.key == user.key

    

    # print(x)
