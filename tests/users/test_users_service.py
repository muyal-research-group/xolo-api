import datetime
import pytest
import pytest_asyncio

import commonx.dto.xolo as DTO
import xoloapi.users.dto as UDTO
from xoloapi.acl.domain.aggregates import AccessGrant, ResourcePolicy
from xoloapi.acl.domain.value_objects import Permission, Principal, PrincipalType
from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.groups.domain.aggregates import SecurityGroup
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from xoloapi.licenses.application.licenses_service import LicensesService
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.ngac.domain.aggregates import NGACNode
from xoloapi.ngac.enums import NodeType
from xoloapi.ngac.infrastructure.mongo_ngac_repository import MongoNGACRepository
from xoloapi.scopes.infrastructure.mongo_repository import MongoScopesRepository
from xoloapi.users.application.users_service import UsersService
from xoloapi.users.infrastructure.mongo_password_reset_repository import MongoPasswordResetRepository
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository

ACCOUNT_ID = "acc-test"

_EXTRA_COLLECTIONS = [
    CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    CollectionNames.ACL_GROUPS_COLLECTION_NAME,
    CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
    CollectionNames.NGAC_NODES_COLLECTION_NAME,
    CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
    CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
]


@pytest_asyncio.fixture
async def users_service_full(users_db, users_repo, users_password_reset_repo, users_mailer):
    for col in _EXTRA_COLLECTIONS:
        await users_db.drop_collection(col)
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
        acl_repository=MongoResourcePolicyRepository(
            db=users_db,
            collection_name=CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
        ),
        groups_repository=MongoSecurityGroupRepository(
            db=users_db,
            groups_col=CollectionNames.ACL_GROUPS_COLLECTION_NAME,
            members_col=CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
        ),
        ngac_repository=MongoNGACRepository(
            db=users_db,
            nodes_col=CollectionNames.NGAC_NODES_COLLECTION_NAME,
            assignments_col=CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
            associations_col=CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
        ),
    )
    for col in _EXTRA_COLLECTIONS:
        await users_db.drop_collection(col)


@pytest.mark.asyncio
async def test_users_service_end_to_end(users_service, users_mailer):
    scope_result = await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    assert scope_result.is_ok

    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok
    assert len(users_mailer.welcome_messages) == 1
    assert users_mailer.welcome_messages[0]["recipient_email"] == "alice@example.com"

    auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert auth.is_ok

    auth_data = auth.unwrap()
    verified = await users_service.verify(
        ACCOUNT_ID,
        DTO.VerifyDTO(
            access_token=auth_data.access_token,
            username="alice",
            secret=auth_data.temporal_secret,
        )
    )
    assert verified.is_ok

    disabled = await users_service.disable_user(ACCOUNT_ID, DTO.EnableOrDisableUserDTO(username="alice"))
    assert disabled.is_ok
    enabled = await users_service.enable_user(ACCOUNT_ID, DTO.EnableOrDisableUserDTO(username="alice"))
    assert enabled.is_ok

    updated = await users_service.update_password(
        ACCOUNT_ID,
        DTO.UpdateUserPasswordDTO(username="alice", password="new-password")
    )
    assert updated.is_ok

    logout = await users_service.logout(ACCOUNT_ID, DTO.LogoutDTO(username="alice", access_token=auth_data.access_token))
    assert logout.is_ok


@pytest.mark.asyncio
async def test_users_service_password_reset_request_and_confirm(users_service, users_mailer):
    scope_result = await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    assert scope_result.is_ok

    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok

    request_result = await users_service.request_password_recovery(
        ACCOUNT_ID,
        UDTO.PasswordRecoveryRequestDTO(identifier="alice")
    )
    assert request_result.is_ok
    assert len(users_mailer.password_reset_messages) == 1

    confirm_result = await users_service.confirm_password_recovery(
        ACCOUNT_ID,
        UDTO.PasswordRecoveryConfirmDTO(
            token=users_mailer.password_reset_messages[0]["reset_token"],
            password="new-password",
        )
    )
    assert confirm_result.is_ok

    auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="new-password",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert auth.is_ok


