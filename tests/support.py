from contextlib import asynccontextmanager
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from option import Ok, Err
import redis.asyncio as aioredis

import xoloapi.config as Cfg
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db import close_mongo_connection, connect_to_mongo
from xoloapi.db.cache import close_redis_connection, connect_to_redis
from xoloapi.db.constants import CollectionNames
from xoloapi.server import app

MONGO_URI = "mongodb://localhost:27018"
REDIS_URI = "redis://localhost:6379/15"


class FakeAPIKeyService:
    def __init__(self, scopes: list[APIKeyScope], account_id: str):
        self._scopes = scopes
        self._account_id = account_id

    async def validate(self, raw_key: str, required_scope: str):
        # Create the API key object
        api_key = APIKey(
            key_id="test-key",
            key_hash="hash",
            key_prefix="test",
            account_id=self._account_id,
            name="Test key",
            scopes=self._scopes,
            created_by="tests",
        )
        
        # Check if the required scope is in the key's scopes (matching real validation)
        if not api_key.allows(required_scope):
            from xoloapi.errors import AccessDeniedError
            error = AccessDeniedError(
                f"API key does not have the '{required_scope}' scope",
                metadata={"required_scope": required_scope, "key_scopes": [s.value for s in api_key.scopes]},
            )
            return Err(error)
        
        return Ok(api_key)


async def reset_database(db_name: str, collections: list[str]) -> None:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[db_name]
    for collection in collections:
        await db.drop_collection(collection)
    client.close()


async def seed_accounts(db_name: str, account_ids: list[str]) -> None:
    if not account_ids:
        return
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[db_name]
    now = datetime.now(timezone.utc)
    await db[CollectionNames.ACCOUNTS_COLLECTION_NAME].insert_many(
        [
            {
                "account_id": account_id,
                "name": f"Account {account_id}",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for account_id in sorted(set(account_ids))
        ]
    )
    client.close()


async def get_redis_client():
    return aioredis.from_url(REDIS_URI, decode_responses=True)


async def reset_redis() -> None:
    client = await get_redis_client()
    await client.flushdb()
    await client.aclose()


@asynccontextmanager
async def app_client(
    db_name: str,
    collections: list[str],
    api_key_scopes: list[APIKeyScope] | None = None,
    api_key_account_id: str = "acc-test",
    admin_token: str | None = None,
    account_ids: list[str] | None = None,
):
    old_mongo_uri = Cfg.XOLO_MONGODB_URI
    old_db_name = Cfg.XOLO_MONGODB_DATABASE_NAME
    old_redis_uri = Cfg.XOLO_CACHE_REDIS_URI
    old_admin_tokens = Cfg.XOLO_SUPER_ADMIN_TOKENS
    old_legacy_admin_tokens = Cfg.XOLO_SUPER_ADMIN_KEYS

    Cfg.XOLO_MONGODB_URI = MONGO_URI
    Cfg.XOLO_MONGODB_DATABASE_NAME = db_name
    Cfg.XOLO_CACHE_REDIS_URI = REDIS_URI
    if admin_token is not None:
        Cfg.XOLO_SUPER_ADMIN_TOKENS = {admin_token}
        Cfg.XOLO_SUPER_ADMIN_KEYS = Cfg.XOLO_SUPER_ADMIN_TOKENS

    seeded_account_ids = list(account_ids or [])
    if api_key_scopes is not None and api_key_account_id not in seeded_account_ids:
        seeded_account_ids.append(api_key_account_id)
    managed_collections = list(collections)
    if seeded_account_ids and CollectionNames.ACCOUNTS_COLLECTION_NAME not in managed_collections:
        managed_collections.append(CollectionNames.ACCOUNTS_COLLECTION_NAME)

    await reset_database(db_name, managed_collections)
    await reset_redis()
    await seed_accounts(db_name, seeded_account_ids)
    await connect_to_mongo()
    await connect_to_redis()
    try:
        if api_key_scopes is not None:
            from xoloapi.middleware.apikey import _get_apikey_service

            app.dependency_overrides[_get_apikey_service] = lambda: FakeAPIKeyService(api_key_scopes, api_key_account_id)

        headers = {}
        if api_key_scopes is not None:
            headers["X-API-Key"] = "test-key"
        if admin_token is not None:
            headers["X-Admin-Token"] = admin_token

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=headers or None,
        ) as client:
            yield client
    finally:
        if api_key_scopes is not None:
            from xoloapi.middleware.apikey import _get_apikey_service

            app.dependency_overrides.pop(_get_apikey_service, None)
        await close_redis_connection()
        await close_mongo_connection()
        await reset_database(db_name, managed_collections)
        await reset_redis()
        Cfg.XOLO_MONGODB_URI = old_mongo_uri
        Cfg.XOLO_MONGODB_DATABASE_NAME = old_db_name
        Cfg.XOLO_CACHE_REDIS_URI = old_redis_uri
        Cfg.XOLO_SUPER_ADMIN_TOKENS = old_admin_tokens
        Cfg.XOLO_SUPER_ADMIN_KEYS = old_legacy_admin_tokens
