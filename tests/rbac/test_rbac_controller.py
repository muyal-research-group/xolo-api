import pytest

from tests.rbac.conftest import ACCOUNT_ID


def _path(path: str, account_id: str = ACCOUNT_ID) -> str:
    return f"/api/v4/accounts/{account_id}/rbac{path}"


@pytest.mark.asyncio
async def test_create_and_list_roles(rbac_client):
    create = await rbac_client.post(_path("/roles"), json={
        "name": "editor",
        "description": "Can edit",
        "permissions": ["article:write"],
    })
    assert create.status_code == 201

    listed = await rbac_client.get(_path("/roles"))
    assert listed.status_code == 200
    assert [role["name"] for role in listed.json()] == ["editor"]


@pytest.mark.asyncio
async def test_role_can_be_edited_linked_to_parent_and_deleted(rbac_client):
    parent = await rbac_client.post(_path("/roles"), json={
        "name": "parent",
        "permissions": ["report:read"],
    })
    child = await rbac_client.post(_path("/roles"), json={
        "name": "child",
        "description": "temporary",
        "permissions": [],
    })
    assert parent.status_code == child.status_code == 201
    parent_id = parent.json()["role_id"]
    child_id = child.json()["role_id"]

    updated = await rbac_client.patch(_path(f"/roles/{child_id}"), json={
        "name": "child-edited",
        "description": None,
    })
    assert updated.status_code == 200
    assert updated.json()["name"] == "child-edited"
    assert updated.json()["description"] is None

    permission = await rbac_client.post(
        _path(f"/roles/{child_id}/permissions"), json={"permission": "report:write"}
    )
    parent_link = await rbac_client.post(
        _path(f"/roles/{child_id}/parents"), json={"parent_role_id": parent_id}
    )
    assert permission.status_code == parent_link.status_code == 200
    assert permission.json()["permissions"] == ["report:write"]
    assert parent_link.json()["parent_role_ids"] == [parent_id]

    removed_parent = await rbac_client.request(
        "DELETE", _path(f"/roles/{child_id}/parents"), json={"parent_role_id": parent_id}
    )
    removed_permission = await rbac_client.request(
        "DELETE", _path(f"/roles/{child_id}/permissions"), json={"permission": "report:write"}
    )
    assert removed_parent.status_code == removed_permission.status_code == 200
    assert removed_parent.json()["parent_role_ids"] == []
    assert removed_permission.json()["permissions"] == []

    deleted = await rbac_client.delete(_path(f"/roles/{child_id}"))
    assert deleted.status_code == 204
    missing = await rbac_client.get(_path(f"/roles/{child_id}"))
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_account_mismatch_returns_403(rbac_client):
    res = await rbac_client.get(_path("/roles", account_id="acc-other"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_role_names_are_isolated_by_account(rbac_service):
    first = await rbac_service.create_role("acc-one", name="editor", permissions=["article:write"])
    second = await rbac_service.create_role("acc-two", name="editor", permissions=["article:read"])

    assert first.is_ok
    assert second.is_ok

    first_roles = await rbac_service.list_roles("acc-one")
    second_roles = await rbac_service.list_roles("acc-two")

    assert first_roles.is_ok and [role.name for role in first_roles.unwrap()] == ["editor"]
    assert second_roles.is_ok and [role.name for role in second_roles.unwrap()] == ["editor"]
    assert first_roles.unwrap()[0].permissions == ["article:write"]
    assert second_roles.unwrap()[0].permissions == ["article:read"]


@pytest.mark.asyncio
async def test_assignments_and_checks_are_account_scoped(rbac_service):
    role = (await rbac_service.create_role("acc-one", name="viewer", permissions=["report:read"])).unwrap()

    assign = await rbac_service.assign_role("acc-one", subject_id="user-1", role_id=role.role_id)
    assert assign.is_ok

    allowed = await rbac_service.check("acc-one", subject_id="user-1", required_permission="report:read")
    denied = await rbac_service.check("acc-two", subject_id="user-1", required_permission="report:read")

    assert allowed.is_ok and allowed.unwrap() is True
    assert denied.is_ok and denied.unwrap() is False
