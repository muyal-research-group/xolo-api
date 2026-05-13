"""
Tests for API key authorization on scopes and licenses endpoints.

Verifies that account owners can:
1. Create scopes using API keys with "scopes" scope
2. Assign scopes to users using API keys
3. Create and delete licenses using API keys with "licenses" scope
4. Admin tokens and API keys can be used on same endpoints
"""
import pytest
import commonx.dto.xolo as DTO

from xoloapi.db.constants import CollectionNames
from tests.support import app_client

DB_NAME = "xolo_test_apikey_auth_scopes_licenses"
COLLECTIONS = [
    CollectionNames.ACCOUNTS_COLLECTION_NAME,
    CollectionNames.USERS_COLLECTION_NAME,
    CollectionNames.SCOPES_COLLECTION_NAME,
    CollectionNames.SCOPE_USER_COLLECTION_NAME,
    CollectionNames.LICENSES_COLLECTION_NAME,
    CollectionNames.API_KEYS_COLLECTION_NAME,
]

ACCOUNT_A = "acc-owner-a"
USER_ALICE = "alice"
ADMIN_TOKEN = "admin-token-test"


async def create_test_user(client, username: str, scope: str) -> bool:
    """Helper to create a test user via signup endpoint."""
    res = await client.post(
        "/api/v4/users/signup",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json=DTO.SignUpDTO(
            username=username,
            first_name="Test",
            last_name="User",
            email=f"{username}@example.com",
            password="password123",
            profile_photo="",
            scope=scope,
            expiration="15m",
        ).model_dump()
    )
    return res.status_code == 200


@pytest.mark.asyncio
async def test_account_owner_can_create_scopes_with_api_key():
    """Account owner with API key scoped to 'scopes' can create scopes."""
    async with app_client(
        DB_NAME, 
        COLLECTIONS, 
        admin_token=ADMIN_TOKEN,
        account_ids=[ACCOUNT_A],
    ) as client:
        # Admin creates initial scope and user
        await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "INIT"},
        )
        await create_test_user(client, USER_ALICE, "INIT")

        # Admin creates API key with "scopes" scope for account A
        apikey_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/apikeys",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "scopes-admin", "scopes": ["scopes"]},
        )
        assert apikey_res.status_code == 201
        raw_key = apikey_res.json()["key"]

        # Account owner uses API key to create scope
        create_scope_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-API-Key": raw_key},
            json={"name": "READ"},
        )
        assert create_scope_res.status_code == 200
        assert create_scope_res.json()["name"] == "READ"


@pytest.mark.asyncio
async def test_account_owner_can_assign_scopes_with_api_key():
    """Account owner can assign scopes to users using API key."""
    async with app_client(
        DB_NAME, 
        COLLECTIONS, 
        admin_token=ADMIN_TOKEN,
        account_ids=[ACCOUNT_A],
    ) as client:
        # Admin setup: Create scope and user
        await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "INIT"},
        )
        await create_test_user(client, USER_ALICE, "INIT")

        # Admin creates second scope and API key with "scopes" scope
        await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "WRITE"},
        )

        apikey_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/apikeys",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "scopes-admin", "scopes": ["scopes"]},
        )
        raw_key = apikey_res.json()["key"]

        # Account owner assigns scope to user via API key
        assign_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes/assign",
            headers={"X-API-Key": raw_key},
            json={"name": "WRITE", "username": USER_ALICE},
        )
        assert assign_res.status_code == 200


@pytest.mark.asyncio
async def test_account_owner_can_create_licenses_with_api_key():
    """Account owner with API key scoped to 'licenses' can create licenses."""
    async with app_client(
        DB_NAME, 
        COLLECTIONS, 
        admin_token=ADMIN_TOKEN,
        account_ids=[ACCOUNT_A],
    ) as client:
        # Admin setup: Create scope and user
        await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "INIT"},
        )
        await create_test_user(client, USER_ALICE, "INIT")

        # Admin creates API key with "licenses" scope
        apikey_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/apikeys",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "licenses-admin", "scopes": ["licenses"]},
        )
        raw_key = apikey_res.json()["key"]

        # Account owner creates license via API key
        license_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/licenses",
            headers={"X-API-Key": raw_key},
            json={
                "username": USER_ALICE,
                "scope": "INIT",
                "expires_in": "15m",
                "force": True,
            },
        )
        assert license_res.status_code == 200
        assert license_res.json()["ok"] is True
        assert "expires_at" in license_res.json()


@pytest.mark.asyncio
async def test_admin_token_and_api_key_both_work():
    """Both admin token and API key can be used interchangeably on same endpoints."""
    async with app_client(
        DB_NAME, 
        COLLECTIONS, 
        admin_token=ADMIN_TOKEN,
        account_ids=[ACCOUNT_A],
    ) as client:
        # Admin creates API key
        apikey_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/apikeys",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "scopes-admin", "scopes": ["scopes"]},
        )
        raw_key = apikey_res.json()["key"]

        # Create scope with admin token
        await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={"name": "READ"},
        )

        # Create scope with API key
        scope_res = await client.post(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-API-Key": raw_key},
            json={"name": "WRITE"},
        )
        assert scope_res.status_code == 200

        # List with both methods
        list_admin = await client.get(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-Admin-Token": ADMIN_TOKEN},
        )
        list_key = await client.get(
            f"/api/v4/accounts/{ACCOUNT_A}/scopes",
            headers={"X-API-Key": raw_key},
        )

        assert list_admin.status_code == 200
        assert list_key.status_code == 200
        assert len(list_admin.json()) == 2
        assert len(list_key.json()) == 2
