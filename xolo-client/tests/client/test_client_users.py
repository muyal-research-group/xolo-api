from xolo.client.client import XoloClient
from xolo.client import models as M


def test_signup_auth_verify_and_get_current_user_return_expected_dtos(
    protected_client: XoloClient,
    rand_name,
    unwrap_ok,
):
    scope = rand_name("scope")
    created_scope = unwrap_ok(
        protected_client.create_scope(scope=scope, secret=protected_client.secret),
        M.CreatedScopeResponseDTO,
    )
    assert created_scope.name == scope.upper()

    username = rand_name("signup-user")
    email = f"{username}@x.com"
    password = "secret"

    signed_up = unwrap_ok(
        protected_client.signup(
            username=username,
            first_name="Signup",
            last_name="User",
            email=email,
            password=password,
            scope=scope,
            expiration="1d",
        ),
        M.CreatedUserResponseDTO,
    )
    assert signed_up.key

    auth = unwrap_ok(
        protected_client.auth(
            username=username,
            password=password,
            scope=scope,
            expiration="1d",
            renew_token=True,
        ),
        M.AuthenticatedDTO,
    )
    assert auth.username == username
    assert auth.email == email
    assert auth.access_token
    assert auth.temporal_secret

    verified = unwrap_ok(
        protected_client.verify_token(
            access_token=auth.access_token,
            username=username,
            secret=auth.temporal_secret,
        ),
        M.VerifyTokenResponseDTO,
    )
    assert verified.ok is True
    assert verified.username == username
    assert verified.access_token == auth.access_token

    current_user = unwrap_ok(
        protected_client.get_current_user(
            token=auth.access_token,
            temporal_secret=auth.temporal_secret,
        ),
        M.UserDTO,
    )
    assert current_user.key == signed_up.key
    assert current_user.username == username
    assert current_user.email == email


def test_create_user_auth_and_logout_return_expected_dtos(
    protected_client: XoloClient,
    rand_name,
    unwrap_ok,
):
    scope = rand_name("scope")
    created_scope = unwrap_ok(
        protected_client.create_scope(scope=scope, secret=protected_client.secret),
        M.CreatedScopeResponseDTO,
    )
    assert created_scope.name == scope.upper()

    username = rand_name("created-user")
    password = "secret"

    created_user = unwrap_ok(
        protected_client.create_user(
            username=username,
            first_name="Created",
            last_name="User",
            email=f"{username}@x.com",
            password=password,
            profile_photo="",
        ),
        M.CreatedUserResponseDTO,
    )
    assert created_user.key

    assigned_scope = unwrap_ok(
        protected_client.assign_scope(
            username=username,
            scope=scope,
            secret=protected_client.secret,
        ),
        M.AssignedScopeResponseDTO,
    )
    assert assigned_scope.ok is True
    assert assigned_scope.username == username
    assert assigned_scope.name == scope.upper()

    created_license = unwrap_ok(
        protected_client.create_license(
            username=username,
            scope=scope,
            secret=protected_client.secret,
            expires_in="1d",
        ),
        M.AssignLicenseResponseDTO,
    )
    assert created_license.ok is True
    assert created_license.expires_at

    auth = unwrap_ok(
        protected_client.auth(
            username=username,
            password=password,
            scope=scope,
            expiration="1d",
            renew_token=True,
        ),
        M.AuthenticatedDTO,
    )
    assert auth.user_id == created_user.key
    assert auth.username == username

    logged_out = unwrap_ok(
        protected_client.logout(
            username=username,
            access_token=auth.access_token,
            token=auth.access_token,
            temporal_secret=auth.temporal_secret,
        ),
        M.OperationResultDTO,
    )
    assert logged_out.ok is True


def test_disable_and_enable_user_return_expected_dtos(
    protected_client: XoloClient,
    make_signed_up_user,
    unwrap_ok,
):
    user = make_signed_up_user()

    disabled = unwrap_ok(
        protected_client.disable_user(
            username=user.username,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.UserDisabledResponseDTO,
    )
    assert disabled.ok is True
    assert disabled.username == user.username

    enabled = unwrap_ok(
        protected_client.enable_user(
            username=user.username,
            token=user.auth.access_token,
            temporal_secret=user.auth.temporal_secret,
        ),
        M.UserEnabledResponseDTO,
    )
    assert enabled.ok is True
    assert enabled.username == user.username
