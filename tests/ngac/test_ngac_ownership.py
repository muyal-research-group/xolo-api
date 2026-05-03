"""
Retail store ownership test suite.

Use case
────────
Alice owns a retail store and sets up its NGAC policy:

  PolicyClass        : RetailPolicy
  UserAttributes     : StoreOwner, Worker
  ObjectAttributes   : StoreInventory, StoreShift
  Objects (resources): product-123, shift-morning
  User nodes         : alice-node (owner), bob-node (worker), carol-node (worker)

Access rules (associations)
────────────────────────────
  Worker     --[sell]-------------------------------> StoreInventory, StoreShift
  StoreOwner --[sell, fire_worker, end_shift]-------> StoreInventory, StoreShift

Business rules this suite verifies
────────────────────────────────────
  1. Workers can sell products and sign shift objects.
  2. Only the store owner can fire a worker or end a shift.
  3. Firing Bob (removing his Worker assignment) revokes his access immediately.
  4. Firing Bob leaves Carol's access untouched.
  5. Workers cannot mutate any NGAC node owned by Alice.
  6. A superadmin bypasses all ownership checks.
"""
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

import commonx.dto.xolo as DTO
from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.accounts.dependencies import get_accounts_service
from xoloapi.accounts.dto import CreateAccountDTO
from xoloapi.accounts.infrastructure.mongo_repository import MongoAccountsRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.errors.base import AccessDeniedError
from option import Ok
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.ngac.dto import (
    AssignDTO, AssociateDTO, CheckAccessDTO,
    CreateNodeDTO, RemoveAssignmentDTO,
)
from xoloapi.ngac.enums import NodeType
from xoloapi.ngac.service import NGACService
from tests.ngac.conftest import _DB_NAME, _MONGO_URI

# ── Principals ─────────────────────────────────────────────────────────────

ALICE_KEY = "alice-store-owner"
BOB_KEY   = "bob-worker"
CAROL_KEY = "carol-worker"
ADMIN_KEY = "superadmin-key"
ACCOUNT_ID = "acc-ngac-own"


def _dto_user(key: str, username: str) -> DTO.UserDTO:
    return DTO.UserDTO(
        key=key, username=username, first_name=username,
        last_name="", email=f"{username}@store.com", profile_photo="",
    )


ALICE = _dto_user(ALICE_KEY, "alice")
BOB   = _dto_user(BOB_KEY,   "bob")
CAROL = _dto_user(CAROL_KEY, "carol")
ADMIN = _dto_user(ADMIN_KEY, "admin")


class _FakeAPIKeyService:
    async def validate(self, raw_key: str, required_scope: str):
        return Ok(APIKey(
            key_id="test-key",
            key_hash="hash",
            key_prefix="test",
            account_id=ACCOUNT_ID,
            name="Test key",
            scopes=[APIKeyScope.ALL, APIKeyScope.NGAC],
            created_by="tests",
        ))


def _path(path: str) -> str:
    return f"/api/v4/accounts/{ACCOUNT_ID}/ngac{path}"


@pytest_asyncio.fixture
async def ngac_http_accounts_service():
    client = AsyncIOMotorClient(_MONGO_URI)
    db = client[_DB_NAME]
    service = AccountsService(
        repository=MongoAccountsRepository(
            collection=db[CollectionNames.ACCOUNTS_COLLECTION_NAME],
        )
    )
    await db[CollectionNames.ACCOUNTS_COLLECTION_NAME].delete_many({"account_id": ACCOUNT_ID})
    await service.create_account(CreateAccountDTO(account_id=ACCOUNT_ID, name="NGAC Ownership Account"))
    yield service
    await db[CollectionNames.ACCOUNTS_COLLECTION_NAME].delete_many({"account_id": ACCOUNT_ID})
    client.close()


# ── Store graph fixture (service-level) ────────────────────────────────────

