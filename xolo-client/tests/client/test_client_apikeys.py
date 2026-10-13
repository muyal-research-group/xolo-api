from xolo.client.client import XoloClient
from xolo.client import models as M


def test_api_key_methods_return_expected_dtos(
    admin_client: XoloClient,
    rand_name,
    unwrap_ok,
    unwrap_ok_list,
):
    created = unwrap_ok(
        admin_client.create_api_key(
            name=rand_name("api-key"),
            scopes=["acl", "rbac"],
            admin_token=admin_client.admin_token,
        ),
        M.CreatedAPIKeyResponseDTO,
    )
    assert created.key_id
    assert created.key
    assert created.key_prefix
    assert {scope.value for scope in created.scopes} == {"acl", "rbac"}

    listed = unwrap_ok_list(
        admin_client.list_api_keys(admin_token=admin_client.admin_token),
        M.APIKeyMetadataDTO,
    )
    listed_key = next(item for item in listed if item.key_id == created.key_id)
    assert listed_key.name == created.name
    assert {scope.value for scope in listed_key.scopes} == {"acl", "rbac"}

    fetched = unwrap_ok(
        admin_client.get_api_key(
            key_id=created.key_id,
            admin_token=admin_client.admin_token,
        ),
        M.APIKeyMetadataDTO,
    )
    assert fetched.key_id == created.key_id
    assert fetched.name == created.name
    assert fetched.key_prefix == created.key_prefix

    rotated = unwrap_ok(
        admin_client.rotate_api_key(
            key_id=created.key_id,
            admin_token=admin_client.admin_token,
        ),
        M.RotatedAPIKeyResponseDTO,
    )
    assert rotated.key_id == created.key_id
    assert rotated.key
    assert rotated.key_prefix

    revoked = unwrap_ok(
        admin_client.revoke_api_key(
            key_id=created.key_id,
            admin_token=admin_client.admin_token,
        ),
        M.RevokedAPIKeyResponseDTO,
    )
    assert revoked.ok is True
    assert revoked.key_id == created.key_id
