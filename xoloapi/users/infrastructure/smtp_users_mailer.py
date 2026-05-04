import asyncio
import smtplib
from email.message import EmailMessage

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


class SMTPUsersMailer(IUsersMailer):
    def _send_sync(self, message: EmailMessage) -> None:
        if not Cfg.XOLO_SMTP_HOST:
            raise RuntimeError("XOLO_SMTP_HOST is not configured")
        if not Cfg.XOLO_MAIL_SENDER_ADDRESS:
            raise RuntimeError("XOLO_MAIL_SENDER_ADDRESS is not configured")
        if Cfg.XOLO_SMTP_USE_SSL:
            with smtplib.SMTP_SSL(Cfg.XOLO_SMTP_HOST, Cfg.XOLO_SMTP_PORT) as smtp:
                if Cfg.XOLO_SMTP_USERNAME:
                    smtp.login(Cfg.XOLO_SMTP_USERNAME, Cfg.XOLO_SMTP_PASSWORD)
                smtp.send_message(message)
            return

        with smtplib.SMTP(Cfg.XOLO_SMTP_HOST, Cfg.XOLO_SMTP_PORT) as smtp:
            if Cfg.XOLO_SMTP_USE_TLS:
                smtp.starttls()
            if Cfg.XOLO_SMTP_USERNAME:
                smtp.login(Cfg.XOLO_SMTP_USERNAME, Cfg.XOLO_SMTP_PASSWORD)
            smtp.send_message(message)

    async def _send_message(self, *, recipient_email: str, action: str, content: dict[str, str]):
        try:
            message = EmailMessage()
            message["Subject"] = content["subject"]
            message["From"] = f"{Cfg.XOLO_MAIL_SENDER_NAME} <{Cfg.XOLO_MAIL_SENDER_ADDRESS}>"
            message["To"] = recipient_email
            message.set_content(content["text"])
            message.add_alternative(content["html"], subtype="html")
            await asyncio.to_thread(self._send_sync, message)
            return Ok(True)
        except Exception as e:
            log.error(build_log_payload(f"users.mail.smtp.{action}.error", error=e, recipient_email=recipient_email))
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
