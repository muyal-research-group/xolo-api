import pytest
from fastapi import HTTPException

import xoloapi.config as Cfg
from xoloapi.users.dependencies import get_users_mailer
from xoloapi.users.infrastructure.cloudflare_users_mailer import CloudflareUsersMailer
from xoloapi.users.infrastructure.noop_users_mailer import NoOpUsersMailer
from xoloapi.users.infrastructure.smtp_users_mailer import SMTPUsersMailer


def test_get_users_mailer_selects_noop(monkeypatch):
    monkeypatch.setattr(Cfg, "XOLO_EMAIL_PROVIDER", "noop")
    assert isinstance(get_users_mailer(), NoOpUsersMailer)


def test_get_users_mailer_selects_smtp(monkeypatch):
    monkeypatch.setattr(Cfg, "XOLO_EMAIL_PROVIDER", "smtp")
    assert isinstance(get_users_mailer(), SMTPUsersMailer)


def test_get_users_mailer_selects_cloudflare(monkeypatch):
    monkeypatch.setattr(Cfg, "XOLO_EMAIL_PROVIDER", "cloudflare")
    assert isinstance(get_users_mailer(), CloudflareUsersMailer)


def test_get_users_mailer_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(Cfg, "XOLO_EMAIL_PROVIDER", "broken")
    with pytest.raises(HTTPException):
        get_users_mailer()
