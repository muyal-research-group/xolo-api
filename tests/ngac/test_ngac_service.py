import pytest
from xoloapi.ngac.dto import (
    AssignDTO, AssociateDTO, CheckAccessDTO,
    CreateNodeDTO, RemoveAssignmentDTO,
)
from xoloapi.ngac.enums import NodeType
from xoloapi.ngac.service import NGACService
from tests.ngac.conftest import ACCOUNT_ID


# ── Helpers ────────────────────────────────────────────────────────────────

async def _add(service: NGACService, name: str, node_type: NodeType) -> str:
    result = await service.create_node(ACCOUNT_ID, CreateNodeDTO(name=name, node_type=node_type))
    assert result.is_ok, str(result.unwrap_err())
    return result.unwrap()


async def _assign(service: NGACService, from_id: str, to_id: str):
    result = await service.assign(ACCOUNT_ID, AssignDTO(from_id=from_id, to_id=to_id))
    assert result.is_ok, str(result.unwrap_err())


async def _associate(service: NGACService, ua_id: str, oa_id: str, ops: list[str]):
    result = await service.associate(ACCOUNT_ID, AssociateDTO(
        user_attribute_id   = ua_id,
        object_attribute_id = oa_id,
        operations          = ops,
    ))
    assert result.is_ok, str(result.unwrap_err())


# ── Nodes ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_node_returns_prefixed_id(ngac_service: NGACService):
    result = await ngac_service.create_node(ACCOUNT_ID, CreateNodeDTO(name="Alice", node_type=NodeType.USER))
    assert result.is_ok
    assert result.unwrap().startswith("n-")


@pytest.mark.asyncio
async def test_list_nodes_empty(ngac_service: NGACService):
    result = await ngac_service.list_nodes(ACCOUNT_ID)
    assert result.is_ok
    assert result.unwrap() == []


@pytest.mark.asyncio
async def test_list_nodes_type_filter(ngac_service: NGACService):
    await ngac_service.create_node(ACCOUNT_ID, CreateNodeDTO(name="Alice",      node_type=NodeType.USER))
    await ngac_service.create_node(ACCOUNT_ID, CreateNodeDTO(name="MedStaff",   node_type=NodeType.USER_ATTRIBUTE))
    await ngac_service.create_node(ACCOUNT_ID, CreateNodeDTO(name="MedPolicy",  node_type=NodeType.POLICY_CLASS))

    ua_result = await ngac_service.list_nodes(ACCOUNT_ID, node_type=NodeType.USER_ATTRIBUTE)
    assert ua_result.is_ok
    assert len(ua_result.unwrap()) == 1


@pytest.mark.asyncio
async def test_get_node(ngac_service: NGACService):
    node_id = (await ngac_service.create_node(
        ACCOUNT_ID,
        CreateNodeDTO(name="Bucket", node_type=NodeType.OBJECT)
    )).unwrap()

    result = await ngac_service.get_node(ACCOUNT_ID, node_id)
    assert result.is_ok
    assert result.unwrap()["name"] == "Bucket"


@pytest.mark.asyncio
async def test_delete_node(ngac_service: NGACService):
    node_id = (await ngac_service.create_node(
        ACCOUNT_ID,
        CreateNodeDTO(name="Temp", node_type=NodeType.USER)
    )).unwrap()

    del_result = await ngac_service.delete_node(ACCOUNT_ID, node_id)
    assert del_result.is_ok

    get_result = await ngac_service.get_node(ACCOUNT_ID, node_id)
    assert get_result.is_err


# ── Assignments: valid paths ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_user_to_user_attribute(ngac_service: NGACService):
    u  = await _add(ngac_service, "Bob",      NodeType.USER)
    ua = await _add(ngac_service, "HRClerks", NodeType.USER_ATTRIBUTE)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=u, to_id=ua))
    assert result.is_ok


@pytest.mark.asyncio
async def test_assign_object_to_object_attribute(ngac_service: NGACService):
    o  = await _add(ngac_service, "Doc",     NodeType.OBJECT)
    oa = await _add(ngac_service, "HRFiles", NodeType.OBJECT_ATTRIBUTE)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=o, to_id=oa))
    assert result.is_ok


@pytest.mark.asyncio
async def test_assign_ua_to_policy_class(ngac_service: NGACService):
    ua = await _add(ngac_service, "MedStaff", NodeType.USER_ATTRIBUTE)
    pc = await _add(ngac_service, "MedPolicy", NodeType.POLICY_CLASS)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=ua, to_id=pc))
    assert result.is_ok


@pytest.mark.asyncio
async def test_assign_ua_to_ua_hierarchy(ngac_service: NGACService):
    ua1 = await _add(ngac_service, "Junior", NodeType.USER_ATTRIBUTE)
    ua2 = await _add(ngac_service, "Senior", NodeType.USER_ATTRIBUTE)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=ua1, to_id=ua2))
    assert result.is_ok


