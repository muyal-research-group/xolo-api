import pytest
from xoloapi.ngac.enums import NodeType
from xoloapi.ngac.domain.aggregates import NGACAssignment, NGACAssociation, NGACNode
from xoloapi.ngac.infrastructure.mongo_ngac_repository import MongoNGACRepository
from tests.ngac.conftest import ACCOUNT_ID


def _node(node_id: str, node_type: NodeType) -> NGACNode:
    return NGACNode(account_id=ACCOUNT_ID, node_id=node_id, node_type=node_type, name=node_id)


def _assignment(from_id: str, to_id: str, idx: int = 0) -> NGACAssignment:
    return NGACAssignment(account_id=ACCOUNT_ID, assignment_id=f"a-{idx}", from_id=from_id, to_id=to_id)


def _association(ua: str, oa: str, idx: int = 0) -> NGACAssociation:
    return NGACAssociation(
        account_id           = ACCOUNT_ID,
        association_id      = f"as-{idx}",
        user_attribute_id   = ua,
        object_attribute_id = oa,
        operations          = ["read"],
    )


# ── Nodes: create ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_node_returns_id(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.create_node(_node("n-u1", NodeType.USER))
    assert result.is_ok
    assert result.unwrap() == "n-u1"


@pytest.mark.asyncio
async def test_create_duplicate_node_returns_err(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-dup", NodeType.USER))
    result = await ngac_repo.create_node(_node("n-dup", NodeType.USER))
    assert result.is_err


@pytest.mark.asyncio
async def test_get_node_returns_correct_record(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-ua", NodeType.USER_ATTRIBUTE))
    result = await ngac_repo.find_node(ACCOUNT_ID, "n-ua")
    assert result.is_ok
    node = result.unwrap()
    assert node.is_some
    assert node.unwrap().node_type == NodeType.USER_ATTRIBUTE


@pytest.mark.asyncio
async def test_get_nonexistent_node_returns_none(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.find_node(ACCOUNT_ID, "ghost")
    assert result.is_ok
    assert result.unwrap().is_none


# ── Nodes: list ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_nodes_empty(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.list_nodes(ACCOUNT_ID)
    assert result.is_ok
    assert result.unwrap() == []


@pytest.mark.asyncio
async def test_list_nodes_returns_all(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-u",  NodeType.USER))
    await ngac_repo.create_node(_node("n-ua", NodeType.USER_ATTRIBUTE))
    await ngac_repo.create_node(_node("n-pc", NodeType.POLICY_CLASS))

    result = await ngac_repo.list_nodes(ACCOUNT_ID)
    assert result.is_ok
    assert len(result.unwrap()) == 3


@pytest.mark.asyncio
async def test_list_nodes_with_type_filter(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-u",   NodeType.USER))
    await ngac_repo.create_node(_node("n-ua1", NodeType.USER_ATTRIBUTE))
    await ngac_repo.create_node(_node("n-ua2", NodeType.USER_ATTRIBUTE))
    await ngac_repo.create_node(_node("n-pc",  NodeType.POLICY_CLASS))

    result = await ngac_repo.list_nodes(ACCOUNT_ID, node_type=NodeType.USER_ATTRIBUTE)
    assert result.is_ok
    nodes = result.unwrap()
    assert len(nodes) == 2
    assert all(n.node_type == NodeType.USER_ATTRIBUTE for n in nodes)


# ── Nodes: delete + cascade ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_node_removes_it(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-del", NodeType.USER))
    result = await ngac_repo.delete_node(ACCOUNT_ID, "n-del")
    assert result.is_ok
    found = await ngac_repo.find_node(ACCOUNT_ID, "n-del")
    assert found.is_ok
    assert found.unwrap().is_none


@pytest.mark.asyncio
async def test_delete_nonexistent_node_returns_err(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.delete_node(ACCOUNT_ID, "ghost")
    assert result.is_err


@pytest.mark.asyncio
async def test_delete_node_cascades_assignments(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-u",  NodeType.USER))
    await ngac_repo.create_node(_node("n-ua", NodeType.USER_ATTRIBUTE))
    await ngac_repo.create_assignment(_assignment("n-u", "n-ua"))

    await ngac_repo.delete_node(ACCOUNT_ID, "n-u")

    assignments = (await ngac_repo.list_assignments(ACCOUNT_ID)).unwrap()
    assert not any(a.from_id == "n-u" for a in assignments)


@pytest.mark.asyncio
async def test_delete_node_cascades_associations(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-ua", NodeType.USER_ATTRIBUTE))
    await ngac_repo.create_node(_node("n-oa", NodeType.OBJECT_ATTRIBUTE))
    await ngac_repo.create_association(_association("n-ua", "n-oa"))

    await ngac_repo.delete_node(ACCOUNT_ID, "n-ua")

    associations = (await ngac_repo.list_associations(ACCOUNT_ID)).unwrap()
    assert not any(a.user_attribute_id == "n-ua" for a in associations)


# ── Assignments ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_assignment_returns_id(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.create_assignment(_assignment("n-u", "n-ua"))
    assert result.is_ok


@pytest.mark.asyncio
async def test_create_assignment_idempotent(ngac_repo: MongoNGACRepository):
    a = _assignment("n-u", "n-ua")
    await ngac_repo.create_assignment(a)
    result = await ngac_repo.create_assignment(a)  # duplicate
    assert result.is_ok  # no error; idempotent

    all_assignments = (await ngac_repo.list_assignments(ACCOUNT_ID)).unwrap()
    assert len(all_assignments) == 1


@pytest.mark.asyncio
async def test_remove_assignment(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_assignment(_assignment("n-u", "n-ua"))
    result = await ngac_repo.remove_assignment(ACCOUNT_ID, "n-u", "n-ua")
    assert result.is_ok

    assignments = (await ngac_repo.list_assignments(ACCOUNT_ID)).unwrap()
    assert assignments == []


@pytest.mark.asyncio
async def test_remove_nonexistent_assignment_returns_err(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.remove_assignment(ACCOUNT_ID, "ghost", "ghost2")
    assert result.is_err


@pytest.mark.asyncio
async def test_list_assignments_empty(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.list_assignments(ACCOUNT_ID)
    assert result.is_ok
    assert result.unwrap() == []


# ── Associations ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_association_returns_id(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.create_association(_association("n-ua", "n-oa"))
    assert result.is_ok


@pytest.mark.asyncio
async def test_create_association_upserts_on_duplicate(ngac_repo: MongoNGACRepository):
    base = _association("n-ua", "n-oa", 0)
    await ngac_repo.create_association(base)

    updated = NGACAssociation(
        account_id           = ACCOUNT_ID,
        association_id      = "as-1",
        user_attribute_id   = "n-ua",
        object_attribute_id = "n-oa",
        operations          = ["read", "write"],
    )
    await ngac_repo.create_association(updated)

    all_assocs = (await ngac_repo.list_associations(ACCOUNT_ID)).unwrap()
    assert len(all_assocs) == 1
    assert set(all_assocs[0].operations) == {"read", "write"}


@pytest.mark.asyncio
async def test_remove_association(ngac_repo: MongoNGACRepository):
    assoc = _association("n-ua", "n-oa")
    assoc_id = (await ngac_repo.create_association(assoc)).unwrap()

    # The upsert stores the association_id from the last write; retrieve it
    stored_id = (await ngac_repo.list_associations(ACCOUNT_ID)).unwrap()[0].association_id
    result = await ngac_repo.remove_association(ACCOUNT_ID, stored_id)
    assert result.is_ok

    assert (await ngac_repo.list_associations(ACCOUNT_ID)).unwrap() == []


@pytest.mark.asyncio
async def test_remove_nonexistent_association_returns_err(ngac_repo: MongoNGACRepository):
    result = await ngac_repo.remove_association(ACCOUNT_ID, "ghost-id")
    assert result.is_err


# ── load_graph_data ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_graph_data_returns_all_collections(ngac_repo: MongoNGACRepository):
    await ngac_repo.create_node(_node("n-u",  NodeType.USER))
    await ngac_repo.create_node(_node("n-ua", NodeType.USER_ATTRIBUTE))
    await ngac_repo.create_node(_node("n-o",  NodeType.OBJECT))
    await ngac_repo.create_node(_node("n-oa", NodeType.OBJECT_ATTRIBUTE))
    await ngac_repo.create_node(_node("n-pc", NodeType.POLICY_CLASS))

    await ngac_repo.create_assignment(_assignment("n-u",  "n-ua", 0))
    await ngac_repo.create_assignment(_assignment("n-ua", "n-pc", 1))
    await ngac_repo.create_assignment(_assignment("n-o",  "n-oa", 2))
    await ngac_repo.create_assignment(_assignment("n-oa", "n-pc", 3))
    await ngac_repo.create_association(_association("n-ua", "n-oa"))

    result = await ngac_repo.load_graph_data(ACCOUNT_ID)
    assert result.is_ok

    nodes, assignments, associations = result.unwrap()
    assert len(nodes)        == 5
    assert len(assignments)  == 4
    assert len(associations) == 1