@pytest_asyncio.fixture
async def store(ngac_service: NGACService):
    """
    Builds the full retail NGAC graph owned by Alice and returns a dict
    of every node ID plus the four association IDs.
    """
    svc = ngac_service

    async def node(name: str, ntype: NodeType) -> str:
        r = await svc.create_node(ACCOUNT_ID, CreateNodeDTO(name=name, node_type=ntype), owner_id=ALICE_KEY)
        assert r.is_ok, r.unwrap_err()
        return r.unwrap()

    async def link(from_id: str, to_id: str) -> None:
        r = await svc.assign(ACCOUNT_ID, AssignDTO(from_id=from_id, to_id=to_id), owner_id=ALICE_KEY)
        assert r.is_ok, r.unwrap_err()

    async def associate(ua_id: str, oa_id: str, ops: list[str]) -> str:
        r = await svc.associate(
            ACCOUNT_ID,
            AssociateDTO(user_attribute_id=ua_id, object_attribute_id=oa_id, operations=ops),
            owner_id=ALICE_KEY,
        )
        assert r.is_ok, r.unwrap_err()
        return r.unwrap()

    # ── Nodes ──────────────────────────────────────────────────────────────
    pc         = await node("RetailPolicy",   NodeType.POLICY_CLASS)
    ua_owner   = await node("StoreOwner",     NodeType.USER_ATTRIBUTE)
    ua_worker  = await node("Worker",         NodeType.USER_ATTRIBUTE)
    oa_inv     = await node("StoreInventory", NodeType.OBJECT_ATTRIBUTE)
    oa_shift   = await node("StoreShift",     NodeType.OBJECT_ATTRIBUTE)
    alice_node = await node("alice-node",     NodeType.USER)
    bob_node   = await node("bob-node",       NodeType.USER)
    carol_node = await node("carol-node",     NodeType.USER)
    product    = await node("product-123",    NodeType.OBJECT)
    shift      = await node("shift-morning",  NodeType.OBJECT)

    # ── Structure ──────────────────────────────────────────────────────────
    await link(ua_owner,   pc)
    await link(ua_worker,  pc)
    await link(oa_inv,     pc)
    await link(oa_shift,   pc)
    await link(alice_node, ua_owner)
    await link(bob_node,   ua_worker)
    await link(carol_node, ua_worker)
    await link(product,    oa_inv)
    await link(shift,      oa_shift)

    # ── Associations ───────────────────────────────────────────────────────
    worker_inv_id   = await associate(ua_worker, oa_inv,   ["sell"])
    worker_shift_id = await associate(ua_worker, oa_shift, ["sell"])
    owner_inv_id    = await associate(ua_owner,  oa_inv,   ["sell", "fire_worker", "end_shift"])
    owner_shift_id  = await associate(ua_owner,  oa_shift, ["sell", "fire_worker", "end_shift"])

    return {
        "pc": pc,
        "ua_owner": ua_owner,   "ua_worker": ua_worker,
        "oa_inv": oa_inv,       "oa_shift": oa_shift,
        "alice_node": alice_node,
        "bob_node":   bob_node,
        "carol_node": carol_node,
        "product": product,     "shift": shift,
        "worker_inv_id":   worker_inv_id,
        "worker_shift_id": worker_shift_id,
        "owner_inv_id":    owner_inv_id,
        "owner_shift_id":  owner_shift_id,
    }


# ── HTTP client fixtures ───────────────────────────────────────────────────

def _make_client(user: DTO.UserDTO, svc: NGACService, extra_admin_keys: set[str] | None = None):
    from xoloapi.ngac.controller import get_ngac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    import xoloapi.config as Cfg

    captured_keys = Cfg.XOLO_SUPER_ADMIN_TOKENS

    app.dependency_overrides[MX.get_current_user] = lambda: user
    app.dependency_overrides[get_ngac_service]    = lambda: svc
    if extra_admin_keys is not None:
        Cfg.XOLO_SUPER_ADMIN_TOKENS = extra_admin_keys

    return app, captured_keys


