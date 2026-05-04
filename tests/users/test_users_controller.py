import pytest

import xoloapi.users.dto as UDTO
from tests.users.conftest import API_KEY_ACCOUNT_ID

ACCOUNT_ID = API_KEY_ACCOUNT_ID
OTHER_ACCOUNT_ID = "acc-other"


@pytest.mark.asyncio
async def test_users_controller_full_flow(users_client, users_mailer):
    scope_res = await users_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    assert scope_res.status_code == 200

    signup_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/signup",
        json={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "password": "password123",
            "profile_photo": "",
            "scope": "ops",
            "expiration": "15m",
        },
    )
    assert signup_res.status_code == 201
    assert len(users_mailer.welcome_messages) == 1

    auth_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert auth_res.status_code == 200
    auth_body = auth_res.json()
    headers = {
        "Authorization": f"Bearer {auth_body['access_token']}",
        "Temporal-Secret-Key": auth_body["temporal_secret"],
    }

    verify_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/verify",
        json={
            "access_token": auth_body["access_token"],
            "username": "alice",
            "secret": auth_body["temporal_secret"],
        },
    )
    assert verify_res.status_code == 204

    me_res = await users_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/users", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "alice"

    update_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/password-recovery",
        json={"identifier": "alice"},
    )
    assert update_res.status_code == 204
    assert len(users_mailer.password_reset_messages) == 1

    reauth_fail_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "new-password",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert reauth_fail_res.status_code != 200

    reauth_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": True,
        },
    )
    assert reauth_res.status_code == 200
    new_auth = reauth_res.json()
    auth_headers = {
        "Authorization": f"Bearer {new_auth['access_token']}",
        "Temporal-Secret-Key": new_auth["temporal_secret"],
    }

    disable_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/alice/disable",
        json={"username": "alice"},
        headers=auth_headers,
    )
    assert disable_res.status_code == 204

    enable_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/alice/enable",
        json={"username": "alice"},
        headers=auth_headers,
    )
    assert enable_res.status_code == 204

    logout_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/logout",
        json={"username": "alice", "access_token": new_auth["access_token"]},
        headers=auth_headers,
    )
    assert logout_res.status_code == 204


@pytest.mark.asyncio
async def test_users_controller_password_reset_confirm(users_client, users_mailer):
    await users_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    signup_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/signup",
        json={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "password": "password123",
            "profile_photo": "",
            "scope": "ops",
            "expiration": "15m",
        },
    )
    assert signup_res.status_code == 201

    request_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/password-recovery",
        json=UDTO.PasswordRecoveryRequestDTO(identifier="alice").model_dump(),
    )
    assert request_res.status_code == 204
    assert len(users_mailer.password_reset_messages) == 1

    confirm_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/password-recovery/confirm",
        json=UDTO.PasswordRecoveryConfirmDTO(
            token=users_mailer.password_reset_messages[0]["reset_token"],
            password="new-password",
        ).model_dump(),
    )
    assert confirm_res.status_code == 204

    auth_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "new-password",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert auth_res.status_code == 200


@pytest.mark.asyncio
async def test_users_controller_list_and_delete(users_client):
    await users_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    signup_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/signup",
        json={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "password": "password123",
            "profile_photo": "",
            "scope": "ops",
            "expiration": "15m",
        },
    )
    assert signup_res.status_code == 201

    list_res = await users_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/users/all")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    other_list_res = await users_client.get(f"/api/v4/accounts/{OTHER_ACCOUNT_ID}/users/all")
    assert other_list_res.status_code == 200
    assert other_list_res.json() == []

    delete_res = await users_client.request("DELETE", f"/api/v4/accounts/{ACCOUNT_ID}/users/alice")
    assert delete_res.status_code == 204

    list_res = await users_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/users/all")
    assert list_res.status_code == 200
    assert list_res.json() == []


@pytest.mark.asyncio
async def test_users_controller_admin_can_block_and_unblock_user(users_client):
    await users_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/scopes", json={"name": "ops"})
    signup_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/signup",
        json={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "password": "password123",
            "profile_photo": "",
            "scope": "ops",
            "expiration": "15m",
        },
    )
    assert signup_res.status_code == 201

    auth_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert auth_res.status_code == 200
    auth_body = auth_res.json()
    headers = {
        "Authorization": f"Bearer {auth_body['access_token']}",
        "Temporal-Secret-Key": auth_body["temporal_secret"],
    }

    block_res = await users_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/users/alice/block")
    assert block_res.status_code == 204

    me_res = await users_client.get(f"/api/v4/accounts/{ACCOUNT_ID}/users", headers=headers)
    assert me_res.status_code != 200

    blocked_auth_res = await users_client.post(
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

    unblock_res = await users_client.post(f"/api/v4/accounts/{ACCOUNT_ID}/users/alice/unblock")
    assert unblock_res.status_code == 204

    reauth_res = await users_client.post(
        f"/api/v4/accounts/{ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert reauth_res.status_code == 200


@pytest.mark.asyncio
async def test_users_controller_auth_requires_matching_account_api_key(users_client):
    response = await users_client.post(
        f"/api/v4/accounts/{OTHER_ACCOUNT_ID}/users/auth",
        json={
            "username": "alice",
            "password": "password123",
            "scope": "ops",
            "expiration": "15m",
            "renew_token": False,
        },
    )
    assert response.status_code == 403
    assert "API key does not belong to the requested account" in str(response.json()["detail"])
