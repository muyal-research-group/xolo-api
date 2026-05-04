from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import time as T
from typing import Any
from uuid import uuid4

import humanfriendly as HF
import jwt
from option import Err, Ok, Result
from xolo.log import Log
from xolo.utils import Utils as XoloUtils

import commonx.errors as EX
import xoloapi.config as Cfg
import xoloapi.dto as DTO
from xoloapi.logging import build_log_payload
from xoloapi.security import Security
from xoloapi.licenses.application.licenses_service import LicensesService
import xoloapi.users.dto as UDTO
from xoloapi.users.domain.aggregates import PasswordResetToken
from xoloapi.users.domain.repositories import IPasswordResetRepository, IUsersRepository
from xoloapi.users.domain.services import IUsersMailer

log = Log(
    name="xolo.users.service",
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class UsersService:
    def __init__(
        self,
        repository: IUsersRepository,
        scopes_repository: Any,
        licenses_service: LicensesService,
        password_reset_repository: IPasswordResetRepository,
        users_mailer: IUsersMailer,
    ):
        self.repository = repository
        self.scopes_repository = scopes_repository
        self.licenses_service = licenses_service
        self.password_reset_repository = password_reset_repository
        self.users_mailer = users_mailer

    @staticmethod
    def _hash_reset_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _to_user_dto(user) -> DTO.UserDTO:
        return DTO.UserDTO(
            key=user.key,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            profile_photo=user.profile_photo,
            disabled=getattr(user, "disabled", False),
        )

    async def _find_user_by_identifier(self, account_id: str, identifier: str):
        normalized = identifier.strip()
        if "@" in normalized:
            return await self.repository.find_by_email(account_id, normalized)
        return await self.repository.find_by_username(account_id, normalized)

    async def request_password_recovery(self, account_id: str, dto: UDTO.PasswordRecoveryRequestDTO) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            identifier = dto.identifier.strip()
            log.debug(build_log_payload("users.password_recovery.request.attempt", identifier=identifier))
            maybe_user = await self._find_user_by_identifier(account_id, identifier)
            if maybe_user.is_none:
                log.info(build_log_payload("users.password_recovery.request", started_at=start_time, identifier=identifier, account_found=False))
                return Ok(True)

            user = maybe_user.unwrap()
            if not user.email:
                log.warning(build_log_payload("users.password_recovery.request.no_email", started_at=start_time, identifier=identifier, user_id=user.key, username=user.username))
                return Ok(True)

            invalidate_result = await self.password_reset_repository.invalidate_for_user(account_id=account_id, user_id=user.key)
            if invalidate_result.is_err:
                log.error(build_log_payload("users.password_recovery.request.error", started_at=start_time, error=invalidate_result.unwrap_err(), identifier=identifier, user_id=user.key, username=user.username))
                return Err(invalidate_result.unwrap_err())

            raw_token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken.new(
                user_id    = user.key,
                account_id = account_id,
                username   = user.username,
                email      = user.email,
                token_hash = self._hash_reset_token(raw_token),
                expires_in = Cfg.XOLO_PASSWORD_RESET_TOKEN_EXPIRES_IN,
            )

            create_result = await self.password_reset_repository.create(reset_token)
            if create_result.is_err:
                log.error(build_log_payload("users.password_recovery.request.error", started_at=start_time, error=create_result.unwrap_err(), identifier=identifier, user_id=user.key, username=user.username))
                return Err(create_result.unwrap_err())

            mail_result = await self.users_mailer.send_password_reset_email(
                recipient_email = user.email,
                recipient_name  = f"{user.first_name} {user.last_name}".strip() or user.username,
                reset_token     = raw_token,
                reset_url       = None,
                expires_in      = Cfg.XOLO_PASSWORD_RESET_TOKEN_EXPIRES_IN,
            )
            if mail_result.is_err:
                await self.password_reset_repository.invalidate_for_user(account_id=account_id, user_id=user.key)
                log.error(build_log_payload("users.password_recovery.request.error", started_at=start_time, error=mail_result.unwrap_err(), identifier=identifier, user_id=user.key, username=user.username))
                return Err(mail_result.unwrap_err())

            log.info(build_log_payload("users.password_recovery.request", started_at=start_time, identifier=identifier, user_id=user.key, username=user.username, account_found=True))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.password_recovery.request.error", started_at=start_time, error=e, identifier=getattr(dto, "identifier", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def confirm_password_recovery(self, account_id: str, dto: UDTO.PasswordRecoveryConfirmDTO) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            token_hash = self._hash_reset_token(dto.token.strip())
            log.debug(build_log_payload("users.password_recovery.confirm.attempt"))
            token_result = await self.password_reset_repository.find_active_by_hash(token_hash)
            if token_result.is_err:
                log.error(build_log_payload("users.password_recovery.confirm.error", started_at=start_time, error=token_result.unwrap_err()))
                return Err(token_result.unwrap_err())

            maybe_token = token_result.unwrap()
            if maybe_token.is_none:
                error = EX.Unauthorized(raw_detail="Invalid or expired password reset token")
                log.warning(build_log_payload("users.password_recovery.confirm.error", started_at=start_time, error=error))
                return Err(error)

            reset_token = maybe_token.unwrap()
            password_hash = XoloUtils.pbkdf2(password=dto.password)
            if reset_token.account_id != account_id:
                return Err(EX.AccessDenied(raw_detail="Password reset token does not belong to this account"))
            update_result = await self.repository.update_password(account_id=account_id, username=reset_token.username, password=password_hash)
            if update_result.is_err:
                log.error(build_log_payload("users.password_recovery.confirm.error", started_at=start_time, error=update_result.unwrap_err(), user_id=reset_token.user_id, username=reset_token.username))
                return Err(update_result.unwrap_err())

            mark_result = await self.password_reset_repository.mark_used(request_id=reset_token.request_id)
            if mark_result.is_err:
                log.error(build_log_payload("users.password_recovery.confirm.error", started_at=start_time, error=mark_result.unwrap_err(), user_id=reset_token.user_id, username=reset_token.username))
                return Err(mark_result.unwrap_err())

            revoke_result = await self.repository.delete_access_token(account_id=account_id, username=reset_token.username)
            if revoke_result.is_err:
                log.warning(build_log_payload("users.password_recovery.confirm.token_revoke.error", started_at=start_time, error=revoke_result.unwrap_err(), user_id=reset_token.user_id, username=reset_token.username))

            log.info(build_log_payload("users.password_recovery.confirm", started_at=start_time, user_id=reset_token.user_id, username=reset_token.username))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.password_recovery.confirm.error", started_at=start_time, error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def signup(self, account_id: str, dto: DTO.SignUpDTO) -> Result[DTO.CreatedUserResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            _username = dto.username.strip()
            _email = dto.email.strip()
            _first_name = dto.first_name.strip()
            _last_name = dto.last_name.strip()
            _scope = dto.scope.strip().upper()
            log.debug(build_log_payload("users.signup.attempt", username=_username, email=_email, first_name=_first_name, last_name=_last_name, scope_name=_scope))
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=_username)
            if maybe_user.is_some:
                e = EX.AlreadyExists(raw_detail="Username already exists", metadata={"entity": "user", "id": _username})
                log.warning(build_log_payload("users.signup.error", started_at=start_time, error=e, username=_username, scope_name=_scope))
                return Err(e)

            scope_exists = (await self.scopes_repository.exists_scope(account_id=account_id, name=_scope)).unwrap_or(False)
            if not scope_exists:
                e = EX.NotFound(raw_detail="Scope not found", metadata={"entity": "scope", "id": _scope})
                log.warning(build_log_payload("users.signup.error", started_at=start_time, error=e, username=_username, scope_name=_scope))
                return Err(e)

            _password = XoloUtils.pbkdf2(password=dto.password)
            result = await self.repository.create(
                account_id=account_id,
                user=DTO.CreateUserDTO(
                    username=_username,
                    first_name=_first_name,
                    last_name=_last_name,
                    email=_email,
                    profile_photo=f"https://api.dicebear.com/9.x/fun-emoji/svg?seed={_username}",
                    password=_password,
                )
            )
            if result.is_err:
                log.error(build_log_payload("users.signup.error", started_at=start_time, error=result.unwrap_err(), username=_username, email=_email, scope_name=_scope))
                return Err(result.unwrap_err())

            key = result.unwrap()
            log.info(build_log_payload("users.signup.user_created", started_at=start_time, user_id=key, username=_username, email=_email, first_name=_first_name, last_name=_last_name, scope_name=_scope))

            res = await self.scopes_repository.assign(account_id=account_id, dto=DTO.AssignScopeDTO(name=_scope, username=_username))
            if res.is_err:
                log.error(build_log_payload("users.signup.scope_assign.error", started_at=start_time, error=res.unwrap_err(), user_id=key, username=_username, scope_name=_scope))
                cleanup = await self.repository.delete_by_id(user_id=key, account_id=account_id)
                if cleanup.is_err:
                    log.error(build_log_payload("users.signup.rollback.error", started_at=start_time, error=cleanup.unwrap_err(), user_id=key, username=_username, scope_name=_scope))
                return Err(cleanup.unwrap_err()) if cleanup.is_err else Err(res.unwrap_err())

            log.info(build_log_payload("users.signup.scope_assign", started_at=start_time, user_id=key, username=_username, scope_name=_scope))

            res = await self.licenses_service.assign_license(
                account_id=account_id,
                dto=DTO.AssignLicenseDTO(
                    username=_username,
                    scope=_scope,
                    expires_in=dto.expiration,
                    force=True,
                )
            )
            if res.is_err:
                log.error(build_log_payload("users.signup.license_assign.error", started_at=start_time, error=res.unwrap_err(), user_id=key, username=_username, scope_name=_scope))
                cleanup = await self.repository.delete_by_id(user_id=key, account_id=account_id)
                if cleanup.is_err:
                    log.error(build_log_payload("users.signup.rollback.error", started_at=start_time, error=cleanup.unwrap_err(), user_id=key, username=_username, scope_name=_scope))
                return Err(cleanup.unwrap_err()) if cleanup.is_err else Err(res.unwrap_err())

            log.info(build_log_payload("users.signup.license_assign", started_at=start_time, user_id=key, username=_username, scope_name=_scope))
            welcome_mail_result = await self.users_mailer.send_welcome_email(
                recipient_email=_email,
                recipient_name=f"{_first_name} {_last_name}".strip() or _username,
                username=_username,
                scope=_scope,
            )
            if welcome_mail_result.is_err:
                log.warning(
                    build_log_payload(
                        "users.signup.welcome_email.error",
                        started_at=start_time,
                        error=welcome_mail_result.unwrap_err(),
                        user_id=key,
                        username=_username,
                        scope_name=_scope,
                    )
                )
            else:
                log.info(build_log_payload("users.signup.welcome_email", started_at=start_time, user_id=key, username=_username, scope_name=_scope))
            return Ok(DTO.CreatedUserResponseDTO(key=key))
        except Exception as e:
            log.error(build_log_payload("users.signup.error", started_at=start_time, error=e, username=getattr(dto, "username", None), scope_name=getattr(dto, "scope", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def get_by_id(self, user_id: str, account_id: str | None = None) -> Result[DTO.UserDTO, EX.XError]:
        try:
            maybe_user = await self.repository.find_by_id(user_id=user_id, account_id=account_id)
            if maybe_user.is_none:
                return Err(EX.NotFound(raw_detail="User not found"))
            user = maybe_user.unwrap()
            return Ok(self._to_user_dto(user))
        except Exception as e:
            return Err(EX.ServerError(raw_detail=str(e)))

    async def list_users(self, account_id: str) -> Result[list[DTO.UserDTO], EX.XError]:
        start_time = T.time()
        try:
            result = await self.repository.find_all(account_id=account_id)
            if result.is_err:
                log.error(build_log_payload("users.list.error", started_at=start_time, error=result.unwrap_err()))
                return Err(result.unwrap_err())
            users = [self._to_user_dto(user) for user in result.unwrap()]
            log.info(build_log_payload("users.list", started_at=start_time, user_count=len(users)))
            return Ok(users)
        except Exception as e:
            log.error(build_log_payload("users.list.error", started_at=start_time, error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def delete_user(self, account_id: str, username: str) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            normalized_username = username.strip()
            log.debug(build_log_payload("users.delete.attempt", username=normalized_username))
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=normalized_username)
            if maybe_user.is_none:
                error = EX.NotFound(raw_detail="User not found")
                log.warning(build_log_payload("users.delete.error", started_at=start_time, error=error, username=normalized_username))
                return Err(error)

            user = maybe_user.unwrap()
            licenses_result = await self.licenses_service.repository.delete_all_by_username(account_id=account_id, username=normalized_username)
            if licenses_result.is_err:
                log.error(build_log_payload("users.delete.error", started_at=start_time, error=licenses_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(licenses_result.unwrap_err())

            assignments_result = await self.scopes_repository.delete_assignments_for_username(account_id=account_id, username=normalized_username)
            if assignments_result.is_err:
                log.error(build_log_payload("users.delete.error", started_at=start_time, error=assignments_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(assignments_result.unwrap_err())

            reset_result = await self.password_reset_repository.invalidate_for_user(account_id=account_id, user_id=user.key)
            if reset_result.is_err:
                log.error(build_log_payload("users.delete.error", started_at=start_time, error=reset_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(reset_result.unwrap_err())

            revoke_result = await self.repository.delete_access_token(account_id=account_id, username=normalized_username)
            if revoke_result.is_err:
                log.error(build_log_payload("users.delete.error", started_at=start_time, error=revoke_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(revoke_result.unwrap_err())

            delete_result = await self.repository.delete_by_id(user_id=user.key, account_id=account_id)
            if delete_result.is_err:
                log.error(build_log_payload("users.delete.error", started_at=start_time, error=delete_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(delete_result.unwrap_err())

            log.info(
                build_log_payload(
                    "users.delete",
                    started_at=start_time,
                    username=normalized_username,
                    user_id=user.key,
                    removed_assignments=assignments_result.unwrap(),
                    removed_licenses=licenses_result.unwrap(),
                )
            )
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.delete.error", started_at=start_time, error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def logout(self, account_id: str, dto: DTO.LogoutDTO) -> Result[bool, EX.XError]:
        try:
            start_time = T.time()
            _username = dto.username.strip()
            log.debug(build_log_payload("users.logout.attempt", username=_username))
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=_username)
            if maybe_user.is_none:
                error = EX.NotFound(raw_detail="User not found")
                log.warning(build_log_payload("users.logout.error", started_at=start_time, error=error, username=_username))
                return Err(error)
            res = await self.repository.delete_access_token(account_id=account_id, username=_username)
            if res.is_err:
                log.error(build_log_payload("users.logout.error", started_at=start_time, error=res.unwrap_err(), username=_username))
                return Err(res.unwrap_err())
            log.info(build_log_payload("users.logout", started_at=start_time, username=_username))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.logout.error", started_at=start_time, error=e, username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def update_password(self, account_id: str, dto: DTO.UpdateUserPasswordDTO) -> Result[DTO.UpdateUserPasswordResponseDTO, EX.XError]:
        try:
            start_time = T.time()
            _username = dto.username.strip()
            log.debug(build_log_payload("users.password_update.attempt", username=_username))
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=_username)
            if maybe_user.is_none:
                error = EX.NotFound(raw_detail="User not found")
                log.warning(build_log_payload("users.password_update.error", started_at=start_time, error=error, username=_username))
                return Err(error)
            new_password = XoloUtils.pbkdf2(password=dto.password)
            updated_result = await self.repository.update_password(account_id=account_id, username=_username, password=new_password)
            if updated_result.is_ok:
                log.info(build_log_payload("users.password_update", started_at=start_time, username=_username))
                return Ok(DTO.UpdateUserPasswordResponseDTO(ok=updated_result.unwrap()))
            log.error(build_log_payload("users.password_update.error", started_at=start_time, error=updated_result.unwrap_err(), username=_username))
            return updated_result
        except Exception as e:
            log.error(build_log_payload("users.password_update.error", started_at=start_time, error=e, username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def create_user(self, account_id: str, dto: DTO.CreateUserDTO) -> Result[DTO.CreatedUserResponseDTO, EX.XError]:
        try:
            start_time  = T.time()
            _username   = dto.username.strip()
            _email      = dto.email.strip()
            _first_name = dto.first_name.strip()
            _last_name  = dto.last_name.strip()
            log.debug(build_log_payload("users.create.attempt", username=_username, email=_email, first_name=_first_name, last_name=_last_name))
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=_username)
            if maybe_user.is_some:
                e = EX.AlreadyExists(raw_detail="Username already exists", metadata={"entity": "user", "id": _username})
                log.warning(build_log_payload("users.create.error", started_at=start_time, error=e, username=_username))
                return Err(e)

            _password = XoloUtils.pbkdf2(password=dto.password)
            result = await self.repository.create(
                account_id=account_id,
                user=DTO.CreateUserDTO(
                    username      = _username,
                    first_name    = _first_name,
                    last_name     = _last_name,
                    email         = _email,
                    profile_photo = "https://www.eldersinsurance.com.au/images/person1.png?width=368&height=278&crop=1",
                    password      = _password,
                )
            )
            if result.is_err:
                log.error(build_log_payload("users.create.error", started_at=start_time, error=result.unwrap_err(), username=_username, email=_email))
                return Err(result.unwrap_err())

            key = result.unwrap()
            log.info(build_log_payload("users.create", started_at=start_time, user_id=key, username=_username, email=_email, first_name=_first_name, last_name=_last_name))
            return Ok(DTO.CreatedUserResponseDTO(key=key))
        except Exception as e:
            log.error(build_log_payload("users.create.error", started_at=start_time, error=e, username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def check_license_and_scope(self, account_id: str, username: str, scope: str) -> Result[bool, EX.XError]:
        try:
            scope_exists = (await self.scopes_repository.exists_scope(account_id=account_id, name=scope)).unwrap_or(False)
            if not scope_exists:
                log.warning(build_log_payload("users.scope_check.error", username=username, scope_name=scope, error=EX.Unauthorized(raw_detail="Invalid scope")))
                return Err(EX.Unauthorized(raw_detail="Invalid scope"))

            license_result = await self.licenses_service.repository.find_by_username_and_scope(account_id=account_id, username=username, scope=scope)
            if license_result.is_err:
                e = license_result.unwrap_err()
                log.warning(build_log_payload("users.scope_check.error", username=username, scope_name=scope, error=e))
                return Err(EX.InvalidLicense(raw_detail=e.detail.raw_error))
            license = license_result.unwrap()
            license_is_valid = self.licenses_service.lm.verify(user_id=username, app_id=scope, license_key=license).unwrap_or(False)
            return Ok(license_is_valid)
        except Exception as e:
            log.error(build_log_payload("users.scope_check.error", username=username, scope_name=scope, error=e))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def auth(self, account_id: str, dto: DTO.AuthDTO) -> Result[DTO.AuthenticatedDTO, EX.XError]:
        try:
            start_time = T.time()
            dto.username = dto.username.strip()
            dto.scope = dto.scope.strip().upper()
            expiration = dto.expiration[0] if isinstance(dto.expiration, tuple) else dto.expiration
            log.debug(build_log_payload("users.auth.attempt", username=dto.username, scope_name=dto.scope, renew_token=dto.renew_token))

            maybe_user = await self.repository.find_by_username(account_id=account_id, username=dto.username)
            if maybe_user.is_none:
                error = EX.NotFound(raw_detail="User not found")
                log.warning(build_log_payload("users.auth.error", started_at=start_time, error=error, username=dto.username, scope_name=dto.scope))
                return Err(error)
            user = maybe_user.unwrap()
            if getattr(user, "disabled", False):
                error = EX.InactiveUserError(user_id=str(user.key))
                log.warning(build_log_payload("users.auth.error", started_at=start_time, error=error, username=dto.username, scope_name=dto.scope, user_id=user.key))
                return Err(error)

            is_auth = XoloUtils.check_password_hash(password=dto.password, password_hash=user.hash_password)
            scope_exists = (await self.scopes_repository.exists_scope(account_id=account_id, name=dto.scope)).unwrap_or(False)
            if not scope_exists:
                log.warning(build_log_payload("users.auth.error", started_at=start_time, error=EX.Unauthorized(raw_detail="Invalid scope"), username=dto.username, scope_name=dto.scope))
                return Err(EX.Unauthorized(raw_detail="Invalid scope"))

            belongs_to = (await self.scopes_repository.exists_scope_user(account_id=account_id, name=dto.scope, username=dto.username)).unwrap_or(False)
            license_result = await self.licenses_service.repository.find_by_username_and_scope(account_id=account_id, username=dto.username, scope=dto.scope)
            if license_result.is_err:
                e = license_result.unwrap_err()
                log.warning(build_log_payload("users.auth.error", started_at=start_time, error=e, username=dto.username, scope_name=dto.scope))
                return Err(EX.InvalidLicense(raw_detail=str(e)))
            license = license_result.unwrap()
            license_is_valid = self.licenses_service.lm.verify(
                user_id=dto.username,
                app_id=dto.scope,
                license_key=license,
            ).unwrap_or(False)

            if not belongs_to and is_auth:
                log.warning(build_log_payload("users.auth.error", started_at=start_time, error=EX.UnauthorizedScope(raw_detail="User does not belong to the specified scope"), username=dto.username, scope_name=dto.scope))
                return Err(EX.UnauthorizedScope(raw_detail="User does not belong to the specified scope"))
            if not license_is_valid:
                log.warning(build_log_payload("users.auth.error", started_at=start_time, error=EX.InvalidLicense(raw_detail="License is invalid or expired"), username=dto.username, scope_name=dto.scope))
                return Err(EX.InvalidLicense(raw_detail="License is invalid or expired"))
            if belongs_to and is_auth and license_is_valid:
                if dto.renew_token:
                    await self.repository.delete_access_token(account_id=account_id, username=dto.username)

                access_token_result = await self.repository.get_access_token(account_id=account_id, username=dto.username)
                if access_token_result.is_ok:
                    token_maybe = access_token_result.unwrap()
                    if token_maybe.is_some:
                        access_token, temp_secret_key = token_maybe.unwrap()
                        log.info(build_log_payload("users.auth.cached", started_at=start_time, username=dto.username, user_id=user.key, scope_name=dto.scope))
                        return Ok(
                            DTO.AuthenticatedDTO(
                                username=dto.username,
                                email=user.email,
                                first_name=user.first_name,
                                last_name=user.last_name,
                                profile_photo=user.profile_photo,
                                access_token=access_token,
                                temporal_secret=temp_secret_key,
                                metadata={},
                                user_id=user.key,
                            )
                        )

                temp_secret_key = uuid4().hex
                iat = datetime.now(timezone.utc)
                exp_in_seconds = HF.parse_timespan(expiration)
                exp = iat + timedelta(seconds=exp_in_seconds)
                access_token = Security.create_access_token(
                    SECRET_KEY=temp_secret_key,
                    ALGORITHM=Security.ALGORITHM,
                    data={
                        "sub": user.key,
                        "aid": account_id,
                        "exp": exp.timestamp(),
                        "iss": dto.scope,
                        "iat": iat.timestamp(),
                        "uid2": user.username,
                    },
                    expires_delta=timedelta(seconds=exp_in_seconds),
                )
                res = await self.repository.set_access_token(
                    username=dto.username,
                    account_id=account_id,
                    access_token=access_token,
                    temp_secret_key=temp_secret_key,
                    exp=expiration,
                )
                if res.is_err:
                    log.error(build_log_payload("users.auth.token_store.error", started_at=start_time, error=res.unwrap_err(), username=dto.username, user_id=user.key, scope_name=dto.scope))
                    return Err(res.unwrap_err())

                log.info(build_log_payload("users.auth", started_at=start_time, username=dto.username, user_id=user.key, scope_name=dto.scope))
                return Ok(
                    DTO.AuthenticatedDTO(
                        username=user.username,
                        email=user.email,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        profile_photo=user.profile_photo,
                        access_token=access_token,
                        temporal_secret=temp_secret_key,
                        metadata={},
                        user_id=user.key,
                    )
                )
            error = EX.Unauthorized(raw_detail="Incorrect username or password")
            log.warning(build_log_payload("users.auth.error", started_at=start_time, error=error, username=dto.username, scope_name=dto.scope))
            return Err(error)
        except Exception as e:
            log.error(build_log_payload("users.auth.error", started_at=start_time, error=e, username=getattr(dto, "username", None), scope_name=getattr(dto, "scope", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def block_user(self, account_id: str, username: str) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            normalized_username = username.strip()
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=normalized_username)
            if maybe_user.is_none:
                error = EX.NotFound(entity="User")
                log.warning(build_log_payload("users.block.error", started_at=start_time, error=error, username=normalized_username))
                return Err(error)
            user = maybe_user.unwrap()

            disable_result = await self.repository.disable_user(account_id=account_id, username=normalized_username)
            if disable_result.is_err:
                log.error(build_log_payload("users.block.error", started_at=start_time, error=disable_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(disable_result.unwrap_err())

            revoke_result = await self.repository.delete_access_token(account_id=account_id, username=normalized_username)
            if revoke_result.is_err:
                log.error(build_log_payload("users.block.error", started_at=start_time, error=revoke_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(revoke_result.unwrap_err())

            log.info(build_log_payload("users.block", started_at=start_time, username=normalized_username, user_id=user.key))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.block.error", started_at=start_time, error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def unblock_user(self, account_id: str, username: str) -> Result[bool, EX.XError]:
        start_time = T.time()
        try:
            normalized_username = username.strip()
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=normalized_username)
            if maybe_user.is_none:
                error = EX.NotFound(entity="User")
                log.warning(build_log_payload("users.unblock.error", started_at=start_time, error=error, username=normalized_username))
                return Err(error)
            user = maybe_user.unwrap()

            enable_result = await self.repository.enable_user(account_id=account_id, username=normalized_username)
            if enable_result.is_err:
                log.error(build_log_payload("users.unblock.error", started_at=start_time, error=enable_result.unwrap_err(), username=normalized_username, user_id=user.key))
                return Err(enable_result.unwrap_err())

            log.info(build_log_payload("users.unblock", started_at=start_time, username=normalized_username, user_id=user.key))
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload("users.unblock.error", started_at=start_time, error=e, username=username))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def disable_user(self, account_id: str, dto: DTO.EnableOrDisableUserDTO) -> Result[bool, EX.XError]:
        try:
            start_time = T.time()
            username = dto.username.strip()
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=username)
            if maybe_user.is_none:
                error = EX.NotFound(entity="User")
                log.warning(build_log_payload("users.disable.error", started_at=start_time, error=error, username=username))
                return Err(error)
            res = await self.repository.disable_user(account_id=account_id, username=username)
            if res.is_err:
                log.error(build_log_payload("users.disable.error", started_at=start_time, error=res.unwrap_err(), username=username))
                return Err(res.unwrap_err())
            log.info(build_log_payload("users.disable", started_at=start_time, username=username))
            return Ok(res.unwrap())
        except Exception as e:
            log.error(build_log_payload("users.disable.error", started_at=start_time, error=e, username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def enable_user(self, account_id: str, dto: DTO.EnableOrDisableUserDTO) -> Result[bool, EX.XError]:
        try:
            start_time = T.time()
            username = dto.username.strip()
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=username)
            if maybe_user.is_none:
                error = EX.NotFound(entity="User")
                log.warning(build_log_payload("users.enable.error", started_at=start_time, error=error, username=username))
                return Err(error)
            res = await self.repository.enable_user(account_id=account_id, username=username)
            if res.is_err:
                log.error(build_log_payload("users.enable.error", started_at=start_time, error=res.unwrap_err(), username=username))
                return Err(res.unwrap_err())
            log.info(build_log_payload("users.enable", started_at=start_time, username=username))
            return Ok(res.unwrap())
        except Exception as e:
            log.error(build_log_payload("users.enable.error", started_at=start_time, error=e, username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def verify(self, account_id: str, dto: DTO.VerifyDTO) -> Result[bool, EX.XError]:
        try:
            start_time = T.time()
            username = dto.username.strip()
            log.debug(build_log_payload("users.verify.attempt", username=username))
            maybe_user = await self.repository.find_by_username(account_id=account_id, username=username)
            if maybe_user.is_none:
                error = EX.NotFound(raw_detail="User not found by username", metadata={"entity": "User", "id": username})
                log.warning(build_log_payload("users.verify.error", started_at=start_time, error=error, username=username))
                return Err(error)

            access_token_result = await self.repository.get_access_token(account_id=account_id, username=username)
            if access_token_result.is_err:
                log.warning(build_log_payload("users.verify.error", started_at=start_time, error=access_token_result.unwrap_err(), username=username))
                return Err(EX.Unauthorized(raw_detail=access_token_result.unwrap_err().detail.raw_error))

            access_token_maybe = access_token_result.unwrap()
            if access_token_maybe.is_none:
                error = EX.Unauthorized(raw_detail="No access token found")
                log.warning(build_log_payload("users.verify.error", started_at=start_time, error=error, username=username))
                return Err(error)

            stored_access_token, stored_secret = access_token_maybe.unwrap()
            if stored_access_token != dto.access_token:
                error = EX.Unauthorized(raw_detail="Invalid access token")
                log.warning(build_log_payload("users.verify.error", started_at=start_time, error=error, username=username))
                return Err(error)
            if stored_secret != dto.secret:
                error = EX.Unauthorized(raw_detail="Invalid secret key")
                log.warning(build_log_payload("users.verify.error", started_at=start_time, error=error, username=username))
                return Err(error)

            claims = jwt.decode(jwt=dto.access_token, key=dto.secret, algorithms=["HS256"])
            if claims.get("aid") != account_id:
                error = EX.AccessDenied(raw_detail="Token does not belong to this account")
                log.warning(build_log_payload("users.verify.error", started_at=start_time, error=error, username=username, account_id=account_id))
                return Err(error)
            current_time = datetime.now(timezone.utc).timestamp()
            expiration_time = float(claims.get("exp", 0))
            if current_time <= expiration_time:
                log.info(build_log_payload("users.verify", started_at=start_time, username=username))
                return Ok(True)
            error = EX.TokenExpired(raw_detail="Token has expired.")
            log.warning(build_log_payload("users.verify.error", started_at=start_time, error=error, username=username))
            return Err(error)
        except Exception as e:
            log.error(build_log_payload("users.verify.error", started_at=start_time, error=e, username=getattr(dto, "username", None)))
            return Err(EX.ServerError(raw_detail=str(e)))
