import pytest
from xoloapi.server import app
from fastapi.testclient import TestClient
from commonx.dto.xolo import CreateUserDTO


@pytest.mark.asyncio
async def test_create_group():
    with TestClient(app) as client:
        res = client.post(
            url ="/api/v4/users",
            json=CreateUserDTO(
                username="imss",
                first_name="Ignacio",
                last_name="Sanchez",
                email="x@x.com",
                password="password123",
                profile_photo=""
            ).model_dump()
        )
        assert res.status_code==201
        # res = client.post(
        #     url="/api/v4/acl/groups",
        #     json={
        #         "name":"imss"
        #     },
        #     timeout=120
        # )
        # print(res.content)
        # assert res.status_code==200
    
