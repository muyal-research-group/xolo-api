import pytest
from xoloapi.server import app
from fastapi.testclient import TestClient
import commonx.dto.xolo as DTO
from uuid import uuid4

@pytest.mark.asyncio
async def test_full_flow():
    with TestClient(app) as client:
        uid      = uuid4().hex
        username = f"user_{uid}"
        password = "password123"
        scope    = f"test{uid[:6]}"

        res = client.post(
            url  = "/api/v4/scopes",
            json = DTO.CreateScopeDTO(
                name = scope,
            ).model_dump(),
        )
        assert res.status_code==200
        

        res = client.post(
            url ="/api/v4/users/signup",
            json=DTO.SignUpDTO(
                username=username,
                first_name="Ignacio",
                last_name="Sanchez",
                email=f"{username}@x.com",
                password=password,
                profile_photo="",
                scope =scope,
                expiration="15m"
            ).model_dump()
        )
        assert res.status_code==201
        res = client.post(
            url="/api/v4/users/auth",
            json=DTO.AuthDTO(
                password    = password,
                username    = username,
                expiration  = "15min",
                renew_token = False,
                scope       = scope
            ).model_dump(),
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
    
