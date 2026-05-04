import asyncio

import requests
from option import Err, Ok
from xolo.log import Log

import commonx.errors as EX
import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload
from xoloapi.users.domain.services import IUsersMailer
from xoloapi.users.infrastructure.mail_content import build_password_reset_content, build_welcome_content

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class CloudflareUsersMailer(IUsersMailer):
    def _send_sync(self, payload: dict[str, str]) -> None:
        if not Cfg.XOLO_CLOUDFLARE_ACCOUNT_ID:
            raise RuntimeError("XOLO_CLOUDFLARE_ACCOUNT_ID is not configured")
        if not Cfg.XOLO_CLOUDFLARE_EMAIL_API_TOKEN:
            raise RuntimeError("XOLO_CLOUDFLARE_EMAIL_API_TOKEN is not configured")
        if not Cfg.XOLO_MAIL_SENDER_ADDRESS:
            raise RuntimeError("XOLO_MAIL_SENDER_ADDRESS is not configured")
        response = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{Cfg.XOLO_CLOUDFLARE_ACCOUNT_ID}/email/sending/send",
            headers={
                "Authorization": f"Bearer {Cfg.XOLO_CLOUDFLARE_EMAIL_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("success", False):
            raise RuntimeError(str(data.get("errors") or data))

    async def _send_message(self, *, recipient_email: str, action: str, content: dict[str, str]):
        try:
            await asyncio.to_thread(
                self._send_sync,
                {
                    "to": recipient_email,
                    "from": Cfg.XOLO_MAIL_SENDER_ADDRESS,
                    "subject": content["subject"],
                    "html": content["html"],
                    "text": content["text"],
                },
            )
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload(f"users.mail.cloudflare.{action}.error", error=e, recipient_email=recipient_email))
            return Err(EX.ServerError(raw_detail=str(e)))

    async def send_password_reset_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        reset_token: str,
        reset_url: str | None,
        expires_in: str,
    ):
        return await self._send_message(
            recipient_email=recipient_email,
            action="password_reset",
            content=build_password_reset_content(
                recipient_name=recipient_name,
                reset_token=reset_token,
                reset_url=reset_url,
                expires_in=expires_in,
            ),
        )

    async def send_welcome_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        username: str,
        scope: str,
    ):
        return await self._send_message(
            recipient_email=recipient_email,
            action="welcome",
            content=build_welcome_content(
                recipient_name=recipient_name,
                username=username,
                scope=scope,
            ),
        )
