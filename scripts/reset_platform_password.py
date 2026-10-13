#!/usr/bin/env python3
"""Reset a platform user's password as a one-shot recovery operation."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorClient
from option import Err, Ok, Result
from redis.asyncio import Redis

import xoloapi.config as Cfg
from xoloapi.db.constants import CollectionNames
from xoloapi.errors.base import NotFoundError, ValidationError, XoloException
from xoloapi.platform_users.application import PlatformUserService
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.repositories import IPlatformUserRepository
from xoloapi.platform_users.infrastructure.mongo_repository import MongoPlatformUserRepository
from xoloapi.platform_users.infrastructure.session_store import PlatformSessionStore


USERNAME_ENV = "XOLO_PLATFORM_RESET_USERNAME"
PASSWORD_ENV = "XOLO_PLATFORM_RESET_PASSWORD"


class UserSessionStore(Protocol):
    async def delete_user_sessions(self, user_id: str) -> None: ...


async def reset_platform_password(
    repository: IPlatformUserRepository,
    sessions: UserSessionStore,
    username: str,
    password: str,
) -> Result[PlatformUser, XoloException]:
    """Reset one existing user's password and invalidate all their sessions."""
    username = username.strip().lower()
    if not username:
        return Err(ValidationError("Reset username is required", USERNAME_ENV))

    found = await repository.find_by_username(username)
    if found.is_err:
        return Err(found.unwrap_err())
    maybe_user = found.unwrap()
    if maybe_user.is_none:
        return Err(NotFoundError("Platform user", username))

    service = PlatformUserService(repository)
    reset = await service.reset_password(maybe_user.unwrap().user_id, password)
    if reset.is_err:
        return Err(reset.unwrap_err())

    user = reset.unwrap()
    await sessions.delete_user_sessions(user.user_id)
    return Ok(user)


async def run() -> int:
    username = os.environ.get(USERNAME_ENV, Cfg.XOLO_PLATFORM_BOOTSTRAP_USERNAME)
    password = os.environ.get(PASSWORD_ENV, "")
    if not password:
        print(f"Error: {PASSWORD_ENV} is required.", file=sys.stderr)
        return 2

    mongo = AsyncIOMotorClient(Cfg.XOLO_MONGODB_URI)
    redis = Redis.from_url(Cfg.XOLO_CACHE_REDIS_URI, decode_responses=True)
    try:
        await mongo.admin.command("ping")
        await redis.ping()
        collection = mongo[Cfg.XOLO_MONGODB_DATABASE_NAME][
            CollectionNames.PLATFORM_USERS_COLLECTION_NAME
        ]
        repository = MongoPlatformUserRepository(collection)
        sessions = PlatformSessionStore(redis, Cfg.XOLO_PLATFORM_SESSION_MAX_AGE)
        result = await reset_platform_password(repository, sessions, username, password)
        if result.is_err:
            print(f"Error: {result.unwrap_err()}", file=sys.stderr)
            return 1

        user = result.unwrap()
        print(
            f"Password reset for platform user '{user.username}'. "
            "Existing sessions were invalidated; a password change is required after sign-in."
        )
        return 0
    except Exception as exc:
        print(f"Error: password reset failed: {exc}", file=sys.stderr)
        return 1
    finally:
        mongo.close()
        await redis.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
