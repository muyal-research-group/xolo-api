from option import Ok
from xolo.log import Log

import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload
from xoloapi.users.domain.services import IUsersMailer

log = Log(
    name=__name__,
    console_handler_filter=lambda x: True,
    interval=Cfg.XOLO_LOG_INTERVAL,
    when=Cfg.XOLO_LOG_WHEN,
    path=Cfg.XOLO_LOG_PATH,
)


class NoOpUsersMailer(IUsersMailer):
    async def send_password_reset_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        reset_token: str,
        reset_url: str | None,
        expires_in: str,
    ):
        log.info(
            build_log_payload(
                "users.mail.noop.password_reset",
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                has_reset_url=bool(reset_url),
                expires_in=expires_in,
            )
        )
        return Ok(True)

    async def send_welcome_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        username: str,
        scope: str,
    ):
        log.info(
            build_log_payload(
                "users.mail.noop.welcome",
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                username=username,
                scope_name=scope,
            )
        )
        return Ok(True)
