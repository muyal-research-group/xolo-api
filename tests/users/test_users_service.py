import pytest

import commonx.dto.xolo as DTO
import xoloapi.users.dto as UDTO

ACCOUNT_ID = "acc-test"


@pytest.mark.asyncio
async def test_users_service_end_to_end(users_service, users_mailer):
    scope_result = await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    assert scope_result.is_ok

    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok
    assert len(users_mailer.welcome_messages) == 1
    assert users_mailer.welcome_messages[0]["recipient_email"] == "alice@example.com"

    auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert auth.is_ok

    auth_data = auth.unwrap()
    verified = await users_service.verify(
        ACCOUNT_ID,
        DTO.VerifyDTO(
            access_token=auth_data.access_token,
            username="alice",
            secret=auth_data.temporal_secret,
        )
    )
    assert verified.is_ok

    disabled = await users_service.disable_user(ACCOUNT_ID, DTO.EnableOrDisableUserDTO(username="alice"))
    assert disabled.is_ok
    enabled = await users_service.enable_user(ACCOUNT_ID, DTO.EnableOrDisableUserDTO(username="alice"))
    assert enabled.is_ok

    updated = await users_service.update_password(
        ACCOUNT_ID,
        DTO.UpdateUserPasswordDTO(username="alice", password="new-password")
    )
    assert updated.is_ok

    logout = await users_service.logout(ACCOUNT_ID, DTO.LogoutDTO(username="alice", access_token=auth_data.access_token))
    assert logout.is_ok


@pytest.mark.asyncio
async def test_users_service_password_reset_request_and_confirm(users_service, users_mailer):
    scope_result = await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    assert scope_result.is_ok

    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok

    request_result = await users_service.request_password_recovery(
        ACCOUNT_ID,
        UDTO.PasswordRecoveryRequestDTO(identifier="alice")
    )
    assert request_result.is_ok
    assert len(users_mailer.password_reset_messages) == 1

    confirm_result = await users_service.confirm_password_recovery(
        ACCOUNT_ID,
        UDTO.PasswordRecoveryConfirmDTO(
            token=users_mailer.password_reset_messages[0]["reset_token"],
            password="new-password",
        )
    )
    assert confirm_result.is_ok

    auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="new-password",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert auth.is_ok


@pytest.mark.asyncio
async def test_users_service_password_reset_request_is_neutral_for_unknown_user(users_service, users_mailer):
    request_result = await users_service.request_password_recovery(
        ACCOUNT_ID,
        UDTO.PasswordRecoveryRequestDTO(identifier="missing-user")
    )
    assert request_result.is_ok
    assert users_mailer.password_reset_messages == []


@pytest.mark.asyncio
async def test_users_service_signup_survives_welcome_mail_failure(users_service, users_mailer):
    users_mailer.fail_welcome = True
    scope_result = await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    assert scope_result.is_ok

    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok
    assert len(users_mailer.welcome_messages) == 1


@pytest.mark.asyncio
async def test_users_service_delete_user_cascades_related_records(users_service):
    await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok

    deleted = await users_service.delete_user(ACCOUNT_ID, "alice")
    assert deleted.is_ok

    users = await users_service.list_users(ACCOUNT_ID)
    assert users.is_ok
    assert users.unwrap() == []


@pytest.mark.asyncio
async def test_users_service_block_user_invalidates_active_session(users_service):
    await users_service.scopes_repository.create(ACCOUNT_ID, DTO.CreateScopeDTO(name="ops"))
    signup = await users_service.signup(
        ACCOUNT_ID,
        DTO.SignUpDTO(
            username="alice",
            first_name="Alice",
            last_name="Doe",
            email="alice@example.com",
            password="password123",
            profile_photo="",
            scope="ops",
            expiration="15m",
        )
    )
    assert signup.is_ok

    auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert auth.is_ok

    blocked = await users_service.block_user(ACCOUNT_ID, "alice")
    assert blocked.is_ok

    verify = await users_service.verify(
        ACCOUNT_ID,
        DTO.VerifyDTO(
            access_token=auth.unwrap().access_token,
            username="alice",
            secret=auth.unwrap().temporal_secret,
        )
    )
    assert verify.is_err

    blocked_auth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert blocked_auth.is_err

    unblocked = await users_service.unblock_user(ACCOUNT_ID, "alice")
    assert unblocked.is_ok

    reauth = await users_service.auth(
        ACCOUNT_ID,
        DTO.AuthDTO(
            username="alice",
            password="password123",
            scope="ops",
            expiration="15m",
            renew_token=False,
        )
    )
    assert reauth.is_ok
