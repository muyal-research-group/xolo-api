import re

import pytest

ACCOUNT_ID = "acc-ui"


async def login_admin(client):
    response = await client.post(
        "/admin/login",
        data={"admin_token": "admin-token"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "http://test/admin"


async def create_account(client, account_id: str = ACCOUNT_ID, name: str = "UI Account"):
    response = await client.post(
        "/admin/accounts",
        data={"account_id": account_id, "name": name},
    )
    assert response.status_code == 200
    assert f"Account &#39;{account_id}&#39; created." in response.text
    return response


@pytest.mark.asyncio
async def test_admin_login_gate_and_logout(admin_ui_client):
    redirect_res = await admin_ui_client.get("/admin", follow_redirects=False)
    assert redirect_res.status_code == 303
    assert redirect_res.headers["location"] == "http://test/admin/login"

    login_page = await admin_ui_client.get("/admin/login")
    assert login_page.status_code == 200
    assert "Admin login" in login_page.text

    invalid_login = await admin_ui_client.post("/admin/login", data={"admin_token": "wrong-token"})
    assert invalid_login.status_code == 401
    assert "Invalid admin token" in invalid_login.text

    await login_admin(admin_ui_client)

    dashboard = await admin_ui_client.get("/admin?account_id=acc-ui")
    assert dashboard.status_code == 200
    assert "Admin panel" in dashboard.text
    assert "Current account:" in dashboard.text
    assert "Accounts" in dashboard.text

    logout_res = await admin_ui_client.post("/admin/logout", follow_redirects=False)
    assert logout_res.status_code == 303
    assert logout_res.headers["location"] == "http://test/admin/login"

    after_logout = await admin_ui_client.get("/admin", follow_redirects=False)
    assert after_logout.status_code == 303
    assert after_logout.headers["location"] == "http://test/admin/login"


@pytest.mark.asyncio
async def test_admin_can_create_list_and_delete_accounts(admin_ui_client):
    await login_admin(admin_ui_client)

    page_res = await admin_ui_client.get("/admin/accounts")
    assert page_res.status_code == 200
    assert "Existing accounts" in page_res.text

    create_res = await create_account(admin_ui_client, account_id="alpha-org", name="Alpha Org")
    assert "Alpha Org" in create_res.text
    assert "Open account" in create_res.text

    delete_res = await admin_ui_client.post(
        "/admin/accounts/delete",
        data={"account_id": "alpha-org"},
    )
    assert delete_res.status_code == 200
    assert "Account &#39;alpha-org&#39; deleted." in delete_res.text


@pytest.mark.asyncio
async def test_admin_shows_error_for_unknown_account_selection(admin_ui_client):
    await login_admin(admin_ui_client)

    page_res = await admin_ui_client.get("/admin/users?account_id=missing-account")
    assert page_res.status_code == 200
    assert "Account not found" in page_res.text
    assert "missing-account" in page_res.text


@pytest.mark.asyncio
async def test_admin_can_create_api_key_and_raw_key_is_one_time(admin_ui_client):
    await login_admin(admin_ui_client)

    create_res = await admin_ui_client.post(
        "/admin/apikeys",
        data={"account_id": ACCOUNT_ID, "name": "ops-admin", "scopes": ["users", "licenses"]},
    )
    assert create_res.status_code == 200
    assert "Store this API key now" in create_res.text
    assert ACCOUNT_ID in create_res.text
    assert "ops-admin" in create_res.text

    raw_key_match = re.search(r"XOLO_[A-Z0-9_-]+", create_res.text)
    assert raw_key_match is not None
    raw_key = raw_key_match.group(0)

    list_res = await admin_ui_client.get(f"/admin/apikeys?account_id={ACCOUNT_ID}")
    assert list_res.status_code == 200
    assert "Showing keys for account" in list_res.text
    assert "ops-admin" in list_res.text
    assert raw_key not in list_res.text
    assert "Store this API key now" not in list_res.text

    key_id_match = re.search(r'name="key_id" value="([^"]+)"', list_res.text)
    assert key_id_match is not None
    delete_res = await admin_ui_client.post(
        "/admin/apikeys/delete",
        data={"account_id": ACCOUNT_ID, "key_id": key_id_match.group(1)},
    )
    assert delete_res.status_code == 200
    assert "deleted" in delete_res.text
    assert "ops-admin" not in delete_res.text


@pytest.mark.asyncio
async def test_admin_can_manage_scopes_users_and_licenses(admin_ui_client):
    await login_admin(admin_ui_client)

    create_scope_res = await admin_ui_client.post(
        "/admin/scopes",
        data={"account_id": ACCOUNT_ID, "name": "ops"},
    )
    assert create_scope_res.status_code == 200
    assert "Scope" in create_scope_res.text
    assert ACCOUNT_ID in create_scope_res.text
    assert "OPS" in create_scope_res.text
    assert "created" in create_scope_res.text

    create_user_res = await admin_ui_client.post(
        "/admin/users",
        data={
            "account_id": ACCOUNT_ID,
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "password": "password123",
        },
    )
    assert create_user_res.status_code == 200
    assert "User &#39;alice&#39; created." in create_user_res.text
    assert ACCOUNT_ID in create_user_res.text

    assign_scope_res = await admin_ui_client.post(
        "/admin/scopes/assign",
        data={"account_id": ACCOUNT_ID, "name": "ops", "username": "alice"},
    )
    assert assign_scope_res.status_code == 200
    assert "assigned" in assign_scope_res.text
    assert "OPS" in assign_scope_res.text
    assert "alice" in assign_scope_res.text
    assert "Existing scope assignments" in assign_scope_res.text

    assign_license_res = await admin_ui_client.post(
        "/admin/licenses",
        data={
            "account_id": ACCOUNT_ID,
            "username": "alice",
            "scope": "ops",
            "expires_in": "15m",
            "force": "on",
        },
    )
    assert assign_license_res.status_code == 200
    assert "License assigned" in assign_license_res.text
    assert "OPS" in assign_license_res.text
    assert "alice" in assign_license_res.text
    assert "Existing licenses" in assign_license_res.text

    block_user_res = await admin_ui_client.post(
        "/admin/users/block",
        data={"account_id": ACCOUNT_ID, "username": "alice"},
    )
    assert block_user_res.status_code == 200
    assert "blocked" in block_user_res.text

    blocked_auth_res = await admin_ui_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert blocked_auth_res.status_code != 200

    unblock_user_res = await admin_ui_client.post(
        "/admin/users/unblock",
        data={"account_id": ACCOUNT_ID, "username": "alice"},
    )
    assert unblock_user_res.status_code == 200
    assert "unblocked" in unblock_user_res.text

    blocked_delete_scope_res = await admin_ui_client.post(
        "/admin/scopes/delete",
        data={"account_id": ACCOUNT_ID, "name": "OPS"},
    )
    assert blocked_delete_scope_res.status_code == 200
    assert "cannot be deleted" in blocked_delete_scope_res.text
    assert "Existing scopes" in blocked_delete_scope_res.text

    delete_license_res = await admin_ui_client.post(
        "/admin/licenses/delete",
        data={"account_id": ACCOUNT_ID, "username": "alice", "scope": "OPS"},
    )
    assert delete_license_res.status_code == 200
    assert "License removed" in delete_license_res.text

    unassign_scope_res = await admin_ui_client.post(
        "/admin/scopes/unassign",
        data={"account_id": ACCOUNT_ID, "name": "OPS", "username": "alice"},
    )
    assert unassign_scope_res.status_code == 200
    assert "unassigned" in unassign_scope_res.text

    delete_scope_res = await admin_ui_client.post(
        "/admin/scopes/delete",
        data={"account_id": ACCOUNT_ID, "name": "OPS"},
    )
    assert delete_scope_res.status_code == 200
    assert "deleted" in delete_scope_res.text

    users_page_res = await admin_ui_client.get(f"/admin/users?account_id={ACCOUNT_ID}")
    assert users_page_res.status_code == 200
    assert "Existing users" in users_page_res.text
    assert ACCOUNT_ID in users_page_res.text

    delete_user_res = await admin_ui_client.post(
        "/admin/users/delete",
        data={"account_id": ACCOUNT_ID, "username": "alice"},
    )
    assert delete_user_res.status_code == 200
    assert "User &#39;alice&#39; deleted." in delete_user_res.text

    auth_res = await admin_ui_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert auth_res.status_code != 200


@pytest.mark.asyncio
async def test_admin_can_open_and_use_acl_rbac_abac_and_ngac_pages(admin_ui_client):
    await login_admin(admin_ui_client)

    acl_page = await admin_ui_client.get("/admin/acl")
    assert acl_page.status_code == 200
    assert "ACL" in acl_page.text

    create_acl_group = await admin_ui_client.post(
        "/admin/acl/groups",
        data={"name": "Reviewers", "description": "ACL reviewers", "owner_id": "owner-1"},
    )
    assert create_acl_group.status_code == 200
    assert "Reviewers" in create_acl_group.text

    claim_acl_resource = await admin_ui_client.post(
        "/admin/acl/resources/claim",
        data={"resource_id": "document-123", "owner_id": "owner-1"},
    )
    assert claim_acl_resource.status_code == 200
    assert "document-123" in claim_acl_resource.text

    grant_acl_res = await admin_ui_client.post(
        "/admin/acl/grants",
        data={
            "resource_id": "document-123",
            "principal_id": "alice",
            "principal_type": "USER",
            "permissions": "read,write",
        },
    )
    assert grant_acl_res.status_code == 200
    assert "document-123" in grant_acl_res.text
    assert "alice" in grant_acl_res.text

    rbac_create_res = await admin_ui_client.post(
        "/admin/rbac/roles",
        data={"name": "reviewer", "description": "Can review docs", "permissions": "docs:read"},
    )
    assert rbac_create_res.status_code == 200
    assert "reviewer" in rbac_create_res.text
    role_id_match = re.search(r'value="(role-[A-Za-z0-9_-]+)"', rbac_create_res.text)
    assert role_id_match is not None

    rbac_update_res = await admin_ui_client.post(
        "/admin/rbac/roles/update",
        data={"role_id": role_id_match.group(1), "name": "senior-reviewer", "description": "Can review all docs"},
    )
    assert rbac_update_res.status_code == 200
    assert "senior-reviewer" in rbac_update_res.text

    abac_create_res = await admin_ui_client.post(
        "/admin/abac/policies",
        data={
            "name": "office-read",
            "effect": "ALLOW",
            "subject": "alice",
            "resource": "document-123",
            "location": "office",
            "time_start": "",
            "time_end": "",
            "action": "read",
        },
    )
    assert abac_create_res.status_code == 200
    assert "office-read" in abac_create_res.text
    policy_id_match = re.search(r'value="(ap-[A-Za-z0-9_-]{6,})"', abac_create_res.text)
    assert policy_id_match is not None

    abac_update_res = await admin_ui_client.post(
        "/admin/abac/policies/update",
        data={
            "policy_id": policy_id_match.group(1),
            "name": "office-read-updated",
            "effect": "ALLOW",
            "subject": "alice",
            "resource": "document-123",
            "location": "office",
            "time_start": "",
            "time_end": "",
            "action": "read",
        },
    )
    assert abac_update_res.status_code == 200
    assert "office-read-updated" in abac_update_res.text

    abac_eval_res = await admin_ui_client.post(
        "/admin/abac/evaluate",
        data={
            "subject": "alice",
            "resource": "document-123",
            "location": "office",
            "time": "",
            "action": "read",
        },
    )
    assert abac_eval_res.status_code == 200
    assert "ALLOW" in abac_eval_res.text

    ngac_page = await admin_ui_client.get("/admin/ngac")
    assert ngac_page.status_code == 200
    assert "NGAC" in ngac_page.text
