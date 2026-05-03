import hashlib
import hmac
import secrets
import datetime
from nanoid import generate
from option import Ok, Err, Result, Option
from xolo.log import Log
from xoloapi.apikeys.domain.aggregates import APIKey
from xoloapi.apikeys.domain.value_objects import APIKeyScope
from xoloapi.apikeys.domain.repositories import IAPIKeyRepository
from xoloapi.errors.base import (
    XoloException,
    NotFoundError,
    UnauthorizedError,
    AccessDeniedError,
    InternalError,
)
import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class APIKeyService:

    def __init__(self, repository: IAPIKeyRepository):
        self.repository    = repository
        self.API_KEY_PREFIX = "XOLO"

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _generate_raw_key(self, primary_scope: str) -> str:
        return f"{self.API_KEY_PREFIX}_{primary_scope}_{secrets.token_urlsafe(32)}".upper()

    @staticmethod
    def _valid_admin_token(token: str) -> bool:
        """Constant-time comparison against every configured admin token."""
        return any(
            hmac.compare_digest(token, admin_token)
            for admin_token in Cfg.XOLO_SUPER_ADMIN_TOKENS
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def create(
        self,
        account_id: str,
        name:       str,
        scopes:     list[APIKeyScope],
        expires_at: datetime.datetime | None = None,
    ) -> Result[tuple[APIKey, str], XoloException]:
        """Create a new API key. Returns (APIKey metadata, raw key).
        The raw key is returned exactly once and never stored."""
        log.debug(build_log_payload("apikeys.create.attempt", account_id=account_id, key_name=name, scopes=[scope.value for scope in scopes]))
        primary_scope = scopes[0].value if scopes else "all"
        raw_key       = self._generate_raw_key(primary_scope)
        key_hash      = self._hash(raw_key)
        key_id        = f"ak-{generate(size=12)}"

        api_key = APIKey(
            key_id     = key_id,
            key_hash   = key_hash,
            key_prefix = raw_key[:16],
            account_id = account_id,
            name       = name,
            scopes     = scopes,
            created_by = "admin",
            expires_at = expires_at,
        )

        result = await self.repository.save(api_key)
        if result.is_err:
            log.error(build_log_payload("apikeys.create.error", error=result.unwrap_err(), account_id=account_id, key_id=key_id, key_name=name))
            return Err(result.unwrap_err())

        log.info(build_log_payload("apikeys.create.service", account_id=account_id, key_id=key_id, key_name=name, scopes=[scope.value for scope in scopes]))
        return Ok((result.unwrap(), raw_key))

    async def list_keys(self) -> Result[list[APIKey], XoloException]:
        return await self.repository.find_all()

    async def get(self, key_id: str) -> Result[Option[APIKey], XoloException]:
        return await self.repository.find_by_id(key_id)

    async def list_keys_for_account(self, account_id: str) -> Result[list[APIKey], XoloException]:
        return await self.repository.find_all_for_account(account_id)

    async def delete(self, key_id: str) -> Result[bool, XoloException]:
        result = await self.repository.delete(key_id)
        if result.is_err:
            log.error(build_log_payload("apikeys.delete.error", error=result.unwrap_err(), key_id=key_id))
            return Err(result.unwrap_err())
        log.info(build_log_payload("apikeys.delete.service", key_id=key_id))
        return Ok(True)

    async def revoke(self, key_id: str) -> Result[bool, XoloException]:
        find_result = await self.repository.find_by_id(key_id)
        if find_result.is_err:
            log.error(build_log_payload("apikeys.revoke.error", error=find_result.unwrap_err(), key_id=key_id))
            return Err(find_result.unwrap_err())

        maybe = find_result.unwrap()
        if maybe.is_none:
            error = NotFoundError("APIKey", key_id)
            log.warning(build_log_payload("apikeys.revoke.error", error=error, key_id=key_id))
            return Err(error)

        save_result = await self.repository.save(maybe.unwrap().revoke())
        if save_result.is_err:
            log.error(build_log_payload("apikeys.revoke.error", error=save_result.unwrap_err(), key_id=key_id))
            return Err(save_result.unwrap_err())
        log.info(build_log_payload("apikeys.revoke.service", key_id=key_id))
        return Ok(True)

    async def rotate(self, key_id: str) -> Result[tuple[APIKey, str], XoloException]:
        """Generate a new secret for an existing key record, invalidating the old one."""
        find_result = await self.repository.find_by_id(key_id)
        if find_result.is_err:
            log.error(build_log_payload("apikeys.rotate.error", error=find_result.unwrap_err(), key_id=key_id))
            return Err(find_result.unwrap_err())

        maybe = find_result.unwrap()
        if maybe.is_none:
            error = NotFoundError("APIKey", key_id)
            log.warning(build_log_payload("apikeys.rotate.error", error=error, key_id=key_id))
            return Err(error)

        old        = maybe.unwrap()
        primary    = old.scopes[0].value if old.scopes else "all"
        raw_key    = self._generate_raw_key(primary)
        new_hash   = self._hash(raw_key)
        new_prefix = raw_key[:16]

        save_result = await self.repository.save(old.rotate(new_hash, new_prefix))
        if save_result.is_err:
            log.error(build_log_payload("apikeys.rotate.error", error=save_result.unwrap_err(), key_id=key_id))
            return Err(save_result.unwrap_err())

        log.info(build_log_payload("apikeys.rotate.service", key_id=key_id, key_prefix=new_prefix))
        return Ok((save_result.unwrap(), raw_key))

    async def validate(self, raw_key: str, required_scope: str) -> Result[APIKey, XoloException]:
        """Validate an incoming raw key and assert it covers required_scope.
        Updates last_used_at on success (best-effort)."""
        key_hash    = self._hash(raw_key)
        find_result = await self.repository.find_by_hash(key_hash)

        if find_result.is_err:
            log.error(build_log_payload("apikeys.validate.error", error=find_result.unwrap_err(), required_scope=required_scope))
            return Err(find_result.unwrap_err())

        maybe = find_result.unwrap()
        if maybe.is_none:
            error = UnauthorizedError("Invalid API key")
            log.warning(build_log_payload("apikeys.validate.error", error=error, required_scope=required_scope))
            return Err(error)

        api_key = maybe.unwrap()

        if not api_key.is_valid():
            error = UnauthorizedError("API key is revoked or expired")
            log.warning(build_log_payload("apikeys.validate.error", error=error, required_scope=required_scope, key_id=api_key.key_id))
            return Err(error)

        if not api_key.allows(required_scope):
            error = AccessDeniedError(
                f"API key does not have the '{required_scope}' scope",
                metadata={"required_scope": required_scope, "key_scopes": [s.value for s in api_key.scopes]},
            )
            log.warning(build_log_payload("apikeys.validate.error", error=error, required_scope=required_scope, key_id=api_key.key_id))
            return Err(error)

        await self.repository.update_last_used(api_key.key_id)
        log.debug(build_log_payload("apikeys.validate.service", required_scope=required_scope, key_id=api_key.key_id, key_name=api_key.name))
        return Ok(api_key)
