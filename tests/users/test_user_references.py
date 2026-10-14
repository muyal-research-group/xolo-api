import pytest
from mongomock_motor import AsyncMongoMockClient

from xoloapi.users.application.user_resolution import resolve_user_identifier
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository


def _document(account_id: str, key: str, username: str) -> dict:
    return {
        "account_id": account_id,
        "key": key,
        "username": username,
        "normalized_username": username.casefold(),
        "first_name": username,
        "last_name": "User",
        "email": f"{key}@example.com",
        "hash_password": "unused",
        "profile_photo": "",
    }


@pytest.mark.asyncio
async def test_reference_search_is_ranked_escaped_and_account_scoped():
    collection = AsyncMongoMockClient().db.users
    await collection.insert_many([
        _document("a", "u1", "ann"),
        _document("a", "u2", "anna"),
        _document("a", "u3", "jo-ann"),
        _document("a", "u4", "xann-long"),
        _document("b", "u5", "ann-other-account"),
        _document("a", "u6", "literal.*user"),
    ])
    repository = MongoUsersRepository(collection)

    matches = await repository.search_references("a", "ann", 20)
    assert [(user.username, kind) for user, kind in matches] == [
        ("ann", "exact"), ("anna", "prefix"), ("jo-ann", "word_prefix"),
        ("xann-long", "contains"),
    ]
    escaped = await repository.search_references("a", ".*", 3)
    assert [user.username for user, _ in escaped] == ["literal.*user"]


@pytest.mark.asyncio
async def test_identifier_resolution_prefers_id_over_colliding_username():
    collection = AsyncMongoMockClient().db.users
    await collection.insert_many([
        _document("a", "collision", "alice"),
        _document("a", "other", "collision"),
    ])
    resolved = await resolve_user_identifier(MongoUsersRepository(collection), "a", " collision ")
    assert resolved.is_ok
    assert resolved.unwrap().user_id == "collision"
    assert resolved.unwrap().username == "alice"
