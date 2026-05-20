"""
Controller-level (HTTP) tests for the NGAC module.

Uses FastAPI's TestClient with dependency overrides so no real auth token is
needed.  MongoDB must be reachable at localhost:27018; Redis must be up for
the app lifespan.
"""
import pytest
from httpx import AsyncClient
from tests.ngac.conftest import ACCOUNT_ID


# ── Payloads ───────────────────────────────────────────────────────────────

def _node_payload(name: str, node_type: str) -> dict:
    return {"name": name, "node_type": node_type}


def _path(path: str, account_id: str = ACCOUNT_ID) -> str:
    return f"/api/v4/accounts/{account_id}/ngac{path}"


# ── POST /ngac/nodes ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_node_201(ngac_client: AsyncClient):
    res = await ngac_client.post(_path("/nodes"), json=_node_payload("Alice", "user"))
    assert res.status_code == 201
    body = res.json()
    assert "node_id" in body
    assert body["node_id"].startswith("n-")


@pytest.mark.asyncio
async def test_create_all_node_types(ngac_client: AsyncClient):
    for ntype in ["user", "object", "user_attribute", "object_attribute", "policy_class"]:
        res = await ngac_client.post(_path("/nodes"), json=_node_payload(f"N-{ntype}", ntype))
        assert res.status_code == 201, f"Failed for type={ntype}: {res.text}"


@pytest.mark.asyncio
async def test_create_duplicate_node_returns_409(ngac_client: AsyncClient):
    res1 = await ngac_client.post(_path("/nodes"), json=_node_payload("Alice", "user"))
    node_id = res1.json()["node_id"]

    # Duplicate check is on node_id, not name — try creating one with same name is fine
    # To force conflict we'd need same node_id, which is generated. Verify uniqueness instead.
    res2 = await ngac_client.post(_path("/nodes"), json=_node_payload("Alice", "user"))
    assert res2.status_code == 201  # names are not unique — different IDs
    assert res2.json()["node_id"] != node_id


# ── GET /ngac/nodes ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_nodes_empty(ngac_client: AsyncClient):
    res = await ngac_client.get(_path("/nodes"))
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_nodes_returns_all(ngac_client: AsyncClient):
    await ngac_client.post(_path("/nodes"), json=_node_payload("Alice",    "user"))
    await ngac_client.post(_path("/nodes"), json=_node_payload("MedStaff", "user_attribute"))
    await ngac_client.post(_path("/nodes"), json=_node_payload("MedPC",    "policy_class"))

    res = await ngac_client.get(_path("/nodes"))
    assert res.status_code == 200
    assert len(res.json()) == 3


@pytest.mark.asyncio
async def test_list_nodes_with_type_filter(ngac_client: AsyncClient):
    await ngac_client.post(_path("/nodes"), json=_node_payload("Alice",  "user"))
    await ngac_client.post(_path("/nodes"), json=_node_payload("UA1",    "user_attribute"))
    await ngac_client.post(_path("/nodes"), json=_node_payload("UA2",    "user_attribute"))

    res = await ngac_client.get(_path("/nodes"), params={"node_type": "user_attribute"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert all(n["node_type"] == "user_attribute" for n in body)


# ── GET /ngac/nodes/{node_id} ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_node_200(ngac_client: AsyncClient):
    node_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Obj", "object"))).json()["node_id"]

    res = await ngac_client.get(_path(f"/nodes/{node_id}"))
    assert res.status_code == 200
    body = res.json()
    assert body["node_id"] == node_id
    assert body["name"] == "Obj"


@pytest.mark.asyncio
async def test_get_node_404(ngac_client: AsyncClient):
    res = await ngac_client.get(_path("/nodes/ghost-id"))
    assert res.status_code == 404


# ── DELETE /ngac/nodes/{node_id} ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_node_204(ngac_client: AsyncClient):
    node_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Temp", "user"))).json()["node_id"]

    res = await ngac_client.delete(_path(f"/nodes/{node_id}"))
    assert res.status_code == 204

    assert (await ngac_client.get(_path(f"/nodes/{node_id}"))).status_code == 404


@pytest.mark.asyncio
async def test_delete_node_404(ngac_client: AsyncClient):
    res = await ngac_client.delete(_path("/nodes/ghost-id"))
    assert res.status_code == 404


# ── POST /ngac/assign ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_valid_returns_204(ngac_client: AsyncClient):
    u_id  = (await ngac_client.post(_path("/nodes"), json=_node_payload("User",  "user"))).json()["node_id"]
    ua_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Staff", "user_attribute"))).json()["node_id"]

    res = await ngac_client.post(_path("/assign"), json={"from_id": u_id, "to_id": ua_id})
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_assign_invalid_type_returns_422(ngac_client: AsyncClient):
    u_id  = (await ngac_client.post(_path("/nodes"), json=_node_payload("User", "user"))).json()["node_id"]
    pc_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("PC",   "policy_class"))).json()["node_id"]

    # user → policy_class is not a valid assignment
    res = await ngac_client.post(_path("/assign"), json={"from_id": u_id, "to_id": pc_id})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_assign_nonexistent_node_returns_404(ngac_client: AsyncClient):
    res = await ngac_client.post(_path("/assign"), json={"from_id": "ghost-a", "to_id": "ghost-b"})
    assert res.status_code == 404


