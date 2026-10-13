from fastapi import Depends, HTTPException
from option import Err, Ok

import xoloapi.config as Cfg
from xoloapi.db import get_collection, get_database
from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.application.licenses_service import LicensesService
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository
from xoloapi.scopes.infrastructure.mongo_repository import MongoScopesRepository
from xoloapi.users.application.users_service import UsersService
from xoloapi.users.infrastructure.mongo_password_reset_repository import MongoPasswordResetRepository
from xoloapi.users.infrastructure.cloudflare_users_mailer import CloudflareUsersMailer
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository
from xoloapi.users.infrastructure.noop_users_mailer import NoOpUsersMailer
from xoloapi.users.infrastructure.smtp_users_mailer import SMTPUsersMailer
from xoloapi.errors.base import InternalError, NotFoundError


def get_users_repository() -> MongoUsersRepository:
    return MongoUsersRepository(
        collection=get_collection(CollectionNames.USERS_COLLECTION_NAME),
    )


def get_cache_redis():
    from xoloapi.db.cache import get_redis_client

    cache = get_redis_client()
    if cache is None:
        raise HTTPException(status_code=500, detail="Cache is not available")
    return cache


class AuthUserLookupService:
    """Minimal user lookup used while validating bearer tokens."""

    def __init__(self, repository: MongoUsersRepository):
        self.repository = repository

    async def get_by_id(self, user_id: str, account_id: str | None = None):
        try:
            user = await self.repository.find_by_id(user_id, account_id=account_id)
            if user.is_none:
                return Err(NotFoundError("User", user_id))
            return Ok(user.unwrap())
        except Exception as error:
            return Err(InternalError("Failed to look up authenticated user", cause=error))


def get_auth_users_service() -> AuthUserLookupService:
    # This lookup deliberately has no Redis, mailer, or authorization-policy
    # dependencies. Missing credentials can therefore be rejected before any
    # unrelated infrastructure is required.
    return AuthUserLookupService(repository=get_users_repository())


def get_users_mailer():
    provider = Cfg.XOLO_EMAIL_PROVIDER
    if provider == "smtp":
        return SMTPUsersMailer()
    if provider == "cloudflare":
        return CloudflareUsersMailer()
    if provider == "noop":
        return NoOpUsersMailer()
    raise HTTPException(status_code=500, detail=f"Unsupported XOLO_EMAIL_PROVIDER: {provider}")


def get_users_service(cache=Depends(get_cache_redis), users_mailer=Depends(get_users_mailer)) -> UsersService:
    from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
    from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
    from xoloapi.ngac.infrastructure.mongo_ngac_repository import MongoNGACRepository

    users_collection = get_collection(CollectionNames.USERS_COLLECTION_NAME)
    users_repository = MongoUsersRepository(collection=users_collection, cache_redis=cache)
    db = get_database()
    return UsersService(
        repository=users_repository,
        scopes_repository=MongoScopesRepository(
            collection=get_collection(CollectionNames.SCOPES_COLLECTION_NAME),
            scope_user_collection=get_collection(CollectionNames.SCOPE_USER_COLLECTION_NAME),
        ),
        licenses_service=LicensesService(
            users_repository=MongoUsersRepository(collection=users_collection),
            repository=MongoLicensesRepository(
                collection=get_collection(CollectionNames.LICENSES_COLLECTION_NAME),
            ),
            secret_key=Cfg.XOLO_LICENSE_SECRET_KEY,
        ),
        password_reset_repository=MongoPasswordResetRepository(
            collection=get_collection(CollectionNames.PASSWORD_RESET_TOKENS_COLLECTION_NAME),
        ),
        users_mailer=users_mailer,
        acl_repository=MongoResourcePolicyRepository(
            db=db,
            collection_name=CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
        ),
        groups_repository=MongoSecurityGroupRepository(
            db=db,
            groups_col=CollectionNames.ACL_GROUPS_COLLECTION_NAME,
            members_col=CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
        ),
        ngac_repository=MongoNGACRepository(
            db=db,
            nodes_col=CollectionNames.NGAC_NODES_COLLECTION_NAME,
            assignments_col=CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
            associations_col=CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
        ),
    )
