from fastapi import Depends, HTTPException

import xoloapi.config as Cfg
from xoloapi.db import get_collection
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


def get_cache_redis():
    from xoloapi.db.cache import get_redis_client

    cache = get_redis_client()
    if cache is None:
        raise HTTPException(status_code=500, detail="Cache is not available")
    return cache


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
    users_collection = get_collection(CollectionNames.USERS_COLLECTION_NAME)
    users_repository = MongoUsersRepository(collection=users_collection, cache_redis=cache)
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
    )