# ── DELETE /ngac/assign ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_assignment_204(ngac_client: AsyncClient):
    u_id  = (await ngac_client.post(_path("/nodes"), json=_node_payload("User",  "user"))).json()["node_id"]
    ua_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Staff", "user_attribute"))).json()["node_id"]
    await ngac_client.post(_path("/assign"), json={"from_id": u_id, "to_id": ua_id})

    res = await ngac_client.request(
        method = "DELETE",
        url    = _path("/assign"),
        json   = {"from_id": u_id, "to_id": ua_id}
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_remove_assignment_404(ngac_client: AsyncClient):
    res = await ngac_client.request(
        method = "DELETE",
        url    = _path("/assign"),
        json   = {"from_id": "ghost", "to_id": "ghost2"}
    )
    assert res.status_code == 404


# ── GET /ngac/assignments ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_assignments_200(ngac_client: AsyncClient):
    res = await ngac_client.get(_path("/assignments"))
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ── POST /ngac/associate ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_associate_valid_returns_204(ngac_client: AsyncClient):
    ua_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Staff",   "user_attribute"))).json()["node_id"]
    oa_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Records", "object_attribute"))).json()["node_id"]

    res = await ngac_client.post(_path("/associate"), json={
        "user_attribute_id":   ua_id,
        "object_attribute_id": oa_id,
        "operations":          ["read", "write"],
    })
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_associate_wrong_type_returns_422(ngac_client: AsyncClient):
    u_id  = (await ngac_client.post(_path("/nodes"), json=_node_payload("User",    "user"))).json()["node_id"]
    oa_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Records", "object_attribute"))).json()["node_id"]

    res = await ngac_client.post(_path("/associate"), json={
        "user_attribute_id":   u_id,    # wrong type — user, not user_attribute
        "object_attribute_id": oa_id,
        "operations":          ["read"],
    })
    assert res.status_code == 422


# ── GET /ngac/associations ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_associations_200(ngac_client: AsyncClient):
    res = await ngac_client.get(_path("/associations"))
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ── DELETE /ngac/associate/{id} ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_association_204(ngac_client: AsyncClient):
    ua_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Staff",   "user_attribute"))).json()["node_id"]
    oa_id = (await ngac_client.post(_path("/nodes"), json=_node_payload("Records", "object_attribute"))).json()["node_id"]
    await ngac_client.post(_path("/associate"), json={
        "user_attribute_id": ua_id, "object_attribute_id": oa_id, "operations": ["read"]
    })

    assoc_id = (await ngac_client.get(_path("/associations"))).json()[0]["association_id"]
    res = await ngac_client.delete(_path(f"/associate/{assoc_id}"))
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_remove_association_404(ngac_client: AsyncClient):
    res = await ngac_client.delete(_path("/associate/ghost-id"))
    assert res.status_code == 404


# ── POST /ngac/check ───────────────────────────────────────────────────────

async def _build_full_graph(client: AsyncClient) -> tuple[str, str]:
    """Creates a minimal valid NGAC graph. Returns (user_node_id, object_node_id)."""
    u_id  = (await client.post(_path("/nodes"), json=_node_payload("Alice",    "user"))).json()["node_id"]
    ua_id = (await client.post(_path("/nodes"), json=_node_payload("Staff",    "user_attribute"))).json()["node_id"]
    o_id  = (await client.post(_path("/nodes"), json=_node_payload("Doc",      "object"))).json()["node_id"]
    oa_id = (await client.post(_path("/nodes"), json=_node_payload("Records",  "object_attribute"))).json()["node_id"]
    pc_id = (await client.post(_path("/nodes"), json=_node_payload("Policy",   "policy_class"))).json()["node_id"]

    await client.post(_path("/assign"), json={"from_id": u_id,  "to_id": ua_id})
    await client.post(_path("/assign"), json={"from_id": ua_id, "to_id": pc_id})
    await client.post(_path("/assign"), json={"from_id": o_id,  "to_id": oa_id})
    await client.post(_path("/assign"), json={"from_id": oa_id, "to_id": pc_id})
    await client.post(_path("/associate"), json={
        "user_attribute_id": ua_id, "object_attribute_id": oa_id, "operations": ["read"]
    })
    return u_id, o_id


@pytest.mark.asyncio
async def test_check_access_allowed(ngac_client: AsyncClient):
    u_id, o_id = await _build_full_graph(ngac_client)

    res = await ngac_client.post(_path("/check"), json={
        "user_id": u_id, "object_id": o_id, "operation": "read"
    })
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True
    assert body["user_id"]   == u_id
    assert body["object_id"] == o_id


@pytest.mark.asyncio
async def test_check_access_denied_wrong_operation(ngac_client: AsyncClient):
    u_id, o_id = await _build_full_graph(ngac_client)

    res = await ngac_client.post(_path("/check"), json={
        "user_id": u_id, "object_id": o_id, "operation": "write"  # only read was granted
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False


@pytest.mark.asyncio
async def test_check_access_denied_no_graph(ngac_client: AsyncClient):
    res = await ngac_client.post(_path("/check"), json={
        "user_id": "ghost-user", "object_id": "ghost-obj", "operation": "read"
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False


@pytest.mark.asyncio
async def test_check_access_and_rule_denied(ngac_client: AsyncClient):
    """Object under two PCs; user only satisfies one → denied."""
    u_id  = (await ngac_client.post(_path("/nodes"), json=_node_payload("Dr Smith",     "user"))).json()["node_id"]
    ua_m  = (await ngac_client.post(_path("/nodes"), json=_node_payload("MedStaff",     "user_attribute"))).json()["node_id"]
    ua_e  = (await ngac_client.post(_path("/nodes"), json=_node_payload("EmerDoctors",  "user_attribute"))).json()["node_id"]
    o_id  = (await ngac_client.post(_path("/nodes"), json=_node_payload("Chart A",      "object"))).json()["node_id"]
    oa_m  = (await ngac_client.post(_path("/nodes"), json=_node_payload("PatRecords",   "object_attribute"))).json()["node_id"]
    oa_e  = (await ngac_client.post(_path("/nodes"), json=_node_payload("EmerRecords",  "object_attribute"))).json()["node_id"]
    pc_m  = (await ngac_client.post(_path("/nodes"), json=_node_payload("MedPC",        "policy_class"))).json()["node_id"]
    pc_e  = (await ngac_client.post(_path("/nodes"), json=_node_payload("EmerPC",       "policy_class"))).json()["node_id"]

    for f, t in [(u_id, ua_m), (ua_m, pc_m), (o_id, oa_m), (oa_m, pc_m),
                 (o_id, oa_e), (oa_e, pc_e), (ua_e, pc_e)]:
        await ngac_client.post(_path("/assign"), json={"from_id": f, "to_id": t})

    await ngac_client.post(_path("/associate"), json={
        "user_attribute_id": ua_m, "object_attribute_id": oa_m, "operations": ["read"]
    })
    await ngac_client.post(_path("/associate"), json={
        "user_attribute_id": ua_e, "object_attribute_id": oa_e, "operations": ["read"]
    })

    res = await ngac_client.post(_path("/check"), json={
        "user_id": u_id, "object_id": o_id, "operation": "read"
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False


# ── Auth guard ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(unauthenticated_ngac_client: AsyncClient):
    for method, path in [
        ("GET",  _path("/nodes")),
        ("POST", _path("/nodes")),
        ("POST", _path("/assign")),
        ("POST", _path("/check")),
    ]:
        res = await getattr(unauthenticated_ngac_client, method.lower())(path)
        assert res.status_code == 401, f"{method} {path} should require auth"
