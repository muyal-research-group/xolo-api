import pytest

import commonx.dto.xolo as DTO

from tests.support import app, app_client
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.db.constants import CollectionNames
from xoloapi.users.dependencies import get_users_mailer
from xoloapi.users.infrastructure.noop_users_mailer import NoOpUsersMailer


COLLECTIONS = [
    CollectionNames.USERS_COLLECTION_NAME,
    CollectionNames.LICENSES_COLLECTION_NAME,
    CollectionNames.SCOPES_COLLECTION_NAME,
    CollectionNames.SCOPE_USER_COLLECTION_NAME,
]


@pytest.mark.asyncio
async def test_full_flow():
    account_id = "acc-legacy-flow"
    username = "legacy_flow_user"
    password = "password123"
    scope = "legacy-flow-scope"

    app.dependency_overrides[get_users_mailer] = lambda: NoOpUsersMailer()
    try:
        async with app_client(
            "xolo_test_legacy_flow",
            COLLECTIONS,
            api_key_scopes=[APIKeyScope.ALL, APIKeyScope.SCOPES],
            api_key_account_id=account_id,
            admin_token="admin-token",
            account_ids=[account_id],
        ) as client:
            scope_response = await client.post(
                f"/api/v4/accounts/{account_id}/scopes",
                json=DTO.CreateScopeDTO(name=scope).model_dump(),
            )
            assert scope_response.status_code == 200

            signup_response = await client.post(
                f"/api/v4/accounts/{account_id}/users/signup",
                json=DTO.SignUpDTO(
                    username=username,
                    first_name="Legacy",
                    last_name="Flow",
                    email=f"{username}@x.com",
                    password=password,
                    profile_photo="",
                    scope=scope,
                    expiration="15m",
                ).model_dump(),
            )
            assert signup_response.status_code == 201, signup_response.text

            auth_response = await client.post(
                f"/api/v4/accounts/{account_id}/users/auth",
                json=DTO.AuthDTO(
                    username=username,
                    password=password,
                    expiration="15min",
                    renew_token=False,
                    scope=scope,
                ).model_dump(),
            )
            assert auth_response.status_code == 200
            assert auth_response.json()["username"] == username
    finally:
        app.dependency_overrides.pop(get_users_mailer, None)
