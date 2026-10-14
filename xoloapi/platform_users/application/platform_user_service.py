from __future__ import annotations

import datetime as dt
import secrets

from nanoid import generate
from option import Err, Ok, Result

from xoloapi.errors.base import (
    AccessDeniedError,
    AlreadyExistsError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    XoloException,
)
from xoloapi.platform_users.domain.aggregates import PlatformUser
from xoloapi.platform_users.domain.repositories import IPlatformUserRepository
from xoloapi.platform_users.domain.value_objects import PlatformPermission, PlatformRole
from xoloapi.security import Security


class PlatformUserService:
    def __init__(self, repository: IPlatformUserRepository):
        self.repository = repository

    async def bootstrap(self, username: str, password: str) -> Result[PlatformUser | None, XoloException]:
        indexes = await self.repository.ensure_indexes()
        if indexes.is_err:
            return Err(indexes.unwrap_err())
        count = await self.repository.count()
        if count.is_err:
            return Err(count.unwrap_err())
        if count.unwrap() > 0:
            return Ok(None)
        username = self._normalize_username(username)
        if len(username) < 3:
            return Err(ValidationError("Username must contain at least 3 characters", "username"))
        if not password:
            return Err(ValidationError(
                "XOLO_PLATFORM_BOOTSTRAP_PASSWORD is required when no platform administrator exists",
                "XOLO_PLATFORM_BOOTSTRAP_PASSWORD",
            ))
        validation = self._validate_password(password)
        if validation is not None:
            return Err(validation)
        now = dt.datetime.now(dt.timezone.utc)
        user = PlatformUser(
            user_id=generate(size=21),
            username=username,
            password_hash=await Security.hash_value(password),
            role=PlatformRole.ADMIN,
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        saved = await self.repository.save(user)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def authenticate(self, username: str, password: str) -> Result[PlatformUser, XoloException]:
        username = self._normalize_username(username)
        if len(username) < 3:
            return Err(UnauthorizedError("Invalid username or password"))
        found = await self.repository.find_by_username(username)
        if found.is_err:
            return Err(found.unwrap_err())
        maybe_user = found.unwrap()
        if maybe_user.is_none:
            return Err(UnauthorizedError("Invalid username or password"))
        user = maybe_user.unwrap()
        if not user.is_active:
            return Err(AccessDeniedError("Platform user is disabled"))
        if not await Security.verify_password(user.password_hash, password):
            return Err(UnauthorizedError("Invalid username or password"))
        user.last_login_at = dt.datetime.now(dt.timezone.utc)
        user.updated_at = user.last_login_at
        saved = await self.repository.save(user)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def get(self, user_id: str) -> Result[PlatformUser, XoloException]:
        found = await self.repository.find_by_id(user_id)
        if found.is_err:
            return Err(found.unwrap_err())
        maybe_user = found.unwrap()
        if maybe_user.is_none:
            return Err(NotFoundError("Platform user", user_id))
        return Ok(maybe_user.unwrap())

    async def list_users(self) -> Result[list[PlatformUser], XoloException]:
        return await self.repository.list_all()

    async def create(
        self,
        username: str,
        password: str,
        role: PlatformRole,
        permissions: set[PlatformPermission],
        allowed_account_ids: set[str],
        *,
        must_change_password: bool = True,
    ) -> Result[PlatformUser, XoloException]:
        username = self._normalize_username(username)
        if len(username) < 3:
            return Err(ValidationError("Username must contain at least 3 characters", "username"))
        validation = self._validate_password(password)
        if validation is not None:
            return Err(validation)
        existing = await self.repository.find_by_username(username)
        if existing.is_err:
            return Err(existing.unwrap_err())
        if existing.unwrap().is_some:
            return Err(AlreadyExistsError("Platform user", username))
        now = dt.datetime.now(dt.timezone.utc)
        user = PlatformUser(
            user_id=generate(size=21),
            username=username,
            password_hash=await Security.hash_value(password),
            role=role,
            permissions=self._permissions_for_role(role, permissions),
            allowed_account_ids=allowed_account_ids,
            must_change_password=must_change_password,
            created_at=now,
            updated_at=now,
        )
        saved = await self.repository.save(user)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def update(
        self,
        user_id: str,
        *,
        role: PlatformRole | None = None,
        permissions: set[PlatformPermission] | None = None,
        allowed_account_ids: set[str] | None = None,
        is_active: bool | None = None,
    ) -> Result[PlatformUser, XoloException]:
        result = await self.get(user_id)
        if result.is_err:
            return Err(result.unwrap_err())
        user = result.unwrap()
        next_role = role if role is not None else user.role
        next_active = is_active if is_active is not None else user.is_active
        if user.role == PlatformRole.ADMIN and user.is_active and (
            next_role != PlatformRole.ADMIN or not next_active
        ):
            guard = await self._ensure_another_admin()
            if guard is not None:
                return Err(guard)
        user.role = next_role
        user.is_active = next_active
        if permissions is not None:
            user.permissions = self._permissions_for_role(next_role, permissions)
        elif next_role == PlatformRole.GUEST:
            user.permissions = self._permissions_for_role(next_role, user.permissions)
        if allowed_account_ids is not None:
            user.allowed_account_ids = allowed_account_ids
        user.updated_at = dt.datetime.now(dt.timezone.utc)
        saved = await self.repository.save(user)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> Result[PlatformUser, XoloException]:
        result = await self.get(user_id)
        if result.is_err:
            return Err(result.unwrap_err())
        user = result.unwrap()
        if not await Security.verify_password(user.password_hash, current_password):
            return Err(UnauthorizedError("Current password is incorrect"))
        validation = self._validate_password(new_password)
        if validation is not None:
            return Err(validation)
        if secrets.compare_digest(current_password, new_password):
            return Err(ValidationError("The new password must be different", "new_password"))
        user.password_hash = await Security.hash_value(new_password)
        user.must_change_password = False
        user.updated_at = dt.datetime.now(dt.timezone.utc)
        saved = await self.repository.save(user)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def reset_password(self, user_id: str, password: str) -> Result[PlatformUser, XoloException]:
        result = await self.get(user_id)
        if result.is_err:
            return Err(result.unwrap_err())
        validation = self._validate_password(password)
        if validation is not None:
            return Err(validation)
        user = result.unwrap()
        user.password_hash = await Security.hash_value(password)
        user.must_change_password = True
        user.updated_at = dt.datetime.now(dt.timezone.utc)
        saved = await self.repository.save(user)
        return Err(saved.unwrap_err()) if saved.is_err else Ok(saved.unwrap())

    async def delete(self, user_id: str) -> Result[bool, XoloException]:
        result = await self.get(user_id)
        if result.is_err:
            return Err(result.unwrap_err())
        user = result.unwrap()
        if user.role == PlatformRole.ADMIN and user.is_active:
            guard = await self._ensure_another_admin()
            if guard is not None:
                return Err(guard)
        deleted = await self.repository.delete(user_id)
        return Err(deleted.unwrap_err()) if deleted.is_err else Ok(deleted.unwrap())

    async def _ensure_another_admin(self) -> XoloException | None:
        count = await self.repository.count_active_admins()
        if count.is_err:
            return count.unwrap_err()
        if count.unwrap() <= 1:
            return ConflictError("The last active platform administrator cannot be removed, disabled, or demoted")
        return None

    @staticmethod
    def _permissions_for_role(role: PlatformRole, permissions: set[PlatformPermission]) -> set[PlatformPermission]:
        if role == PlatformRole.ADMIN:
            return set()
        if role == PlatformRole.GUEST:
            return {permission for permission in permissions if permission.read_only}
        return set(permissions)

    @staticmethod
    def _normalize_username(username: str) -> str:
        return username.strip().lower()

    @staticmethod
    def _validate_password(password: str) -> ValidationError | None:
        if len(password) < 12:
            return ValidationError("Password must contain at least 12 characters", "password")
        return None
