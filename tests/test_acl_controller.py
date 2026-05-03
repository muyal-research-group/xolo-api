import pytest
from xoloapi.server import app
from fastapi.testclient import TestClient
import commonx.dto.xolo as DTO
from uuid import uuid4
from option import Ok

import xoloapi.config as Cfg
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.middleware.apikey import _get_apikey_service


class _FakeAPIKeyService:
    def __init__(self, account_id: str):
        self._account_id = account_id

    async def validate(self, raw_key: str, required_scope: str):
        return Ok(APIKey(
            key_id="test-key",
            key_hash="hash",
            key_prefix="test",
            account_id=self._account_id,
            name="Test key",
            scopes=[APIKeyScope.ALL, APIKeyScope.SCOPES],
            created_by="tests",
        ))

@pytest.mark.asyncio
async def test_full_flow():
    original_tokens = Cfg.XOLO_SUPER_ADMIN_TOKENS
    original_legacy_tokens = Cfg.XOLO_SUPER_ADMIN_KEYS
    Cfg.XOLO_SUPER_ADMIN_TOKENS = {"admin-token"}
    Cfg.XOLO_SUPER_ADMIN_KEYS = Cfg.XOLO_SUPER_ADMIN_TOKENS
    with TestClient(app) as client:
        uid      = uuid4().hex
        account_id = f"acc-{uid[:12]}"
        app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService(account_id)
        username = f"user_{uid}"
        password = "password123"
        scope    = f"test{uid[:6]}"

        create_account = client.post(
            url="/api/v4/accounts",
            json={"account_id": account_id, "name": "Test account"},
            headers={"X-Admin-Token": "admin-token"},
        )
        assert create_account.status_code == 201

        res = client.post(
            url  = f"/api/v4/accounts/{account_id}/scopes",
            json = DTO.CreateScopeDTO(
                name = scope,
            ).model_dump(),
            headers={"X-Admin-Token": "admin-token"},
        )
        assert res.status_code==200
        

        res = client.post(
            url =f"/api/v4/accounts/{account_id}/users/signup",
            json=DTO.SignUpDTO(
                username=username,
                first_name="Ignacio",
                last_name="Sanchez",
                email=f"{username}@x.com",
                password=password,
                profile_photo="",
                scope =scope,
                expiration="15m"
            ).model_dump(),
            headers={"X-API-Key": "test-key"},
        )
        assert res.status_code==201
        res = client.post(
            url=f"/api/v4/accounts/{account_id}/users/auth",
            json=DTO.AuthDTO(
                password    = password,
                username    = username,
                expiration  = "15min",
                renew_token = False,
                scope       = scope
            ).model_dump(),
            headers={"X-API-Key": "test-key"},
            timeout=120
        )
        assert res.status_code==200
        # res = client.post(
        #     url="/api/v4/acl/groups",
        #     json={
        #         "name":"imss"
        #     },
        #     timeout=120
        # )
        # print(res.content)
        # assert res.status_code==200
    app.dependency_overrides.pop(_get_apikey_service, None)
    Cfg.XOLO_SUPER_ADMIN_TOKENS = original_tokens
    Cfg.XOLO_SUPER_ADMIN_KEYS = original_legacy_tokens
    
