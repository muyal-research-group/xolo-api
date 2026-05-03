import pytest
import httpx
from xolo.abac.models import AccessRequest,AttributeComponent



@pytest.mark.skip(reason="Requires an external localhost server and real auth/config; not part of the in-process test suite.")
@pytest.mark.asyncio
async def test_evaluate_batch():
    res = httpx.post(url="http://localhost:10000/api/v4/policies/evaluate/batch",json=
        [
            AccessRequest(
                subject=AttributeComponent(attribute="a",value="x"),
                asset=AttributeComponent(attribute="a",value="x"),
                space=AttributeComponent(attribute="a",value="x"),
                time=AttributeComponent(attribute="a",value="x"),
                action=AttributeComponent(attribute="a",value="x"),
            ).model_dump()
        ]
    ,timeout=120)
    print(res.content)
    assert res.status_code == 200


@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_create_user():
    res = httpx.post(url="http://localhost:10000/api/v4/users/",json={
        "username":"jcastillo",
        "first_name":"Ignacio",
        "last_name":"Castillo",
        "email":"jcastillo@cinvestav.mx", 
        "password":"bc24a0412c775cb3ee62e881283100cfbf3744a4467035c46397ccb09f50862c",
        "profile":"",
        "role":"jcastillo"

    },timeout=120)
    print(res.content)
    assert res.status_code == 201


@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_create_scope():
    res = httpx.post(url="http://localhost:10000/api/v4/scopes/",json={
        "name":"imss"
    },timeout=120)
    print(res.content)
    assert res.status_code==200
@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_assign_scope():
    res = httpx.post(url="http://localhost:10000/api/v4/scopes/assign",json={
        "name":"imss", 
        "username":"jcastillo"
    },timeout=120)
    print(res.content)
    assert res.status_code==200
@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_create_license():
    res = httpx.post(url="http://localhost:10000/api/v4/licenses/",json={
        "username":"jcastillo",
        "scope":"imss",
        "expires_in":"20m",
        "force":True
    },headers={"Secret":"ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"},timeout=120)
    print(res.content)
    assert res.status_code==200

@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_auth_user():
    res = httpx.post(url="http://localhost:10000/api/v4/users/auth",json={
        "username":"jcastillo",
        "password":"bc24a0412c775cb3ee62e881283100cfbf3744a4467035c46397ccb09f50862c",
        "scope": "imss"
    },timeout=120)
    print(res.content)
    assert res.status_code == 200

@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_get_resources_by_username():
    res = httpx.get(url="http://localhost:10000/api/v4/users/jcastillo/resources",timeout=120)
    print(res.content)
    assert res.status_code == 200
@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_grantx():
    res = httpx.post(url="http://localhost:10000/api/v4/users/grantx",timeout=120,json={
        "grants":{
            "test":{"b1":["read"]}
        },
        "role":"jcastillo"
    })
    print(res.content)
    assert res.status_code == 204
@pytest.mark.skip("")
@pytest.mark.asyncio
async def test_grants():
    res = httpx.post(url="http://localhost:10000/api/v4/users/grants",timeout=120,json={
        "grants":{
            "jcastillo":{"$XOLO-API":["grant"]}
        }
    },headers={"Secret":"ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2"})
    print(res.content)
    assert res.status_code == 204