@pytest.mark.asyncio
async def test_assign_oa_to_oa_hierarchy(ngac_service: NGACService):
    oa1 = await _add(ngac_service, "PatientChart", NodeType.OBJECT_ATTRIBUTE)
    oa2 = await _add(ngac_service, "PatientRecords", NodeType.OBJECT_ATTRIBUTE)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=oa1, to_id=oa2))
    assert result.is_ok


# ── Assignments: invalid paths ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_user_to_policy_class_is_invalid(ngac_service: NGACService):
    u  = await _add(ngac_service, "Alice", NodeType.USER)
    pc = await _add(ngac_service, "P1",    NodeType.POLICY_CLASS)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=u, to_id=pc))
    assert result.is_err


@pytest.mark.asyncio
async def test_assign_user_to_object_attribute_is_invalid(ngac_service: NGACService):
    u  = await _add(ngac_service, "Alice",   NodeType.USER)
    oa = await _add(ngac_service, "Records", NodeType.OBJECT_ATTRIBUTE)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=u, to_id=oa))
    assert result.is_err


@pytest.mark.asyncio
async def test_assign_policy_class_to_anything_is_invalid(ngac_service: NGACService):
    pc = await _add(ngac_service, "P1", NodeType.POLICY_CLASS)
    ua = await _add(ngac_service, "UA", NodeType.USER_ATTRIBUTE)

    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id=pc, to_id=ua))
    assert result.is_err


@pytest.mark.asyncio
async def test_assign_nonexistent_node_returns_err(ngac_service: NGACService):
    result = await ngac_service.assign(ACCOUNT_ID, AssignDTO(from_id="ghost-a", to_id="ghost-b"))
    assert result.is_err


# ── Associations ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_associate_ua_to_oa(ngac_service: NGACService):
    ua = await _add(ngac_service, "MedStaff",      NodeType.USER_ATTRIBUTE)
    oa = await _add(ngac_service, "PatientRecords", NodeType.OBJECT_ATTRIBUTE)

    result = await ngac_service.associate(ACCOUNT_ID, AssociateDTO(
        user_attribute_id   = ua,
        object_attribute_id = oa,
        operations          = ["read", "write"],
    ))
    assert result.is_ok


@pytest.mark.asyncio
async def test_associate_wrong_ua_type_returns_err(ngac_service: NGACService):
    u  = await _add(ngac_service, "Bob",     NodeType.USER)  # not UA
    oa = await _add(ngac_service, "Records", NodeType.OBJECT_ATTRIBUTE)

    result = await ngac_service.associate(ACCOUNT_ID, AssociateDTO(
        user_attribute_id   = u,
        object_attribute_id = oa,
        operations          = ["read"],
    ))
    assert result.is_err


@pytest.mark.asyncio
async def test_associate_wrong_oa_type_returns_err(ngac_service: NGACService):
    ua = await _add(ngac_service, "Staff", NodeType.USER_ATTRIBUTE)
    o  = await _add(ngac_service, "Doc",   NodeType.OBJECT)  # not OA

    result = await ngac_service.associate(ACCOUNT_ID, AssociateDTO(
        user_attribute_id   = ua,
        object_attribute_id = o,
        operations          = ["read"],
    ))
    assert result.is_err


