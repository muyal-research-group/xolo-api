from __future__ import annotations

import hashlib
import json
import secrets

from redis.asyncio import Redis


class PlatformSessionStore:
    prefix = "platform:session:"

    def __init__(self, redis: Redis, max_age: int):
        self.redis = redis
        self.max_age = max_age

    @classmethod
    def _key(cls, token: str) -> str:
        return f"{cls.prefix}{hashlib.sha256(token.encode()).hexdigest()}"

    async def create(self, user_id: str) -> tuple[str, str]:
        token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        await self.redis.setex(
            self._key(token), self.max_age,
            json.dumps({"user_id": user_id, "csrf_token": csrf_token}),
        )
        return token, csrf_token

    async def get(self, token: str) -> dict[str, str] | None:
        raw = await self.redis.get(self._key(token))
        if raw is None:
            return None
        await self.redis.expire(self._key(token), self.max_age)
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            await self.redis.delete(self._key(token))
            return None
        if not isinstance(payload, dict) or not payload.get("user_id") or not payload.get("csrf_token"):
            return None
        return payload

    async def delete(self, token: str) -> None:
        await self.redis.delete(self._key(token))

    async def delete_user_sessions(self, user_id: str) -> None:
        async for key in self.redis.scan_iter(match=f"{self.prefix}*"):
            raw = await self.redis.get(key)
            if raw is None:
                continue
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if payload.get("user_id") == user_id:
                await self.redis.delete(key)
