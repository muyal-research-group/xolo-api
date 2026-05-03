from html import escape
from urllib.parse import quote

import xoloapi.config as Cfg


def build_password_reset_url(reset_token: str) -> str | None:
    if not Cfg.XOLO_PASSWORD_RESET_URL_BASE:
        return None
    separator = "&" if "?" in Cfg.XOLO_PASSWORD_RESET_URL_BASE else "?"
    return f"{Cfg.XOLO_PASSWORD_RESET_URL_BASE}{separator}token={quote(reset_token)}"


def build_password_reset_content(
    *,
    recipient_name: str,
    reset_token: str,
    reset_url: str | None,
    expires_in: str,
) -> dict[str, str]:
    final_reset_url = reset_url or build_password_reset_url(reset_token)
    text_lines = [
        f"Hello {recipient_name},",
        "",
        "We received a request to reset your Xolo password.",
        f"This token expires in {expires_in}.",
        "",
        f"Reset token: {reset_token}",
    ]
    html_parts = [
        f"<p>Hello {escape(recipient_name)},</p>",
        "<p>We received a request to reset your Xolo password.</p>",
        f"<p>This token expires in <strong>{escape(expires_in)}</strong>.</p>",
        f"<p><strong>Reset token:</strong> {escape(reset_token)}</p>",
    ]
    if final_reset_url:
        text_lines.extend(["", f"Reset link: {final_reset_url}"])
        html_parts.append(f'<p><a href="{escape(final_reset_url, quote=True)}">Reset your password</a></p>')
    text_lines.extend(["", "If you did not request this change, you can ignore this message."])
    html_parts.append("<p>If you did not request this change, you can ignore this message.</p>")
    return {
        "subject": Cfg.XOLO_PASSWORD_RESET_MAIL_SUBJECT,
        "text": "\n".join(text_lines),
        "html": "".join(html_parts),
    }


def build_welcome_content(
    *,
    recipient_name: str,
    username: str,
    scope: str,
) -> dict[str, str]:
    return {
        "subject": Cfg.XOLO_WELCOME_MAIL_SUBJECT,
        "text": "\n".join(
            [
                f"Hello {recipient_name},",
                "",
                "Welcome to Xolo.",
                f"Your account {username} is ready to use with scope {scope}.",
            ]
        ),
        "html": "".join(
            [
                f"<p>Hello {escape(recipient_name)},</p>",
                "<p>Welcome to Xolo.</p>",
                f"<p>Your account <strong>{escape(username)}</strong> is ready to use with scope <strong>{escape(scope)}</strong>.</p>",
            ]
        ),
    }
