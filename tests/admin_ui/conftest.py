import pytest_asyncio

import xoloapi.config as Cfg
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames
from tests.support import app_client

DB_NAME = "xolo_test_admin_ui"
COLLECTIONS = [
    CollectionNames.ACCOUNTS_COLLECTION_NAME,
    CollectionNames.USERS_COLLECTION_NAME,
    CollectionNames.PASSWORD_RESET_TOKENS_COLLECTION_NAME,
    CollectionNames.LICENSES_COLLECTION_NAME,
    CollectionNames.SCOPES_COLLECTION_NAME,
    CollectionNames.SCOPE_USER_COLLECTION_NAME,
    CollectionNames.API_KEYS_COLLECTION_NAME,
    CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    CollectionNames.ACL_GROUPS_COLLECTION_NAME,
    CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
    CollectionNames.ABAC_POLICIES_COLLECTION_NAME,
    CollectionNames.NGAC_NODES_COLLECTION_NAME,
    CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
    CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
    CollectionNames.RBAC_ROLES_COLLECTION_NAME,
    CollectionNames.RBAC_ASSIGNMENTS_COLLECTION_NAME,
]


@pytest_asyncio.fixture
async def admin_ui_client():
    original_tokens = Cfg.XOLO_SUPER_ADMIN_TOKENS
    original_legacy_tokens = Cfg.XOLO_SUPER_ADMIN_KEYS
    original_session_secret = Cfg.XOLO_ADMIN_UI_SESSION_SECRET
    original_cookie_name = Cfg.XOLO_ADMIN_UI_SESSION_COOKIE_NAME
    original_session_max_age = Cfg.XOLO_ADMIN_UI_SESSION_MAX_AGE
    original_session_secure = Cfg.XOLO_ADMIN_UI_SESSION_SECURE

    Cfg.XOLO_SUPER_ADMIN_TOKENS = {"admin-token"}
    Cfg.XOLO_SUPER_ADMIN_KEYS = Cfg.XOLO_SUPER_ADMIN_TOKENS
    Cfg.XOLO_ADMIN_UI_SESSION_SECRET = "admin-ui-test-secret"
    Cfg.XOLO_ADMIN_UI_SESSION_COOKIE_NAME = "xolo_admin_ui_test"
    Cfg.XOLO_ADMIN_UI_SESSION_MAX_AGE = 3600
    Cfg.XOLO_ADMIN_UI_SESSION_SECURE = False

    async with app_client(
        DB_NAME,
        COLLECTIONS,
        api_key_scopes=[APIKeyScope.ALL],
        api_key_account_id="acc-ui",
        account_ids=["acc-ui"],
    ) as client:
        yield client

    Cfg.XOLO_SUPER_ADMIN_TOKENS = original_tokens
    Cfg.XOLO_SUPER_ADMIN_KEYS = original_legacy_tokens
    Cfg.XOLO_ADMIN_UI_SESSION_SECRET = original_session_secret
    Cfg.XOLO_ADMIN_UI_SESSION_COOKIE_NAME = original_cookie_name
    Cfg.XOLO_ADMIN_UI_SESSION_MAX_AGE = original_session_max_age
    Cfg.XOLO_ADMIN_UI_SESSION_SECURE = original_session_secure