@pytest_asyncio.fixture
async def alice_client(ngac_service: NGACService, ngac_http_accounts_service):
    from xoloapi.ngac.controller import get_ngac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    from xoloapi.middleware.apikey import _get_apikey_service

    app.dependency_overrides[MX.get_current_user] = lambda: ALICE
    app.dependency_overrides[get_ngac_service]    = lambda: ngac_service
    app.dependency_overrides[get_accounts_service] = lambda: ngac_http_accounts_service
    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as c:
        yield c
    app.dependency_overrides.pop(MX.get_current_user, None)
    app.dependency_overrides.pop(get_ngac_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)
    app.dependency_overrides.pop(_get_apikey_service, None)


@pytest_asyncio.fixture
async def bob_client(ngac_service: NGACService, ngac_http_accounts_service):
    from xoloapi.ngac.controller import get_ngac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    from xoloapi.middleware.apikey import _get_apikey_service

    app.dependency_overrides[MX.get_current_user] = lambda: BOB
    app.dependency_overrides[get_ngac_service]    = lambda: ngac_service
    app.dependency_overrides[get_accounts_service] = lambda: ngac_http_accounts_service
    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as c:
        yield c
    app.dependency_overrides.pop(MX.get_current_user, None)
    app.dependency_overrides.pop(get_ngac_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)
    app.dependency_overrides.pop(_get_apikey_service, None)


@pytest_asyncio.fixture
async def admin_client(ngac_service: NGACService, ngac_http_accounts_service):
    from xoloapi.ngac.controller import get_ngac_service
    from xoloapi.server import app
    import xoloapi.middleware as MX
    import xoloapi.config as Cfg
    from xoloapi.middleware.apikey import _get_apikey_service

    original_keys = Cfg.XOLO_SUPER_ADMIN_TOKENS
    Cfg.XOLO_SUPER_ADMIN_TOKENS = {ADMIN_KEY}

    app.dependency_overrides[MX.get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_ngac_service]    = lambda: ngac_service
    app.dependency_overrides[get_accounts_service] = lambda: ngac_http_accounts_service
    app.dependency_overrides[_get_apikey_service] = lambda: _FakeAPIKeyService()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-key"},
    ) as c:
        yield c

    Cfg.XOLO_SUPER_ADMIN_TOKENS = original_keys
    app.dependency_overrides.pop(MX.get_current_user, None)
    app.dependency_overrides.pop(get_ngac_service, None)
    app.dependency_overrides.pop(get_accounts_service, None)
    app.dependency_overrides.pop(_get_apikey_service, None)


# ═══════════════════════════════════════════════════════════════════════════
# 1. ACCESS CONTROL — what each role is allowed to do on resources
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_worker_can_sell_product(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["product"], operation="sell")
    )
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_worker_can_sell_during_shift(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["shift"], operation="sell")
    )
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_all_workers_can_sell(ngac_service: NGACService, store: dict):
    """Both Bob and Carol inherit Worker → can sell."""
    for worker_node in [store["bob_node"], store["carol_node"]]:
        result = await ngac_service.check_access(
            ACCOUNT_ID,
            CheckAccessDTO(user_id=worker_node, object_id=store["product"], operation="sell")
        )
        assert result.unwrap().allowed is True, f"{worker_node} should be able to sell"


@pytest.mark.asyncio
async def test_worker_cannot_fire_worker(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["product"], operation="fire_worker")
    )
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_worker_cannot_end_shift(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["shift"], operation="end_shift")
    )
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_owner_can_sell_product(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["alice_node"], object_id=store["product"], operation="sell")
    )
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_owner_can_fire_worker_on_product(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["alice_node"], object_id=store["product"], operation="fire_worker")
    )
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_owner_can_end_shift(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["alice_node"], object_id=store["shift"], operation="end_shift")
    )
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_owner_can_fire_worker_on_shift_resource(ngac_service: NGACService, store: dict):
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["alice_node"], object_id=store["shift"], operation="fire_worker")
    )
    assert result.unwrap().allowed is True


