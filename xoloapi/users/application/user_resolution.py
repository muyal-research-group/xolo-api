from __future__ import annotations

from dataclasses import dataclass

from option import Err, Ok, Result

from xoloapi.errors.base import NotFoundError, ValidationError, XoloException


@dataclass(frozen=True)
class ResolvedUser:
    user_id: str
    username: str


async def resolve_user_identifier(repository, account_id: str, identifier: str) -> Result[ResolvedUser, XoloException]:
    """Resolve an account user by canonical ID first, then exact username."""
    value = (identifier or "").strip()
    if not value:
        return Err(ValidationError("user_identifier is required"))

    by_id = await repository.find_by_id(value, account_id=account_id)
    if by_id.is_some:
        user = by_id.unwrap()
        return Ok(ResolvedUser(user_id=user.key, username=user.username))

    by_username = await repository.find_by_username(account_id, value)
    if by_username.is_some:
        user = by_username.unwrap()
        return Ok(ResolvedUser(user_id=user.key, username=user.username))
    return Err(NotFoundError("User", value))