@pytest.mark.asyncio
async def test_users_service_password_reset_request_is_neutral_for_unknown_user(users_service, users_mailer):
    request_result = await users_service.request_password_recovery(
        ACCOUNT_ID,
        UDTO.PasswordRecoveryRequestDTO(identifier="missing-user")
    )
    assert request_result.is_ok
    assert users_mailer.password_reset_messages == []


@pytest.mark.asyncio
async def test_users_service_signup_survives_welcome_mail_failure(users_service, users_mailer):
    users_mailer.fail_welcome = True
    scope_result = await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    assert scope_result.is_ok

    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok
    assert len(users_mailer.welcome_messages) == 1


@pytest.mark.asyncio
async def test_users_service_delete_user_cascades_related_records(users_service):
    await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok

    deleted = await users_service.delete_user(ACCOUNT_ID, "alice")
    assert deleted.is_ok

    users = await users_service.list_users(ACCOUNT_ID)
    assert users.is_ok
    assert users.unwrap() == []


@pytest.mark.asyncio
async def test_users_service_block_user_invalidates_active_session(users_service):
    await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok

    auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert auth.is_ok

    blocked = await users_service.block_user(ACCOUNT_ID, "alice")
    assert blocked.is_ok

    verify = await users_service.verify(
        ACCOUNT_ID,
        DTO.VerifyDTO(
            access_token=auth.unwrap().access_token,
            username="alice",
            secret=auth.unwrap().temporal_secret,
        )
    )
    assert verify.is_err

    blocked_auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert blocked_auth.is_err

    unblocked = await users_service.unblock_user(ACCOUNT_ID, "alice")
    assert unblocked.is_ok

    reauth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert reauth.is_ok


@pytest.mark.asyncio
async def test_delete_user_cascades_acl_groups_and_ngac(users_service_full, users_db):
    acl_repo = users_service_full.acl_repository
    groups_repo = users_service_full.groups_repository
    ngac_repo = users_service_full.ngac_repository

    await users_service_full.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    signup = await users_service_full.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        ),
    )
    assert signup.is_ok
    user_id = (await users_service_full.repository.find_by_username(ACCOUNT_ID, "alice")).unwrap().key

    # Seed ACL resource policy owned by the user
    policy = ResourcePolicy(
        account_id=ACCOUNT_ID,
        resource_id="bucket-1",
        grants=[AccessGrant(
            grant_id="g-1",
            principal=Principal(type=PrincipalType.USER, id=user_id),
            permissions={Permission.READ},
            is_owner=True,
        )],
    )
    await acl_repo.save(policy)

    # Seed a security group owned by the user
    now = datetime.datetime.now(datetime.timezone.utc)
    group = SecurityGroup(
        account_id=ACCOUNT_ID, group_id="g-alice",
        name="alice-group", owner_id=user_id,
        created_at=now, updated_at=now,
    )
    await groups_repo.save(group)
    await groups_repo.add_member(ACCOUNT_ID, "g-alice", "u-other")

    # Seed an NGAC node owned by the user
    ngac_node = NGACNode(
        account_id=ACCOUNT_ID, node_id="n-alice",
        node_type=NodeType.USER, name="alice-node",
        owner_id=user_id,
    )
    await ngac_repo.create_node(ngac_node)

    deleted = await users_service_full.delete_user(ACCOUNT_ID, "alice")
    assert deleted.is_ok

    assert (await users_service_full.list_users(ACCOUNT_ID)).unwrap() == []
    assert (await acl_repo.list_all(ACCOUNT_ID)).unwrap() == []
    assert (await groups_repo.list_all(ACCOUNT_ID)).unwrap() == []
    assert (await ngac_repo.list_nodes(ACCOUNT_ID)).unwrap() == []
