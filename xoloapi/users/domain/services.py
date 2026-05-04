from typing import Protocol

from option import Result

import commonx.errors as EX


class IUsersMailer(Protocol):
    async def send_password_reset_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        reset_token: str,
        reset_url: str | None,
        expires_in: str,
    ) -> Result[bool, EX.XError]: ...

    async def send_welcome_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        username: str,
        scope: str,
    ) -> Result[bool, EX.XError]: ...


IPasswordResetMailer = IUsersMailer
