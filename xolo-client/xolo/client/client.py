import sys
import warnings
from typing import Any, Dict, List, Optional

import pyparsing as pp
import requests as R
from option import Err, Ok, Result

import xolo.client.errors as E
import xolo.client.models as M
from xolo.policies.parser import build_parser
from xolo.policies.parser.models import Command


class XoloClient(object):
    def __init__(
        self,
        account_id: str,
        api_key: str,
        api_url: str = "http://localhost:10000/api/v4",
        secret: str = "",
        admin_token: str = "",
    ):
        """Create a client for the Xolo API.

        Args:
            account_id: Account identifier used for account-scoped endpoints.
            api_key: Account API key used for API-key-protected endpoints.
            api_url: Base API root, typically ending in ``/api/v4``.
            secret: Legacy compatibility field retained for older callers.
            admin_token: Admin token used for account administration endpoints.
        """
        normalized_account_id = account_id.strip()
        if not normalized_account_id:
            raise ValueError("account_id is required")

        self.api_url = api_url.rstrip("/")
        self.account_id = normalized_account_id
        self.secret = secret
        self.api_key = api_key.strip()
        self.admin_token = admin_token.strip()
        self.parser = build_parser()

    def execute_script(self, script_text: str) -> List:
        """Parse and execute an Xolo-CL script.

        Args:
            script_text: Full script text to parse and execute.

        Returns:
            A list with the result produced by each parsed command.
        """
        try:
            command_list: List[Command] = self.parser.parseString(script_text, parseAll=True)
        except pp.ParseException as e:
            print("--- PARSING FAILED ---", file=sys.stderr)
            print(f"Error on line {e.lineno}, col {e.col}:", file=sys.stderr)
            print(e.line, file=sys.stderr)
            print(" " * (e.col - 1) + "^", file=sys.stderr)
            print(e, file=sys.stderr)
            raise Exception("Parsing Failed")

        results = []
        for cmd in command_list:
            try:
                results.append(cmd.execute(self))
            except Exception as e:
                print(f"[FATAL] Unhandled error executing command {cmd}: {e}", file=sys.stderr)
        return results

    def base_url(self) -> str:
        """Return the default account-scoped API root.

        Returns:
            The account-scoped base URL used by most client methods.
        """
        return self._account_url()

    def _account_url(self, path: str = "") -> str:
        suffix = f"/{path.lstrip('/')}" if path else ""
        return f"{self.api_url}/accounts/{self.account_id}{suffix}"

    def _global_url(self, path: str = "") -> str:
        suffix = f"/{path.lstrip('/')}" if path else ""
        return f"{self.api_url}{suffix}"

    def __process_exception(self, e: R.HTTPError) -> E.XoloError:
        if e.response is None:
            return E.XoloError.from_exception(e)

        try:
            body = e.response.json()
            error_detail = body.get("detail", body) if isinstance(body, dict) else body
        except ValueError:
            error_detail = e.response.text or str(e)

        return E.XoloError.from_http_response(
            status_code=e.response.status_code,
            detail=error_detail,
            headers=dict(e.response.headers),
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        json: Any = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> R.Response:
        response = R.request(method=method, url=url, headers=headers, json=json, params=params)
        response.raise_for_status()
        return response

    def _response_json(self, response: R.Response) -> Any:
        if not response.content:
            return None
        return response.json()

    def _secret_headers(self, secret: str = "") -> Dict[str, str]:
        resolved_secret = (secret or self.secret).strip()
        return {"Secret": resolved_secret} if resolved_secret else {}

    def _admin_headers(self, admin_token: str = "", *, required: bool = False) -> Dict[str, str]:
        resolved_admin_token = (admin_token or self.admin_token).strip()
        if required and not resolved_admin_token:
            raise ValueError("admin_token is required for this operation")
        return {"X-Admin-Token": resolved_admin_token} if resolved_admin_token else {}

    def _api_key_headers(self, api_key: str = "", *, required: bool = False) -> Dict[str, str]:
        resolved_api_key = (api_key or self.api_key).strip()
        if required and not resolved_api_key:
            raise ValueError("api_key is required for this operation")
        return {"X-API-Key": resolved_api_key} if resolved_api_key else {}

    def _admin_or_api_headers(
        self,
        api_key: str = "",
        admin_token: str = "",
        *,
        required: bool = False,
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        headers.update(self._admin_headers(admin_token))
        headers.update(self._api_key_headers(api_key))
        if required and not headers:
            raise ValueError("admin_token or api_key is required for this operation")
        return headers

    def _bearer_headers(
        self,
        token: str,
        temporal_secret: str = "",
        *,
        api_key: str = "",
        include_api_key: bool = False,
    ) -> Dict[str, str]:
        resolved_token = token.strip()
        if not resolved_token:
            raise ValueError("token is required for this operation")

        headers = {"Authorization": f"Bearer {resolved_token}"}
        if temporal_secret.strip():
            headers["Temporal-Secret-Key"] = temporal_secret.strip()
        if include_api_key:
            headers.update(self._api_key_headers(api_key, required=True))
        return headers

    def _authz_headers(
        self,
        token: str,
        temporal_secret: str = "",
        *,
        api_key: str = "",
        admin_token: str = "",
    ) -> Dict[str, str]:
        headers = self._bearer_headers(token=token, temporal_secret=temporal_secret)
        headers.update(self._admin_or_api_headers(api_key=api_key, admin_token=admin_token, required=True))
        return headers

    def _list_json(self, response: R.Response) -> List[Any]:
        payload = self._response_json(response)
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError("Expected a list response")
        return payload

    def list_accounts(self, admin_token: str = "") -> Result[List[M.AccountDTO], E.XoloError]:
        """List accounts visible to the admin token.

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a list of account DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._global_url("accounts"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.AccountDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_account(
        self, account_id: str, name: str, timezone: str = "UTC", admin_token: str = ""
    ) -> Result[M.AccountDTO, E.XoloError]:
        """Create an account.

        Args:
            account_id: New account identifier.
            name: Human-readable account name.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the created account DTO.
        """
        try:
            payload = M.CreateAccountDTO(account_id=account_id, name=name, timezone=timezone)
            response = self._request(
                "POST",
                self._global_url("accounts"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            data = self._response_json(response) or payload.model_dump()
            return Ok(M.AccountDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_account(
        self,
        account_id: str,
        *,
        name: Optional[str] = None,
        timezone: Optional[str] = None,
        is_active: Optional[bool] = None,
        admin_token: str = "",
    ) -> Result[M.AccountDTO, E.XoloError]:
        """Update account metadata, including its default IANA timezone."""
        try:
            payload = M.UpdateAccountDTO(name=name, timezone=timezone, is_active=is_active)
            response = self._request(
                "PATCH",
                self._global_url(f"accounts/{account_id}"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.AccountDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_account(self, account_id: str, admin_token: str = "") -> Result[M.DeletedAccountResponseDTO, E.XoloError]:
        """Delete an account.

        Args:
            account_id: Account identifier to delete.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a synthetic deletion DTO.
        """
        try:
            self._request(
                "DELETE",
                f"{self._global_url('accounts')}/{account_id}",
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.DeletedAccountResponseDTO(account_id=account_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def signup(
        self,
        username: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        scope: str,
        profile_photo: str = "",
        expiration: str = "1h",
        api_key: str = "",
    ) -> Result[M.CreatedUserResponseDTO, E.XoloError]:
        """Sign up a new end user within the configured account.

        Args:
            username: Username to create.
            first_name: User first name.
            last_name: User last name.
            email: User email.
            password: Plain-text password.
            scope: Scope requested for the signup flow.
            profile_photo: Optional profile-photo URL.
            expiration: Access-token expiration hint.
            api_key: Optional API-key override for this request.

        Returns:
            A ``Result`` containing the created-user DTO.
        """
        try:
            payload = M.SignUpDTO(
                email=email.strip(),
                username=username.strip(),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                password=password.strip(),
                profile_photo=profile_photo.strip(),
                scope=scope.upper().strip(),
                expiration=expiration.strip(),
            )
            response = self._request(
                "POST",
                self._account_url("users/signup"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.CreatedUserResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_user(
        self,
        username: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        profile_photo: str = "",
        admin_token: str = "",
        role: Optional[str] = None,
    ) -> Result[M.CreatedUserResponseDTO, E.XoloError]:
        """Create a user through the admin API.

        Args:
            username: Username to create.
            first_name: User first name.
            last_name: User last name.
            email: User email.
            password: Plain-text password.
            profile_photo: Optional profile-photo URL.
            admin_token: Optional admin-token override.
            role: Legacy compatibility field ignored by the account API.

        Returns:
            A ``Result`` containing the created-user DTO.
        """
        try:
            _ = role
            payload = M.CreateUserDTO(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                profile_photo=profile_photo,
            )
            response = self._request(
                "POST",
                self._account_url("users"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.CreatedUserResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_users(self, admin_token: str = "") -> Result[List[M.UserDTO], E.XoloError]:
        """List all users in the configured account.

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the user list.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("users/all"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.UserDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_users_discovery(self, admin_token: str = "") -> Result[List[M.UserDTO], E.XoloError]:
        """List users for discovery/autocomplete (lightweight, no pagination).

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the user list.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("users/list"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.UserDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_user(self, username: str, api_key: str = "", *, admin_token: str = "") -> Result[M.DeletedUserResponseDTO, E.XoloError]:
        """Delete a user by username.

        Args:
            username: Username to delete.
            api_key: Optional API-key override. The key must have the ``users`` scope.
            admin_token: Deprecated. Ignored. Pass ``api_key`` instead.

        Returns:
            A ``Result`` containing a synthetic deletion DTO.
        """
        if admin_token:
            warnings.warn(
                "admin_token is deprecated for delete_user; the endpoint now requires X-API-Key with the 'users' scope.",
                DeprecationWarning,
                stacklevel=2,
            )
        try:
            self._request(
                "DELETE",
                self._account_url(f"users/{username}"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(M.DeletedUserResponseDTO(username=username))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def block_user(self, username: str, admin_token: str = "") -> Result[M.BlockedUserResponseDTO, E.XoloError]:
        """Block a user through the admin API.

        Args:
            username: Username to block.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a synthetic block DTO.
        """
        try:
            self._request(
                "POST",
                self._account_url(f"users/{username}/block"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.BlockedUserResponseDTO(username=username))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def unblock_user(self, username: str, admin_token: str = "") -> Result[M.UnblockedUserResponseDTO, E.XoloError]:
        """Unblock a user through the admin API.

        Args:
            username: Username to unblock.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a synthetic unblock DTO.
        """
        try:
            self._request(
                "POST",
                self._account_url(f"users/{username}/unblock"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.UnblockedUserResponseDTO(username=username))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def enable_user(self, username: str, token: str, temporal_secret: str) -> Result[M.UserEnabledResponseDTO, E.XoloError]:
        """Enable a user with bearer-token authorization.

        Args:
            username: Username to enable.
            token: Bearer access token.
            temporal_secret: Temporal secret key.

        Returns:
            A ``Result`` containing a synthetic enable DTO.
        """
        try:
            payload = M.EnableOrDisableUserDTO(username=username)
            self._request(
                "POST",
                self._account_url(f"users/{username}/enable"),
                headers=self._bearer_headers(token=token, temporal_secret=temporal_secret),
                json=payload.model_dump(),
            )
            return Ok(M.UserEnabledResponseDTO(username=username))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def disable_user(self, username: str, token: str, temporal_secret: str) -> Result[M.UserDisabledResponseDTO, E.XoloError]:
        """Disable a user with bearer-token authorization.

        Args:
            username: Username to disable.
            token: Bearer access token.
            temporal_secret: Temporal secret key.

        Returns:
            A ``Result`` containing a synthetic disable DTO.
        """
        try:
            payload = M.EnableOrDisableUserDTO(username=username)
            self._request(
                "POST",
                self._account_url(f"users/{username}/disable"),
                headers=self._bearer_headers(token=token, temporal_secret=temporal_secret),
                json=payload.model_dump(),
            )
            return Ok(M.UserDisabledResponseDTO(username=username))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def verify_token(self, access_token: str, username: str, secret: str = "") -> Result[M.VerifyTokenResponseDTO, E.XoloError]:
        """Verify a user token using the account verification endpoint.

        Args:
            access_token: Access token to verify.
            username: Token owner username.
            secret: Temporal secret associated with the token.

        Returns:
            A ``Result`` containing a synthetic verification DTO.
        """
        try:
            payload = M.VerifyDTO(access_token=access_token, username=username, secret=secret)
            self._request("POST", self._account_url("users/verify"), json=payload.model_dump())
            return Ok(M.VerifyTokenResponseDTO(username=username, access_token=access_token))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def introspect_session(
        self,
        access_token: str,
        temporal_secret: str,
        api_key: str = "",
    ) -> Result[M.UserDTO, E.XoloError]:
        """Resolve an active Xolo session to its user from a trusted service."""
        try:
            response = self._request(
                "POST",
                self._account_url("users/introspect"),
                headers=self._bearer_headers(
                    token=access_token,
                    temporal_secret=temporal_secret,
                    api_key=api_key,
                    include_api_key=True,
                ),
            )
            return Ok(M.UserDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def request_password_recovery(self, identifier: str) -> Result[M.OperationResultDTO, E.XoloError]:
        """Request a password reset email or token.

        Args:
            identifier: Username or email used to identify the user.

        Returns:
            A ``Result`` containing a generic success DTO.
        """
        try:
            payload = M.PasswordRecoveryRequestDTO(identifier=identifier)
            self._request("POST", self._account_url("users/password-recovery"), json=payload.model_dump())
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def confirm_password_recovery(self, token: str, password: str) -> Result[M.OperationResultDTO, E.XoloError]:
        """Confirm a password reset with the recovery token.

        Args:
            token: Password-reset token issued by the server.
            password: New plain-text password.

        Returns:
            A ``Result`` containing a generic success DTO.
        """
        try:
            payload = M.PasswordRecoveryConfirmDTO(token=token, password=password)
            self._request(
                "POST",
                self._account_url("users/password-recovery/confirm"),
                json=payload.model_dump(),
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def change_password(
        self,
        password: str,
        token: str,
        temporal_secret: str,
    ) -> Result[M.UpdateUserPasswordResponseDTO, E.XoloError]:
        """Change the signed-in tenant user's password and revoke their session."""
        try:
            response = self._request(
                "POST",
                self._account_url("users/password"),
                headers=self._bearer_headers(token, temporal_secret),
                json={"password": password},
            )
            return Ok(M.UpdateUserPasswordResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_user_password(
        self,
        username: str,
        password: str,
        secret: str = "",
    ) -> Result[M.UpdateUserPasswordResponseDTO, E.XoloError]:
        """Legacy compatibility wrapper for password recovery confirmation.

        Args:
            username: Legacy field retained for backwards compatibility.
            password: New plain-text password.
            secret: Recovery token. This replaces the former admin secret flow.

        Returns:
            A ``Result`` containing a generic password-update DTO.
        """
        try:
            _ = username
            if not secret.strip():
                raise E.ValidationError(
                    "Password recovery confirmation now requires the reset token in the 'secret' argument."
                )
            result = self.confirm_password_recovery(token=secret, password=password)
            if result.is_err:
                return Err(result.unwrap_err())
            return Ok(M.UpdateUserPasswordResponseDTO(ok=True))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def logout(
        self,
        username: str,
        access_token: str,
        token: str,
        temporal_secret: str,
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        """Log out the current bearer session.

        Args:
            username: Username associated with the session.
            access_token: Access token to revoke.
            token: Bearer token used to authorize the logout request.
            temporal_secret: Temporal secret key for the bearer token.

        Returns:
            A ``Result`` containing a generic success DTO.
        """
        try:
            payload = M.LogoutDTO(username=username, access_token=access_token)
            self._request(
                "POST",
                self._account_url("users/logout"),
                headers=self._bearer_headers(token=token, temporal_secret=temporal_secret),
                json=payload.model_dump(),
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def auth(
        self,
        username: str,
        password: str,
        scope: str,
        expiration: str = "1h",
        renew_token: bool = False,
        api_key: str = "",
    ) -> Result[M.AuthenticatedDTO, E.XoloError]:
        """Authenticate a user against the configured account.

        Args:
            username: Username to authenticate.
            password: Plain-text password.
            scope: Requested scope.
            expiration: Access-token expiration hint.
            renew_token: Whether to renew an existing session token.
            api_key: Optional API-key override for this request.

        Returns:
            A ``Result`` containing the authenticated-session DTO.
        """
        try:
            payload = M.AuthDTO(
                username=username,
                password=password,
                scope=scope,
                expiration=expiration,
                renew_token=renew_token,
            )
            response = self._request(
                "POST",
                self._account_url("users/auth"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.AuthenticatedDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def refresh_token(
        self,
        token: str,
        temporal_secret: str,
        expiration: str = "15min",
    ) -> Result[M.AuthenticatedDTO, E.XoloError]:
        """Refresh the current bearer session, returning a new token pair.

        The old ``access_token`` / ``temporal_secret`` pair is invalidated on
        success; use the values from the returned DTO for subsequent calls.

        Args:
            token: Current valid bearer access token.
            temporal_secret: Temporal secret returned at login.
            expiration: Lifetime of the new token (e.g. ``"15min"``, ``"1h"``,
                ``"2d"``). Defaults to ``"15min"``.

        Returns:
            A ``Result`` containing the new authenticated-session DTO.
        """
        try:
            response = self._request(
                "POST",
                self._account_url("users/refresh"),
                headers=self._bearer_headers(token=token, temporal_secret=temporal_secret),
                json={"expiration": expiration},
            )
            return Ok(M.AuthenticatedDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_current_user(self, token: str, temporal_secret: str) -> Result[M.UserDTO, E.XoloError]:
        """Fetch the authenticated user profile.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.

        Returns:
            A ``Result`` containing the current user DTO.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("users"),
                headers=self._bearer_headers(token=token, temporal_secret=temporal_secret),
            )
            return Ok(M.UserDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_license(
        self,
        username: str,
        scope: str,
        secret: str,
        expires_in: str = "1h",
        force: bool = True,
        admin_token: str = "",
    ) -> Result[M.AssignLicenseResponseDTO, E.XoloError]:
        """Create a license for a user and scope.

        Args:
            username: Username receiving the license.
            scope: Scope name for the license.
            secret: Legacy compatibility field retained for older callers.
            expires_in: Relative expiration string.
            force: Whether to replace an existing license.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the license-assignment DTO.
        """
        try:
            _ = secret
            payload = M.AssignLicenseDTO(
                username=username,
                scope=scope,
                expires_in=expires_in,
                force=force,
            )
            response = self._request(
                "POST",
                self._account_url("licenses"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(exclude_none=True),
            )
            data = self._response_json(response) or {"ok": True}
            return Ok(M.AssignLicenseResponseDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_licenses(self, admin_token: str = "") -> Result[List[M.LicenseDTO], E.XoloError]:
        """List licenses in the configured account.

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the license list.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("licenses"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.LicenseDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_license(
        self,
        username: str,
        scope: str,
        force: bool = True,
        secret: str = "",
        admin_token: str = "",
    ) -> Result[M.DeletedLicenseResponseDTO, E.XoloError]:
        """Delete a user's license.

        Args:
            username: License owner username.
            scope: Scope to revoke.
            force: Whether to force deletion.
            secret: Legacy compatibility field retained for older callers.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the delete-license DTO.
        """
        try:
            _ = secret
            payload = M.DeleteLicenseDTO(username=username, scope=scope, force=force)
            response = self._request(
                "DELETE",
                self._account_url("licenses"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(exclude_none=True),
            )
            data = self._response_json(response) or {"ok": True}
            return Ok(M.DeletedLicenseResponseDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def self_delete_license(
        self,
        username: str,
        scope: str,
        token: str,
        secret: str,
        force: bool = True,
    ) -> Result[M.DeletedLicenseResponseDTO, E.XoloError]:
        """Delete the caller's own license.

        Args:
            username: Username deleting the license.
            scope: Scope to revoke.
            token: Access token to revoke from the license flow.
            secret: Temporal secret key associated with the token.
            force: Whether to force deletion.

        Returns:
            A ``Result`` containing the delete-license DTO.
        """
        try:
            payload = M.SelfDeleteLicenseDTO(
                token=token,
                tmp_secret_key=secret,
                username=username,
                scope=scope,
                force=force,
            )
            response = self._request(
                "DELETE",
                self._account_url("licenses/self"),
                json=payload.model_dump(exclude_none=True),
            )
            data = self._response_json(response) or {"ok": True}
            return Ok(M.DeletedLicenseResponseDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def rotate_license(
        self,
        username: str,
        scope: str,
        expires_in: str,
        admin_token: str = "",
    ) -> Result[M.AssignLicenseResponseDTO, E.XoloError]:
        """Rotate (re-issue) an existing license with a new expiration.

        Args:
            username: License owner username.
            scope: Scope name for the license.
            expires_in: Relative expiration string for the new license.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the updated license-assignment DTO.
        """
        try:
            payload = M.RotateLicenseDTO(username=username, scope=scope, expires_in=expires_in)
            response = self._request(
                "POST",
                self._account_url("licenses/rotate"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            data = self._response_json(response) or {"ok": True}
            return Ok(M.AssignLicenseResponseDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_scope(self, scope: str, secret: str = "", admin_token: str = "") -> Result[M.CreatedScopeResponseDTO, E.XoloError]:
        """Create a scope in the configured account.

        Args:
            scope: Scope name to create.
            secret: Legacy compatibility field retained for older callers.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the created-scope DTO.
        """
        try:
            _ = secret
            payload = M.CreateScopeDTO(name=scope)
            response = self._request(
                "POST",
                self._account_url("scopes"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            data = self._response_json(response) or payload.model_dump()
            return Ok(M.CreatedScopeResponseDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_scopes(self, admin_token: str = "") -> Result[List[M.CreatedScopeResponseDTO], E.XoloError]:
        """List scopes in the configured account.

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the scope list.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("scopes"),
                headers=self._admin_headers(admin_token, required=True),
            )
            items = []
            for item in self._list_json(response):
                if isinstance(item, str):
                    items.append(M.CreatedScopeResponseDTO(name=item))
                else:
                    items.append(M.CreatedScopeResponseDTO.model_validate(item))
            return Ok(items)
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_scope(self, scope: str, admin_token: str = "") -> Result[M.DeletedScopeResponseDTO, E.XoloError]:
        """Delete a scope.

        Args:
            scope: Scope name to delete.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a synthetic delete-scope DTO.
        """
        try:
            payload = M.CreateScopeDTO(name=scope)
            self._request(
                "DELETE",
                self._account_url("scopes"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.DeletedScopeResponseDTO(name=scope.upper()))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def assign_scope(
        self,
        username: str,
        scope: str,
        secret: str,
        admin_token: str = "",
    ) -> Result[M.AssignedScopeResponseDTO, E.XoloError]:
        """Assign a scope to a user.

        Args:
            username: Username receiving the scope.
            scope: Scope name to assign.
            secret: Legacy compatibility field retained for older callers.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the scope-assignment DTO.
        """
        try:
            _ = secret
            payload = M.AssignScopeDTO(username=username, name=scope)
            response = self._request(
                "POST",
                self._account_url("scopes/assign"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            data = self._response_json(response) or {"ok": True, "username": username, "name": scope.upper()}
            return Ok(M.AssignedScopeResponseDTO.model_validate(data))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def unassign_scope(self, username: str, scope: str, admin_token: str = "") -> Result[M.UnassignedScopeResponseDTO, E.XoloError]:
        """Unassign a scope from a user.

        Args:
            username: Username losing the scope.
            scope: Scope name to remove.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a synthetic unassignment DTO.
        """
        try:
            payload = M.AssignScopeDTO(username=username, name=scope)
            self._request(
                "DELETE",
                self._account_url("scopes/assign"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.UnassignedScopeResponseDTO(username=username, name=scope.upper()))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_scope_assignments(self, admin_token: str = "") -> Result[List[M.AssignedScopeResponseDTO], E.XoloError]:
        """List scope assignments for the configured account.

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing assignment DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("scopes/assignments"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.AssignedScopeResponseDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_scopes_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List scopes for discovery/autocomplete (id+name pairs).

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of scope discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("scopes/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_users_resources(
        self,
        token: str,
        temporal_secret: str,
        owned_page: int = 1,
        owned_page_size: int = 10,
        shared_page: int = 1,
        shared_page_size: int = 10,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.UsersResourcesDTO, E.XoloError]:
        """Fetch resources visible to the authenticated user.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            owned_page: Owned-resources page number.
            owned_page_size: Owned-resources page size.
            shared_page: Shared-resources page number.
            shared_page_size: Shared-resources page size.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the resources DTO.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("acl/resources"),
                headers=self._authz_headers(
                    token=token,
                    temporal_secret=temporal_secret,
                    api_key=api_key,
                    admin_token=admin_token,
                ),
                params={
                    "owned_page": owned_page,
                    "owned_page_size": owned_page_size,
                    "shared_page": shared_page,
                    "shared_page_size": shared_page_size,
                },
            )
            return Ok(M.UsersResourcesDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_group(
        self,
        name: str,
        owner_username: str,
        description: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.GroupDTO, E.XoloError]:
        """Create a first-class shared security group.

        Args:
            owner_username: Tenant username that administratively owns the group.
            name: Group name.
            description: Group description.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the created-group DTO.
        """
        try:
            payload = M.CreateGroupDTO(name=name, description=description, owner_username=owner_username)
            response = self._request(
                "POST",
                self._account_url("groups"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.GroupDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_group(
        self,
        group_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.DeletedGroupResponseDTO, E.XoloError]:
        """Delete an ACL group.

        Args:
            group_id: Group identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic group-deletion DTO.
        """
        try:
            self._request(
                "DELETE",
                self._account_url(f"groups/{group_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.DeletedGroupResponseDTO(group_id=group_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def add_members_to_group(
        self,
        group_id: str,
        members: List[str],
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.GroupMembersUpdateResponseDTO, E.XoloError]:
        """Add members to an ACL group.

        Args:
            group_id: Group identifier.
            members: User identifiers to add.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic members-update DTO.
        """
        try:
            payload = M.MembersDTO(members=members)
            self._request(
                "POST",
                self._account_url(f"groups/{group_id}/members"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"usernames": members},
            )
            return Ok(M.GroupMembersUpdateResponseDTO(group_id=group_id, members=members))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_groups(
        self, token: str, temporal_secret: str, search: str = "", page: int = 1,
        page_size: int = 25, api_key: str = "", admin_token: str = "",
    ) -> Result[M.GroupPageDTO, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url("groups"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                params={"search": search, "page": page, "page_size": page_size},
            )
            return Ok(M.GroupPageDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_group(self, group_id: str, token: str, temporal_secret: str, api_key: str = "", admin_token: str = "") -> Result[M.GroupDTO, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url(f"groups/{group_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.GroupDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_group_references(self, api_key: str = "") -> Result[List[M.GroupReferenceDTO], E.XoloError]:
        try:
            response = self._request("GET", self._account_url("groups/references"), headers=self._api_key_headers(api_key, required=True))
            return Ok([M.GroupReferenceDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def transfer_group_owner(self, group_id: str, owner_username: str, token: str, temporal_secret: str, api_key: str = "", admin_token: str = "") -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            self._request(
                "POST", self._account_url(f"groups/{group_id}/owner"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"owner_username": owner_username},
            )
            return Ok(M.OperationResultDTO())
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def set_group_status(self, group_id: str, is_active: bool, token: str, temporal_secret: str, api_key: str = "", admin_token: str = "") -> Result[M.GroupDTO, E.XoloError]:
        try:
            response = self._request(
                "POST", self._account_url(f"groups/{group_id}/status"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"is_active": is_active},
            )
            return Ok(M.GroupDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_group_usage(self, group_id: str, token: str, temporal_secret: str, api_key: str = "", admin_token: str = "") -> Result[M.GroupUsageDTO, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url(f"groups/{group_id}/usage"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.GroupUsageDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_acl_policies(
        self, token: str, temporal_secret: str, search: str = "", page: int = 1,
        page_size: int = 25, api_key: str = "", admin_token: str = "",
    ) -> Result[M.ACLPolicyPageDTO, E.XoloError]:
        """List the complete account resource-policy inventory."""
        try:
            response = self._request(
                "GET", self._account_url("acl/policies"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                params={"search": search, "page": page, "page_size": page_size},
            )
            return Ok(M.ACLPolicyPageDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def inspect_acl_effective_access(
        self, resource_id: str, username: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.ACLEffectiveAccessDTO, E.XoloError]:
        """Explain direct, active-group, ignored-group, and owner ACL access."""
        try:
            response = self._request(
                "GET", self._account_url(f"acl/resources/{resource_id}/effective-access/{username}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.ACLEffectiveAccessDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_acl_deletion_impact(
        self, resource_id: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[Dict, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url(f"acl/resources/{resource_id}/deletion-impact"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(self._response_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def transfer_acl_resource_owner(
        self, resource_id: str, principal_id: str, token: str, temporal_secret: str,
        principal_type: str = "USER", keep_previous_permissions: Optional[List[str]] = None,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            payload = M.TransferResourceOwnerDTO(
                principal_id=principal_id, principal_type=principal_type,
                keep_previous_permissions=keep_previous_permissions,
            )
            self._request(
                "POST", self._account_url(f"acl/resources/{resource_id}/owner"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_acl_resource_policy(
        self, resource_id: str, confirmation: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            self._request(
                "DELETE", self._account_url(f"acl/resources/{resource_id}/policy"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"confirm_resource_id": confirmation},
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_group_members(
        self, group_id: str, token: str, temporal_secret: str, search: str = "",
        page: int = 1, page_size: int = 25, api_key: str = "", admin_token: str = "",
    ) -> Result[M.PaginatedDTO[M.GroupMemberDTO], E.XoloError]:
        """List resolved members of a shared security group."""
        try:
            response = self._request(
                "GET", self._account_url(f"groups/{group_id}/members"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                params={"search": search, "page": page, "page_size": page_size},
            )
            return Ok(M.PaginatedDTO[M.GroupMemberDTO].model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def remove_members_from_group(
        self,
        group_id: str,
        members: List[str],
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.GroupMembersUpdateResponseDTO, E.XoloError]:
        """Remove members from an ACL group.

        Args:
            group_id: Group identifier.
            members: User identifiers to remove.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic members-update DTO.
        """
        try:
            payload = M.MembersDTO(members=members)
            self._request(
                "DELETE",
                self._account_url(f"groups/{group_id}/members"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"usernames": members},
            )
            return Ok(M.GroupMembersUpdateResponseDTO(group_id=group_id, members=members))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def grant_permission(
        self,
        resource_id: str,
        principal_id: str,
        permissions: List[str],
        token: str,
        temporal_secret: str,
        principal_type: str = "USER",
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.PermissionUpdateResponseDTO, E.XoloError]:
        """Grant ACL permissions to a principal.

        Args:
            resource_id: Resource identifier.
            principal_id: User or group identifier.
            permissions: Permissions to grant.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            principal_type: Principal type string.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic permission-update DTO.
        """
        try:
            payload = M.GrantOrRevokeDTO(
                principal_id=principal_id,
                principal_type=principal_type,
                resource_id=resource_id,
                permissions=permissions,
            )
            self._request(
                "POST",
                self._account_url("acl/grant"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(
                M.PermissionUpdateResponseDTO(
                    resource_id=resource_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    permissions=permissions,
                )
            )
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def revoke_permission(
        self,
        resource_id: str,
        principal_id: str,
        permissions: List[str],
        token: str,
        temporal_secret: str,
        principal_type: str = "USER",
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.PermissionUpdateResponseDTO, E.XoloError]:
        """Revoke ACL permissions from a principal.

        Args:
            resource_id: Resource identifier.
            principal_id: User or group identifier.
            permissions: Permissions to revoke.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            principal_type: Principal type string.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic permission-update DTO.
        """
        try:
            payload = M.GrantOrRevokeDTO(
                principal_id=principal_id,
                principal_type=principal_type,
                resource_id=resource_id,
                permissions=permissions,
            )
            self._request(
                "DELETE",
                self._account_url("acl/revoke"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(
                M.PermissionUpdateResponseDTO(
                    resource_id=resource_id,
                    principal_id=principal_id,
                    principal_type=principal_type,
                    permissions=permissions,
                )
            )
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def claim_resource(
        self,
        resource_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.ClaimedResourceResponseDTO, E.XoloError]:
        """Claim ownership of a resource.

        Args:
            resource_id: Resource identifier to claim.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic claim DTO.
        """
        try:
            payload = M.ClaimResourceDTO(resource_id=resource_id)
            self._request(
                "POST",
                self._account_url("acl/claim"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.ClaimedResourceResponseDTO(resource_id=resource_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_create_group(
        self,
        name: str,
        owner_id: str,
        description: str = "",
        api_key: str = "",
    ) -> Result[M.CreatedGroupResponseDTO, E.XoloError]:
        """Create a group with a service key; owner_id accepts a user ID or username."""
        try:
            payload = M.ServiceCreateGroupDTO(name=name, owner_id=owner_id, description=description)
            response = self._request(
                "POST",
                self._account_url("acl/service/groups"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.CreatedGroupResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_add_group_members(
        self,
        group_id: str,
        members: List[str],
        api_key: str = "",
    ) -> Result[M.GroupMembersUpdateResponseDTO, E.XoloError]:
        """Add tenant users by ID or username without borrowing an owner session."""
        try:
            self._request(
                "POST",
                self._account_url(f"acl/service/groups/{group_id}/members"),
                headers=self._api_key_headers(api_key, required=True),
                json=M.MembersDTO(members=members).model_dump(),
            )
            return Ok(M.GroupMembersUpdateResponseDTO(group_id=group_id, members=members))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_remove_group_members(
        self,
        group_id: str,
        members: List[str],
        api_key: str = "",
    ) -> Result[M.GroupMembersUpdateResponseDTO, E.XoloError]:
        """Remove tenant users by ID or username without borrowing an owner session."""
        try:
            self._request(
                "DELETE",
                self._account_url(f"acl/service/groups/{group_id}/members"),
                headers=self._api_key_headers(api_key, required=True),
                json=M.MembersDTO(members=members).model_dump(),
            )
            return Ok(M.GroupMembersUpdateResponseDTO(group_id=group_id, members=members))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_list_group_members(
        self,
        group_id: str,
        api_key: str = "",
    ) -> Result[List[M.GroupMemberDTO], E.XoloError]:
        """List a group's members using a service key."""
        try:
            response = self._request(
                "GET",
                self._account_url(f"acl/service/groups/{group_id}/members"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok([M.GroupMemberDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_transfer_group_owner(
        self,
        group_id: str,
        user_id: str,
        api_key: str = "",
        *,
        keep_previous_as_member: bool = True,
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        """Transfer group ownership to an account user by ID or username."""
        try:
            self._request(
                "POST",
                self._account_url(f"acl/service/groups/{group_id}/owner"),
                headers=self._api_key_headers(api_key, required=True),
                json=M.TransferGroupOwnerDTO(
                    user_id=user_id,
                    keep_previous_as_member=keep_previous_as_member,
                ).model_dump(),
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_delete_group(
        self,
        group_id: str,
        api_key: str = "",
    ) -> Result[M.DeletedGroupResponseDTO, E.XoloError]:
        """Delete an unreferenced group using a service key."""
        try:
            self._request(
                "DELETE",
                self._account_url(f"acl/service/groups/{group_id}"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(M.DeletedGroupResponseDTO(group_id=group_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_claim_resource(
        self,
        resource_id: str,
        owner_id: str,
        owner_type: str = "USER",
        api_key: str = "",
    ) -> Result[M.ClaimedResourceResponseDTO, E.XoloError]:
        """Claim a resource for a user or group using a service-scoped key."""
        try:
            payload = M.ServiceClaimResourceDTO(
                resource_id=resource_id,
                owner_id=owner_id,
                owner_type=owner_type,
            )
            self._request(
                "POST",
                self._account_url("acl/service/claim"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(),
            )
            return Ok(M.ClaimedResourceResponseDTO(resource_id=resource_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_grant_permission(
        self,
        resource_id: str,
        principal_id: str,
        permissions: List[str],
        principal_type: str = "USER",
        api_key: str = "",
    ) -> Result[M.PermissionUpdateResponseDTO, E.XoloError]:
        """Grant resource permissions without a user session."""
        try:
            payload = M.GrantOrRevokeDTO(
                resource_id=resource_id,
                principal_id=principal_id,
                principal_type=principal_type,
                permissions=permissions,
            )
            self._request(
                "POST",
                self._account_url("acl/service/grant"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.PermissionUpdateResponseDTO(
                resource_id=resource_id,
                principal_id=principal_id,
                principal_type=principal_type,
                permissions=permissions,
            ))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_revoke_permission(
        self,
        resource_id: str,
        principal_id: str,
        permissions: List[str],
        principal_type: str = "USER",
        api_key: str = "",
    ) -> Result[M.PermissionUpdateResponseDTO, E.XoloError]:
        """Revoke resource permissions without a user session."""
        try:
            payload = M.GrantOrRevokeDTO(
                resource_id=resource_id,
                principal_id=principal_id,
                principal_type=principal_type,
                permissions=permissions,
            )
            self._request(
                "DELETE",
                self._account_url("acl/service/revoke"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.PermissionUpdateResponseDTO(
                resource_id=resource_id,
                principal_id=principal_id,
                principal_type=principal_type,
                permissions=permissions,
            ))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_get_effective_access(
        self,
        resource_id: str,
        user_id: str,
        api_key: str = "",
    ) -> Result[M.EffectiveAccessDTO, E.XoloError]:
        """Get a user's effective direct and group-derived access."""
        try:
            response = self._request(
                "GET",
                self._account_url(f"acl/service/resources/{resource_id}/users/{user_id}/access"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(M.EffectiveAccessDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_list_resource_grants(
        self,
        resource_id: str,
        api_key: str = "",
    ) -> Result[M.ResourceGrantsDTO, E.XoloError]:
        """List all direct grants attached to a resource."""
        try:
            response = self._request(
                "GET",
                self._account_url(f"acl/service/resources/{resource_id}/grants"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(M.ResourceGrantsDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_get_user_resources(
        self,
        user_id: str,
        owned_page: int = 1,
        owned_page_size: int = 10,
        shared_page: int = 1,
        shared_page_size: int = 10,
        api_key: str = "",
    ) -> Result[M.ServiceUserResourcesDTO, E.XoloError]:
        """List resources visible to a user without using their session."""
        try:
            response = self._request(
                "GET",
                self._account_url(f"acl/service/users/{user_id}/resources"),
                headers=self._api_key_headers(api_key, required=True),
                params={
                    "owned_page": owned_page,
                    "owned_page_size": owned_page_size,
                    "shared_page": shared_page,
                    "shared_page_size": shared_page_size,
                },
            )
            return Ok(M.ServiceUserResourcesDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_transfer_resource_owner(
        self,
        resource_id: str,
        principal_id: str,
        principal_type: str = "USER",
        keep_previous_permissions: Optional[List[str]] = None,
        api_key: str = "",
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        """Transfer resource ownership using a service-scoped key."""
        try:
            payload = M.TransferResourceOwnerDTO(
                principal_id=principal_id,
                principal_type=principal_type,
                keep_previous_permissions=keep_previous_permissions,
            )
            self._request(
                "POST",
                self._account_url(f"acl/service/resources/{resource_id}/owner"),
                headers=self._api_key_headers(api_key, required=True),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def service_delete_resource_policy(
        self,
        resource_id: str,
        api_key: str = "",
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        """Delete a resource policy using a service-scoped key."""
        try:
            self._request(
                "DELETE",
                self._account_url(f"acl/service/resources/{resource_id}"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(M.OperationResultDTO(ok=True))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def check_permission_auth(
        self,
        resource_id: str,
        permissions: List[str],
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.CheckPermissionResponseDTO, E.XoloError]:
        """Check ACL permissions for the authenticated user.

        Args:
            resource_id: Resource identifier.
            permissions: Permissions to verify.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the ACL check DTO.
        """
        try:
            payload = M.CheckDTO(resource_id=resource_id, permissions=permissions)
            response = self._request(
                "POST",
                self._account_url("acl/check"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.CheckPermissionResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))
    def check_permission_group(
        self,
        group_id: str,
        resource_id: str,
        permissions: List[str],
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.CheckPermissionResponseDTO, E.XoloError]:
        """Check ACL permissions for a group.

        Args:
            group_id: Group identifier.
            resource_id: Resource identifier.
            permissions: Permissions to verify.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the ACL check DTO.
        """
        try:
            payload = M.CheckDTO(resource_id=resource_id, permissions=permissions, principal_id=group_id, principal_type="GROUP")
            response = self._request(
                "POST",
                self._account_url("acl/check"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.CheckPermissionResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))
    

    def check_group_membership(
        self,
        group_id: str,
        user_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.GroupMembershipResponseDTO, E.XoloError]:
        """Check whether a user is a member of a group.

        Args:
            group_id: Group identifier.
            user_id: User identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the group membership DTO.
        """
        try:
            page = 1
            is_member = False
            while True:
                response = self._request(
                    "GET",
                    self._account_url(f"groups/{group_id}/members"),
                    headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                    params={"page": page, "page_size": 100},
                )
                payload = self._response_json(response)
                if any(item.get("user_id") == user_id for item in payload.get("items", [])):
                    is_member = True
                    break
                if page >= payload.get("total_pages", 0):
                    break
                page += 1
            return Ok(M.GroupMembershipResponseDTO(group_id=group_id, user_id=user_id, is_member=is_member))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_acl_groups_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List shared groups for ACL discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of group discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("groups/references"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_acl_principals_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List ACL principals for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of principal discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("acl/principals/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_acl_resources_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List ACL resources for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of resource discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("acl/resources/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_api_key(
        self,
        name: str,
        scopes: List[str],
        expires_at: Optional[str] = None,
        admin_token: str = "",
    ) -> Result[M.CreatedAPIKeyResponseDTO, E.XoloError]:
        """Create an account API key.

        Args:
            name: API-key display name.
            scopes: Allowed API scopes.
            expires_at: Optional RFC3339 expiration timestamp.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the one-time API-key creation DTO.
        """
        try:
            payload = M.CreateAPIKeyDTO(name=name, scopes=scopes, expires_at=expires_at)
            response = self._request(
                "POST",
                self._account_url("apikeys"),
                headers=self._admin_headers(admin_token, required=True),
                json=payload.model_dump(exclude_none=True, mode="json"),
            )
            return Ok(M.CreatedAPIKeyResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_api_keys(self, admin_token: str = "") -> Result[List[M.APIKeyMetadataDTO], E.XoloError]:
        """List account API keys.

        Args:
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing API-key metadata DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("apikeys"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.APIKeyMetadataDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_api_key(self, key_id: str, admin_token: str = "") -> Result[M.APIKeyMetadataDTO, E.XoloError]:
        """Fetch metadata for an API key.

        Args:
            key_id: API-key identifier.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing API-key metadata.
        """
        try:
            response = self._request(
                "GET",
                self._account_url(f"apikeys/{key_id}"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.APIKeyMetadataDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_api_key_scopes(self, admin_token: str = "") -> Result[List[M.APIKeyScope], E.XoloError]:
        """List every scope accepted when creating an account API key."""
        try:
            response = self._request(
                "GET",
                self._account_url("apikeys/scopes"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok([M.APIKeyScope(scope) for scope in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_api_key(self, key_id: str, admin_token: str = "") -> Result[M.DeletedAPIKeyResponseDTO, E.XoloError]:
        """Permanently remove a key and its metadata; unlike revoke, it disappears from listings."""
        try:
            self._request(
                "DELETE",
                self._account_url(f"apikeys/{key_id}/permanent"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.DeletedAPIKeyResponseDTO(key_id=key_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def revoke_api_key(self, key_id: str, admin_token: str = "") -> Result[M.RevokedAPIKeyResponseDTO, E.XoloError]:
        """Revoke an API key.

        Args:
            key_id: API-key identifier.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing a synthetic API-key revoke DTO.
        """
        try:
            self._request(
                "DELETE",
                self._account_url(f"apikeys/{key_id}"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.RevokedAPIKeyResponseDTO(key_id=key_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def rotate_api_key(self, key_id: str, admin_token: str = "") -> Result[M.RotatedAPIKeyResponseDTO, E.XoloError]:
        """Rotate an API key.

        Args:
            key_id: API-key identifier.
            admin_token: Optional admin-token override.

        Returns:
            A ``Result`` containing the rotated-key DTO.
        """
        try:
            response = self._request(
                "POST",
                self._account_url(f"apikeys/{key_id}/rotate"),
                headers=self._admin_headers(admin_token, required=True),
            )
            return Ok(M.RotatedAPIKeyResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_abac_policy(
        self,
        name: str,
        effect: str,
        events: List[Dict],
        token: str,
        temporal_secret: str,
        timezone: Optional[str] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.CreatedABACPolicyResponseDTO, E.XoloError]:
        """Create an ABAC policy.

        Args:
            name: Policy display name.
            effect: Policy effect string.
            events: Event definitions for the policy.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the created-policy DTO.
        """
        try:
            payload = M.CreateABACPolicyDTO(name=name, effect=effect, events=events, timezone=timezone)
            response = self._request(
                "POST",
                self._account_url("abac/policies"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.CreatedABACPolicyResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_abac_policies(
        self,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[List[M.ABACPolicyDTO], E.XoloError]:
        """List ABAC policies.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing ABAC policy DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("abac/policies"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok([M.ABACPolicyDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_abac_policy(
        self,
        policy_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.ABACPolicyDTO, E.XoloError]:
        """Fetch an ABAC policy by identifier.

        Args:
            policy_id: Policy identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the ABAC policy DTO.
        """
        try:
            response = self._request(
                "GET",
                self._account_url(f"abac/policies/{policy_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.ABACPolicyDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_abac_policy(
        self,
        policy_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.DeletedABACPolicyResponseDTO, E.XoloError]:
        """Delete an ABAC policy.

        Args:
            policy_id: Policy identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic delete-policy DTO.
        """
        try:
            self._request(
                "DELETE",
                self._account_url(f"abac/policies/{policy_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.DeletedABACPolicyResponseDTO(policy_id=policy_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def evaluate_abac(
        self,
        subject: str,
        resource: str,
        action: str,
        token: str,
        temporal_secret: str,
        location: Optional[M.GeoPointDTO] = None,
        time: Optional[str] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.ABACDecisionDTO, E.XoloError]:
        """Evaluate an ABAC access request.

        Args:
            subject: Subject identifier.
            resource: Resource identifier.
            action: Action being evaluated.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            location: Optional geo-point for location-aware evaluation; None = wildcard pass.
            time: Optional ISO-8601 datetime string; None = wildcard pass.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the ABAC decision DTO.
        """
        try:
            payload = M.ABACEvaluateDTO(
                subject=subject,
                resource=resource,
                location=location,
                time=time,
                action=action,
            )
            response = self._request(
                "POST",
                self._account_url("abac/evaluate"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.ABACDecisionDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def upgrade_abac_matcher(
        self, policy_id: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.ABACPolicyDTO, E.XoloError]:
        try:
            response = self._request(
                "POST", self._account_url(f"abac/policies/{policy_id}/upgrade-matcher"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.ABACPolicyDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_abac_policies_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List ABAC policies for discovery/autocomplete (id+name pairs).

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of policy discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("abac/policies/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_abac_subjects_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List ABAC subjects for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of subject discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("abac/subjects/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_abac_resources_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List ABAC resources for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of resource discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("abac/resources/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_abac_locations_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List ABAC locations for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of location discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("abac/locations/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_ngac_node(
        self,
        name: str,
        node_type: str,
        token: str,
        temporal_secret: str,
        properties: Optional[Dict] = None,
        user_id: Optional[str] = None,
        user_identifier: Optional[str] = None,
        resource_id: Optional[str] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.CreatedNGACNodeResponseDTO, E.XoloError]:
        """Create an NGAC node.

        Args:
            name: Node display name.
            node_type: Node type enum value.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            properties: Optional node properties.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the created-node DTO.
        """
        try:
            payload = M.CreateNGACNodeDTO(
                name=name, node_type=node_type, properties=properties or {},
                user_id=user_id, user_identifier=user_identifier, resource_id=resource_id,
            )
            response = self._request(
                "POST",
                self._account_url("ngac/nodes"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.CreatedNGACNodeResponseDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_ngac_nodes(
        self,
        token: str,
        temporal_secret: str,
        node_type: Optional[str] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[List[M.NGACNodeDTO], E.XoloError]:
        """List NGAC nodes.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            node_type: Optional node-type filter.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing NGAC node DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("ngac/nodes"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                params={"node_type": node_type} if node_type else None,
            )
            return Ok([M.NGACNodeDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_ngac_node(
        self,
        node_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.NGACNodeDTO, E.XoloError]:
        """Fetch an NGAC node by identifier.

        Args:
            node_id: Node identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the NGAC node DTO.
        """
        try:
            response = self._request(
                "GET",
                self._account_url(f"ngac/nodes/{node_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.NGACNodeDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_ngac_node(
        self, node_id: str, token: str, temporal_secret: str, *,
        name: Optional[str] = None, properties: Optional[Dict] = None,
        user_id: Optional[str] = None, user_identifier: Optional[str] = None,
        resource_id: Optional[str] = None, unbind_user: bool = False,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.NGACNodeDTO, E.XoloError]:
        """Update an NGAC node and its optional first-class binding."""
        try:
            payload = {
                key: value for key, value in {
                    "name": name, "properties": properties,
                    "user_id": user_id, "user_identifier": user_identifier, "resource_id": resource_id,
                }.items() if value is not None
            }
            if unbind_user:
                payload["user_identifier"] = None
            response = self._request(
                "PATCH", self._account_url(f"ngac/nodes/{node_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload,
            )
            return Ok(M.NGACNodeDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_ngac_node(
        self,
        node_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.DeletedNGACNodeResponseDTO, E.XoloError]:
        """Delete an NGAC node.

        Args:
            node_id: Node identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic delete-node DTO.
        """
        try:
            self._request(
                "DELETE",
                self._account_url(f"ngac/nodes/{node_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.DeletedNGACNodeResponseDTO(node_id=node_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def ngac_assign(
        self,
        from_id: str,
        to_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.NGACAssignmentMutationResponseDTO, E.XoloError]:
        """Create an NGAC assignment.

        Args:
            from_id: Child node identifier.
            to_id: Parent node identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic assignment DTO.
        """
        try:
            payload = M.NGACAssignDTO(from_id=from_id, to_id=to_id)
            self._request(
                "POST",
                self._account_url("ngac/assign"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.NGACAssignmentMutationResponseDTO(from_id=from_id, to_id=to_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def ngac_remove_assignment(
        self,
        from_id: str,
        to_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.NGACAssignmentMutationResponseDTO, E.XoloError]:
        """Remove an NGAC assignment.

        Args:
            from_id: Child node identifier.
            to_id: Parent node identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic assignment DTO.
        """
        try:
            payload = M.RemoveAssignmentDTO(from_id=from_id, to_id=to_id)
            self._request(
                "DELETE",
                self._account_url("ngac/assign"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.NGACAssignmentMutationResponseDTO(from_id=from_id, to_id=to_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_ngac_assignments(
        self,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[List[M.NGACAssignmentDTO], E.XoloError]:
        """List NGAC assignments.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing assignment DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("ngac/assignments"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok([M.NGACAssignmentDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def ngac_associate(
        self,
        user_attribute_id: str,
        object_attribute_id: str,
        operations: List[str],
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.NGACAssociationMutationResponseDTO, E.XoloError]:
        """Create an NGAC association.

        Args:
            user_attribute_id: User-attribute node identifier.
            object_attribute_id: Object-attribute node identifier.
            operations: Allowed operations.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic association DTO.
        """
        try:
            payload = M.NGACAssociateDTO(
                user_attribute_id=user_attribute_id,
                object_attribute_id=object_attribute_id,
                operations=operations,
            )
            self._request(
                "POST",
                self._account_url("ngac/associate"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(
                M.NGACAssociationMutationResponseDTO(
                    user_attribute_id=user_attribute_id,
                    object_attribute_id=object_attribute_id,
                    operations=operations,
                )
            )
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def ngac_remove_association(
        self,
        association_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.NGACAssociationDeletionResponseDTO, E.XoloError]:
        """Delete an NGAC association.

        Args:
            association_id: Association identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic delete-association DTO.
        """
        try:
            self._request(
                "DELETE",
                self._account_url(f"ngac/associate/{association_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.NGACAssociationDeletionResponseDTO(association_id=association_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_ngac_associations(
        self,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[List[M.NGACAssociationDTO], E.XoloError]:
        """List NGAC associations.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing association DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("ngac/associations"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok([M.NGACAssociationDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def ngac_check(
        self,
        user_id: str,
        object_id: str,
        operation: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.NGACDecisionDTO, E.XoloError]:
        """Evaluate NGAC access.

        Args:
            user_id: User node identifier.
            object_id: Object node identifier.
            operation: Requested operation.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the NGAC decision DTO.
        """
        try:
            payload = M.NGACCheckAccessDTO(user_id=user_id, object_id=object_id, operation=operation)
            response = self._request(
                "POST",
                self._account_url("ngac/check"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.NGACDecisionDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_ngac_graph(
        self, token: str, temporal_secret: str, api_key: str = "", admin_token: str = "",
    ) -> Result[M.NGACGraphDTO, E.XoloError]:
        """Return the resolved graph with node and relationship names."""
        try:
            response = self._request(
                "GET", self._account_url("ngac/graph"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.NGACGraphDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_ngac_node_deletion_impact(
        self, node_id: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.NGACDeletionImpactDTO, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url(f"ngac/nodes/{node_id}/deletion-impact"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.NGACDeletionImpactDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_ngac_association(
        self, association_id: str, operations: List[str], token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.NGACAssociationDTO, E.XoloError]:
        try:
            response = self._request(
                "PATCH", self._account_url(f"ngac/associations/{association_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"operations": operations},
            )
            return Ok(M.NGACAssociationDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_ngac_nodes_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List NGAC nodes for discovery/autocomplete (id+name pairs).

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of node discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("ngac/nodes/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_ngac_assignments_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List NGAC assignments for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of assignment discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("ngac/assignments/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_ngac_associations_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List NGAC associations for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of association discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("ngac/associations/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_role(
        self,
        name: str,
        token: str,
        temporal_secret: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Create an RBAC role.

        Args:
            name: Role display name.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            description: Optional role description.
            permissions: Optional initial permission list.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the role DTO.
        """
        try:
            payload = M.CreateRoleDTO(name=name, description=description, permissions=permissions or [])
            response = self._request(
                "POST",
                self._account_url("rbac/roles"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_roles(
        self,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[List[M.RoleDTO], E.XoloError]:
        """List RBAC roles.

        Args:
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing role DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("rbac/roles"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok([M.RoleDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_role(
        self,
        role_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Fetch an RBAC role by identifier.

        Args:
            role_id: Role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the role DTO.
        """
        try:
            response = self._request(
                "GET",
                self._account_url(f"rbac/roles/{role_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_role(
        self,
        role_id: str,
        token: str,
        temporal_secret: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Update an RBAC role.

        Args:
            role_id: Role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            name: Optional replacement name.
            description: Optional replacement description.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the updated role DTO.
        """
        try:
            payload = M.UpdateRoleDTO(name=name, description=description)
            response = self._request(
                "PATCH",
                self._account_url(f"rbac/roles/{role_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_role(
        self,
        role_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.DeletedRoleResponseDTO, E.XoloError]:
        """Delete an RBAC role.

        Args:
            role_id: Role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic delete-role DTO.
        """
        try:
            self._request(
                "DELETE",
                self._account_url(f"rbac/roles/{role_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.DeletedRoleResponseDTO(role_id=role_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def add_role_permission(
        self,
        role_id: str,
        permission: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Add a permission to a role.

        Args:
            role_id: Role identifier.
            permission: Permission string to add.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the updated role DTO.
        """
        try:
            payload = M.PermissionDTO(permission=permission)
            response = self._request(
                "POST",
                self._account_url(f"rbac/roles/{role_id}/permissions"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def remove_role_permission(
        self,
        role_id: str,
        permission: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Remove a permission from a role.

        Args:
            role_id: Role identifier.
            permission: Permission string to remove.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the updated role DTO.
        """
        try:
            payload = M.PermissionDTO(permission=permission)
            response = self._request(
                "DELETE",
                self._account_url(f"rbac/roles/{role_id}/permissions"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def add_role_parent(
        self,
        role_id: str,
        parent_role_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Add a parent role.

        Args:
            role_id: Child role identifier.
            parent_role_id: Parent role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the updated role DTO.
        """
        try:
            payload = M.ParentRoleDTO(parent_role_id=parent_role_id)
            response = self._request(
                "POST",
                self._account_url(f"rbac/roles/{role_id}/parents"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def remove_role_parent(
        self,
        role_id: str,
        parent_role_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RoleDTO, E.XoloError]:
        """Remove a parent role.

        Args:
            role_id: Child role identifier.
            parent_role_id: Parent role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the updated role DTO.
        """
        try:
            payload = M.ParentRoleDTO(parent_role_id=parent_role_id)
            response = self._request(
                "DELETE",
                self._account_url(f"rbac/roles/{role_id}/parents"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.RoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def assign_role(
        self,
        subject_id: str,
        role_id: str,
        token: str,
        temporal_secret: str,
        subject_type: str = "user",
        subject_username: Optional[str] = None,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.AssignmentDTO, E.XoloError]:
        """Assign a role to a subject.

        Args:
            subject_id: Subject identifier.
            role_id: Role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            subject_type: Subject type, either ``"user"`` or ``"group"``.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the assignment DTO.
        """
        try:
            payload = M.AssignRoleDTO(
                subject_id=subject_id, subject_username=subject_username,
                role_id=role_id, subject_type=subject_type,
            )
            response = self._request(
                "POST",
                self._account_url("rbac/assignments"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.AssignmentDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def unassign_role(
        self,
        subject_id: str,
        role_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.UnassignedRoleResponseDTO, E.XoloError]:
        """Unassign a role from a subject.

        Args:
            subject_id: Subject identifier.
            role_id: Role identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing a synthetic unassignment DTO.
        """
        try:
            payload = M.UnassignRoleDTO(subject_id=subject_id, role_id=role_id)
            self._request(
                "DELETE",
                self._account_url("rbac/assignments"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.UnassignedRoleResponseDTO(subject_id=subject_id, role_id=role_id))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_subject_roles(
        self,
        subject_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[List[M.RoleDTO], E.XoloError]:
        """List roles assigned to a subject.

        Args:
            subject_id: Subject identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing role DTOs.
        """
        try:
            response = self._request(
                "GET",
                self._account_url(f"rbac/subjects/{subject_id}/roles"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok([M.RoleDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def check_rbac_permission(
        self,
        subject_id: str,
        permission: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.RBACCheckResultDTO, E.XoloError]:
        """Check an RBAC permission for a subject.

        Args:
            subject_id: Subject identifier.
            permission: Permission string to verify.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the RBAC check DTO.
        """
        try:
            payload = M.RBACCheckPermissionDTO(subject_id=subject_id, permission=permission)
            response = self._request(
                "POST",
                self._account_url("rbac/check"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(),
            )
            return Ok(M.RBACCheckResultDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_effective_permissions(
        self,
        subject_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.EffectivePermissionsDTO, E.XoloError]:
        """Get effective permissions for a subject.

        Args:
            subject_id: Subject identifier.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the effective-permissions DTO.
        """
        try:
            response = self._request(
                "GET",
                self._account_url(f"rbac/subjects/{subject_id}/permissions"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.EffectivePermissionsDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def has_role(
        self,
        subject_id: str,
        role_id: str,
        token: str,
        temporal_secret: str,
        api_key: str = "",
        admin_token: str = "",
    ) -> Result[M.HasRoleDTO, E.XoloError]:
        """Check whether a subject has a specific role (includes group-inherited roles).

        Args:
            subject_id: Subject identifier.
            role_id: Role identifier to check.
            token: Bearer access token.
            temporal_secret: Temporal secret key.
            api_key: Optional API-key override for this request.
            admin_token: Optional admin-token override for this request.

        Returns:
            A ``Result`` containing the has-role DTO.
        """
        try:
            response = self._request(
                "POST",
                self._account_url("rbac/has-role"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"subject_id": subject_id, "role_id": role_id},
            )
            return Ok(M.HasRoleDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_rbac_roles_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List RBAC roles for discovery/autocomplete (id+name pairs).

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of role discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("rbac/roles/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_rbac_permissions_discovery(self, api_key: str = "") -> Result[List[Dict], E.XoloError]:
        """List RBAC permissions for discovery/autocomplete.

        Args:
            api_key: Optional API-key override.

        Returns:
            A ``Result`` containing a list of permission discovery dicts.
        """
        try:
            response = self._request(
                "GET",
                self._account_url("rbac/permissions/list"),
                headers=self._api_key_headers(api_key, required=True),
            )
            return Ok(self._list_json(response))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_role_assignments(
        self, token: str, temporal_secret: str, subject_type: Optional[str] = None,
        subject_id: Optional[str] = None, role_id: Optional[str] = None,
        api_key: str = "", admin_token: str = "",
    ) -> Result[List[M.AssignmentDTO], E.XoloError]:
        try:
            params = {key: value for key, value in {
                "subject_type": subject_type, "subject_id": subject_id, "role_id": role_id,
            }.items() if value is not None}
            response = self._request(
                "GET", self._account_url("rbac/assignments"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                params=params,
            )
            return Ok([M.AssignmentDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def delete_role_assignment(
        self, assignment_id: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            self._request(
                "DELETE", self._account_url(f"rbac/assignments/{assignment_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.OperationResultDTO())
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def query_authorization_audit(
        self, api_key: str = "", cursor: Optional[str] = None, limit: int = 50,
        models: Optional[List[str]] = None, action: Optional[str] = None,
        actor: Optional[str] = None, target: Optional[str] = None,
    ) -> Result[M.AuthorizationAuditPageDTO, E.XoloError]:
        try:
            params: list[tuple[str, object]] = [("limit", limit)]
            if cursor:
                params.append(("cursor", cursor))
            for model in models or []:
                params.append(("model", model))
            for key, value in (("action", action), ("actor", actor), ("target", target)):
                if value:
                    params.append((key, value))
            response = self._request(
                "GET", self._account_url("authorization/audit"),
                headers=self._api_key_headers(api_key, required=True), params=params,
            )
            return Ok(M.AuthorizationAuditPageDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def search_user_references(self, search: str, limit: int = 3, api_key: str = "") -> Result[List[M.UserReferenceDTO], E.XoloError]:
        """Search account users using the shared ranked autocomplete contract."""
        try:
            response = self._request(
                "GET", self._account_url("users/references"),
                headers=self._api_key_headers(api_key, required=True),
                params={"search": search, "limit": limit},
            )
            return Ok([M.UserReferenceDTO.model_validate(item) for item in self._list_json(response)])
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def create_acl_resource(
        self, resource_id: str, owner_type: str, owner_identifier: str,
        token: str, temporal_secret: str, api_key: str = "", admin_token: str = "",
    ) -> Result[M.ResourceGrantsDTO, E.XoloError]:
        try:
            response = self._request(
                "POST", self._account_url("acl/resources"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"resource_id": resource_id, "owner_type": owner_type, "owner_identifier": owner_identifier},
            )
            return Ok(M.ResourceGrantsDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def revoke_acl_grant(
        self, resource_id: str, grant_id: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            self._request(
                "DELETE", self._account_url(f"acl/resources/{resource_id}/grants/{grant_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.OperationResultDTO())
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_acl_grant(
        self, resource_id: str, grant_id: str, permissions: List[str],
        token: str, temporal_secret: str, api_key: str = "", admin_token: str = "",
    ) -> Result[M.ResourceGrantDTO, E.XoloError]:
        """Replace the permission set of an existing non-owner ACL grant."""
        try:
            payload = M.UpdateACLGrantDTO(permissions=permissions)
            response = self._request(
                "PATCH", self._account_url(f"acl/resources/{resource_id}/grants/{grant_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(mode="json"),
            )
            return Ok(M.ResourceGrantDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def list_abac_timezones(self, token: str, temporal_secret: str, api_key: str = "", admin_token: str = "") -> Result[M.TimezoneCatalogDTO, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url("abac/timezones"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
            )
            return Ok(M.TimezoneCatalogDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def update_role_assignment(
        self, assignment_id: str, role_id: str, subject_type: str,
        token: str, temporal_secret: str, user_identifier: Optional[str] = None,
        subject_id: Optional[str] = None, api_key: str = "", admin_token: str = "",
    ) -> Result[M.AssignmentDTO, E.XoloError]:
        try:
            payload = M.UpdateAssignmentDTO(
                role_id=role_id, subject_type=subject_type,
                user_identifier=user_identifier, subject_id=subject_id,
            )
            response = self._request(
                "PATCH", self._account_url(f"rbac/assignments/{assignment_id}"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json=payload.model_dump(exclude_none=True),
            )
            return Ok(M.AssignmentDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    @staticmethod
    def _platform_headers(platform_session: str, csrf_token: str = "") -> Dict[str, str]:
        headers = {"Cookie": f"xolo_platform_session={platform_session}"}
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
            headers["Cookie"] += f"; xolo_platform_csrf={csrf_token}"
        return headers

    def list_notifications(
        self, platform_session: str, *, categories: Optional[List[str]] = None,
        unread_only: bool = False, cursor: Optional[str] = None, limit: int = 30,
    ) -> Result[M.NotificationPageDTO, E.XoloError]:
        try:
            params: list[tuple[str, object]] = [("limit", limit), ("unread_only", unread_only)]
            if cursor: params.append(("cursor", cursor))
            for category in categories or []: params.append(("category", category))
            response = self._request("GET", self._account_url("notifications"), headers=self._platform_headers(platform_session), params=params)
            return Ok(M.NotificationPageDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_notification_unread_count(self, platform_session: str) -> Result[int, E.XoloError]:
        try:
            response = self._request("GET", self._account_url("notifications/unread-count"), headers=self._platform_headers(platform_session))
            return Ok(int(self._response_json(response)["count"]))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def mark_notification_read(self, notification_id: str, platform_session: str, csrf_token: str) -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            self._request("POST", self._account_url(f"notifications/{notification_id}/read"), headers=self._platform_headers(platform_session, csrf_token))
            return Ok(M.OperationResultDTO())
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def mark_all_notifications_read(self, platform_session: str, csrf_token: str) -> Result[M.OperationResultDTO, E.XoloError]:
        try:
            self._request("POST", self._account_url("notifications/read-all"), headers=self._platform_headers(platform_session, csrf_token))
            return Ok(M.OperationResultDTO())
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def assign_role_to_identifier(
        self, user_identifier: str, role_id: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.AssignmentDTO, E.XoloError]:
        try:
            response = self._request(
                "POST", self._account_url("rbac/assignments"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                json={"user_identifier": user_identifier, "role_id": role_id, "subject_type": "USER"},
            )
            return Ok(M.AssignmentDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))

    def get_effective_permissions_for_identifier(
        self, user_identifier: str, token: str, temporal_secret: str,
        api_key: str = "", admin_token: str = "",
    ) -> Result[M.EffectivePermissionsDTO, E.XoloError]:
        try:
            response = self._request(
                "GET", self._account_url("rbac/effective"),
                headers=self._authz_headers(token, temporal_secret, api_key=api_key, admin_token=admin_token),
                params={"user_identifier": user_identifier},
            )
            return Ok(M.EffectivePermissionsDTO.model_validate(self._response_json(response)))
        except R.exceptions.HTTPError as http_err:
            return Err(self.__process_exception(http_err))
        except Exception as e:
            return Err(E.XoloError.from_exception(e))
