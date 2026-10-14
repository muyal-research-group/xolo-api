from xolo.client.client import XoloClient
from xolo.client import models as M


def test_create_scope_assign_scope_create_license_and_delete_license_return_expected_dtos(
    protected_client: XoloClient,
    rand_name,
    unwrap_ok,
):
    scope = rand_name("scope")
    username = rand_name("licensed-user")

    created_scope = unwrap_ok(
        protected_client.create_scope(scope=scope, secret=protected_client.secret),
        M.CreatedScopeResponseDTO,
    )
    assert created_scope.name == scope.upper()

    created_user = unwrap_ok(
        protected_client.create_user(
            username=username,
            first_name="Licensed",
            last_name="User",
            email=f"{username}@x.com",
            password="secret",
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

    deleted_license = unwrap_ok(
        protected_client.delete_license(
            username=username,
            scope=scope,
            secret=protected_client.secret,
        ),
        M.DeletedLicenseResponseDTO,
    )
    assert deleted_license.ok is True


def test_self_delete_license_returns_expected_dto(
    protected_client: XoloClient,
    rand_name,
    unwrap_ok,
):
    scope = rand_name("scope")
    username = rand_name("self-delete-user")
    password = "secret"

    created_scope = unwrap_ok(
        protected_client.create_scope(scope=scope, secret=protected_client.secret),
        M.CreatedScopeResponseDTO,
    )
    assert created_scope.name == scope.upper()

    created_user = unwrap_ok(
        protected_client.create_user(
            username=username,
            first_name="Self",
            last_name="Delete",
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
    assert auth.username == username

    deleted_license = unwrap_ok(
        protected_client.self_delete_license(
            username=username,
            scope=scope,
            token=auth.access_token,
            secret=auth.temporal_secret,
        ),
        M.DeletedLicenseResponseDTO,
    )
    assert deleted_license.ok is True