# ── Access check ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_access_allowed(ngac_service: NGACService):
    u  = await _add(ngac_service, "Dr Smith",       NodeType.USER)
    ua = await _add(ngac_service, "Medical Staff",   NodeType.USER_ATTRIBUTE)
    o  = await _add(ngac_service, "Patient Chart A", NodeType.OBJECT)
    oa = await _add(ngac_service, "Patient Records", NodeType.OBJECT_ATTRIBUTE)
    pc = await _add(ngac_service, "Medical Policy",  NodeType.POLICY_CLASS)

    await _assign(ngac_service, u,  ua)
    await _assign(ngac_service, ua, pc)
    await _assign(ngac_service, o,  oa)
    await _assign(ngac_service, oa, pc)
    await _associate(ngac_service, ua, oa, ["read"])

    result = await ngac_service.check_access(ACCOUNT_ID, CheckAccessDTO(
        user_id=u, object_id=o, operation="read"
    ))
    assert result.is_ok
    decision = result.unwrap()
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_check_access_denied_no_policy_class(ngac_service: NGACService):
    u  = await _add(ngac_service, "User", NodeType.USER)
    ua = await _add(ngac_service, "UA",   NodeType.USER_ATTRIBUTE)
    o  = await _add(ngac_service, "Doc",  NodeType.OBJECT)
    oa = await _add(ngac_service, "OA",   NodeType.OBJECT_ATTRIBUTE)

    # No PC; no assignments to a PC
    await _assign(ngac_service, u, ua)
    await _assign(ngac_service, o, oa)
    await _associate(ngac_service, ua, oa, ["read"])

    result = await ngac_service.check_access(ACCOUNT_ID, CheckAccessDTO(
        user_id=u, object_id=o, operation="read"
    ))
    assert result.is_ok
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_check_access_denied_by_and_rule(ngac_service: NGACService):
    """
    Chart A is under both Medical PC and Emergency PC.
    Dr Smith only qualifies for Medical PC → AND rule denies.
    """
    dr   = await _add(ngac_service, "Dr Smith",      NodeType.USER)
    ua_m = await _add(ngac_service, "Medical Staff",  NodeType.USER_ATTRIBUTE)
    ua_e = await _add(ngac_service, "Emerg Doctors",  NodeType.USER_ATTRIBUTE)
    chart = await _add(ngac_service, "Chart A",       NodeType.OBJECT)
    oa_m = await _add(ngac_service, "Patient Records",NodeType.OBJECT_ATTRIBUTE)
    oa_e = await _add(ngac_service, "Emerg Records",  NodeType.OBJECT_ATTRIBUTE)
    pc_m = await _add(ngac_service, "Medical PC",     NodeType.POLICY_CLASS)
    pc_e = await _add(ngac_service, "Emergency PC",   NodeType.POLICY_CLASS)

    await _assign(ngac_service, dr,    ua_m)
    await _assign(ngac_service, ua_m,  pc_m)
    await _assign(ngac_service, chart, oa_m)
    await _assign(ngac_service, oa_m,  pc_m)
    await _assign(ngac_service, chart, oa_e)
    await _assign(ngac_service, oa_e,  pc_e)
    await _assign(ngac_service, ua_e,  pc_e)

    await _associate(ngac_service, ua_m, oa_m, ["read"])
    await _associate(ngac_service, ua_e, oa_e, ["read"])

    result = await ngac_service.check_access(ACCOUNT_ID, CheckAccessDTO(
        user_id=dr, object_id=chart, operation="read"
    ))
    assert result.is_ok
    decision = result.unwrap()
    assert decision.allowed is False
    assert "emergency" in decision.reason.lower() or "policy class" in decision.reason.lower()


@pytest.mark.asyncio
async def test_check_access_wrong_operation_denied(ngac_service: NGACService):
    u  = await _add(ngac_service, "User", NodeType.USER)
    ua = await _add(ngac_service, "UA",   NodeType.USER_ATTRIBUTE)
    o  = await _add(ngac_service, "Doc",  NodeType.OBJECT)
    oa = await _add(ngac_service, "OA",   NodeType.OBJECT_ATTRIBUTE)
    pc = await _add(ngac_service, "PC",   NodeType.POLICY_CLASS)

    await _assign(ngac_service, u,  ua)
    await _assign(ngac_service, ua, pc)
    await _assign(ngac_service, o,  oa)
    await _assign(ngac_service, oa, pc)
    await _associate(ngac_service, ua, oa, ["read"])  # only read

    result = await ngac_service.check_access(ACCOUNT_ID, CheckAccessDTO(
        user_id=u, object_id=o, operation="write"
    ))
    assert result.is_ok
    assert result.unwrap().allowed is False


@pytest.mark.asyncio
async def test_remove_assignment_breaks_access(ngac_service: NGACService):
    u  = await _add(ngac_service, "User", NodeType.USER)
    ua = await _add(ngac_service, "UA",   NodeType.USER_ATTRIBUTE)
    o  = await _add(ngac_service, "Doc",  NodeType.OBJECT)
    oa = await _add(ngac_service, "OA",   NodeType.OBJECT_ATTRIBUTE)
    pc = await _add(ngac_service, "PC",   NodeType.POLICY_CLASS)

    await _assign(ngac_service, u,  ua)
    await _assign(ngac_service, ua, pc)
    await _assign(ngac_service, o,  oa)
    await _assign(ngac_service, oa, pc)
    await _associate(ngac_service, ua, oa, ["read"])

    # Confirm access
    before = (await ngac_service.check_access(ACCOUNT_ID, CheckAccessDTO(user_id=u, object_id=o, operation="read"))).unwrap()
    assert before.allowed is True

    # Remove user assignment → break the path
    await ngac_service.remove_assignment(ACCOUNT_ID, RemoveAssignmentDTO(from_id=u, to_id=ua))

    after = (await ngac_service.check_access(ACCOUNT_ID, CheckAccessDTO(user_id=u, object_id=o, operation="read"))).unwrap()
    assert after.allowed is False