# ═══════════════════════════════════════════════════════════════════════════
# 2. FIRING — removing a Worker assignment revokes access
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fired_worker_loses_sell_access(ngac_service: NGACService, store: dict):
    before = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["product"], operation="sell")
    )
    assert before.unwrap().allowed is True

    # Owner fires Bob: remove bob-node → Worker assignment
    result = await ngac_service.remove_assignment(
        ACCOUNT_ID,
        RemoveAssignmentDTO(from_id=store["bob_node"], to_id=store["ua_worker"]),
        requester_key=ALICE_KEY,
    )
    assert result.is_ok

    after = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["product"], operation="sell")
    )
    assert after.unwrap().allowed is False


@pytest.mark.asyncio
async def test_fired_worker_loses_shift_access(ngac_service: NGACService, store: dict):
    await ngac_service.remove_assignment(
        ACCOUNT_ID,
        RemoveAssignmentDTO(from_id=store["bob_node"], to_id=store["ua_worker"]),
        requester_key=ALICE_KEY,
    )
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["bob_node"], object_id=store["shift"], operation="sell")
    )
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_carol_unaffected_when_bob_is_fired(ngac_service: NGACService, store: dict):
    """Firing Bob should not revoke Carol's access — she is in Worker independently."""
    await ngac_service.remove_assignment(
        ACCOUNT_ID,
        RemoveAssignmentDTO(from_id=store["bob_node"], to_id=store["ua_worker"]),
        requester_key=ALICE_KEY,
    )
    result = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["carol_node"], object_id=store["product"], operation="sell")
    )
    assert result.unwrap().allowed is True


@pytest.mark.asyncio
async def test_worker_cannot_fire_another_worker(ngac_service: NGACService, store: dict):
    """Bob cannot remove Carol's assignment — he does not own the Worker UA."""
    result = await ngac_service.remove_assignment(
        ACCOUNT_ID,
        RemoveAssignmentDTO(from_id=store["carol_node"], to_id=store["ua_worker"]),
        requester_key=BOB_KEY,
    )
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)

    # Carol's access is intact
    check = await ngac_service.check_access(
        ACCOUNT_ID,
        CheckAccessDTO(user_id=store["carol_node"], object_id=store["product"], operation="sell")
    )
    assert check.unwrap().allowed is True


# ═══════════════════════════════════════════════════════════════════════════
# 3. NODE OWNERSHIP — workers cannot mutate Alice's nodes
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_worker_cannot_delete_product_node(ngac_service: NGACService, store: dict):
    result = await ngac_service.delete_node(ACCOUNT_ID, store["product"], requester_key=BOB_KEY)
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)


@pytest.mark.asyncio
async def test_worker_cannot_delete_owner_user_node(ngac_service: NGACService, store: dict):
    result = await ngac_service.delete_node(ACCOUNT_ID, store["alice_node"], requester_key=BOB_KEY)
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)


@pytest.mark.asyncio
async def test_worker_cannot_delete_policy_class(ngac_service: NGACService, store: dict):
    result = await ngac_service.delete_node(ACCOUNT_ID, store["pc"], requester_key=BOB_KEY)
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)


@pytest.mark.asyncio
async def test_owner_can_delete_own_node(ngac_service: NGACService, store: dict):
    result = await ngac_service.delete_node(ACCOUNT_ID, store["product"], requester_key=ALICE_KEY)
    assert result.is_ok


@pytest.mark.asyncio
async def test_worker_cannot_remove_owner_assignment(ngac_service: NGACService, store: dict):
    """Bob cannot remove alice-node → StoreOwner (Alice owns that assignment)."""
    result = await ngac_service.remove_assignment(
        ACCOUNT_ID,
        RemoveAssignmentDTO(from_id=store["alice_node"], to_id=store["ua_owner"]),
        requester_key=BOB_KEY,
    )
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)


@pytest.mark.asyncio
async def test_worker_cannot_remove_association(ngac_service: NGACService, store: dict):
    """Bob cannot remove Worker → StoreInventory association (owned by Alice)."""
    result = await ngac_service.remove_association(
        ACCOUNT_ID,
        store["worker_inv_id"],
        requester_key=BOB_KEY,
    )
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)


