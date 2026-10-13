from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope


def _key(*scopes: APIKeyScope) -> APIKey:
    return APIKey(
        key_id="key-1",
        key_hash="hash",
        key_prefix="XOLO_test",
        account_id="acc-1",
        name="test",
        scopes=list(scopes),
        created_by="tests",
    )


def test_service_scope_must_be_explicit_even_when_key_has_all_scope():
    assert _key(APIKeyScope.ALL).allows("acl") is True
    assert _key(APIKeyScope.ALL).allows("service") is False
    assert _key(APIKeyScope.ALL, APIKeyScope.SERVICE).allows("service") is True