@pytest.mark.asyncio
async def test_worker_cannot_assign_rogue_user_to_owner_ua(ngac_service: NGACService, store: dict):
    """Bob creates a node he owns, but cannot assign it into StoreOwner UA (Alice's)."""
    rogue_r = await ngac_service.create_node(
        ACCOUNT_ID,
        CreateNodeDTO(name="rogue", node_type=NodeType.USER),
        owner_id=BOB_KEY,
    )
    assert rogue_r.is_ok
    result = await ngac_service.assign(
        ACCOUNT_ID,
        AssignDTO(from_id=rogue_r.unwrap(), to_id=store["ua_owner"]),
        owner_id=BOB_KEY,
    )
    assert result.is_err
    assert isinstance(result.unwrap_err(), AccessDeniedError)


# ═══════════════════════════════════════════════════════════════════════════
# 4. SUPERADMIN — bypasses all ownership checks
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_superadmin_can_delete_any_node(ngac_service: NGACService, store: dict):
    result = await ngac_service.delete_node(
        ACCOUNT_ID, store["product"], requester_key=ADMIN_KEY, is_admin=True
    )
    assert result.is_ok


@pytest.mark.asyncio
async def test_superadmin_can_remove_any_assignment(ngac_service: NGACService, store: dict):
    result = await ngac_service.remove_assignment(
        ACCOUNT_ID,
        RemoveAssignmentDTO(from_id=store["alice_node"], to_id=store["ua_owner"]),
        requester_key=ADMIN_KEY,
        is_admin=True,
    )
    assert result.is_ok


@pytest.mark.asyncio
async def test_superadmin_can_remove_any_association(ngac_service: NGACService, store: dict):
    result = await ngac_service.remove_association(
        ACCOUNT_ID,
        store["owner_inv_id"],
        requester_key=ADMIN_KEY,
        is_admin=True,
    )
    assert result.is_ok


# ═══════════════════════════════════════════════════════════════════════════
# 5. HTTP — ownership returns correct status codes
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_http_worker_delete_node_returns_403(bob_client: AsyncClient, store: dict):
    res = await bob_client.delete(_path(f"/nodes/{store['product']}"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_http_owner_delete_own_node_returns_204(alice_client: AsyncClient, store: dict):
    res = await alice_client.delete(_path(f"/nodes/{store['product']}"))
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_http_superadmin_delete_any_node_returns_204(admin_client: AsyncClient, store: dict):
    res = await admin_client.delete(_path(f"/nodes/{store['product']}"))
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_http_worker_remove_assignment_returns_403(bob_client: AsyncClient, store: dict):
    res = await bob_client.request(
        method="DELETE",
        url=_path("/assign"),
        json={"from_id": store["alice_node"], "to_id": store["ua_owner"]},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_http_owner_remove_own_assignment_returns_204(alice_client: AsyncClient, store: dict):
    res = await alice_client.request(
        method="DELETE",
        url=_path("/assign"),
        json={"from_id": store["alice_node"], "to_id": store["ua_owner"]},
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_http_worker_remove_association_returns_403(bob_client: AsyncClient, store: dict):
    res = await bob_client.delete(_path(f"/associate/{store['worker_inv_id']}"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_http_superadmin_remove_any_association_returns_204(
    admin_client: AsyncClient, store: dict
):    
    res = await admin_client.delete(_path(f"/associate/{store['owner_inv_id']}"))
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_http_worker_assign_to_owner_ua_returns_403(
    bob_client: AsyncClient, ngac_service: NGACService, store: dict
):
    """Bob creates a node he owns via HTTP then tries to assign it into StoreOwner UA."""
    create_res = await bob_client.post(
        _path("/nodes"),
        json={"name": "rogue-user", "node_type": "user"},
    )
    assert create_res.status_code == 201
    rogue_id = create_res.json()["node_id"]

    assign_res = await bob_client.post(
        _path("/assign"),
        json={"from_id": rogue_id, "to_id": store["ua_owner"]},
    )
    assert assign_res.status_code == 403
