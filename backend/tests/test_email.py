"""Отправка писем: Mailpit на стенде и внешний почтовый сервер со STARTTLS и логином (публичный стенд, deploy/)."""
from app.core import email
from app.core.config import settings


class FakeSMTP:
    calls: list = []

    def __init__(self, host, port, timeout):
        FakeSMTP.calls.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        FakeSMTP.calls.append(("starttls",))

    def login(self, user, password):
        FakeSMTP.calls.append(("login", user, password))

    def send_message(self, msg):
        FakeSMTP.calls.append(("send", msg["To"], msg["Subject"]))


def test_send_email_external_smtp_with_starttls_and_login(monkeypatch):
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.ru")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_user", "noreply@example.ru")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    FakeSMTP.calls = []
    assert email.send_email("user@mail.ru", "Код подтверждения", "123456")
    assert FakeSMTP.calls == [("connect", "smtp.example.ru", 587), ("starttls",), ("login", "noreply@example.ru", "secret"),
                              ("send", "user@mail.ru", "Код подтверждения")]

    monkeypatch.setattr(settings, "smtp_starttls", False)  # Mailpit: без TLS и логина
    monkeypatch.setattr(settings, "smtp_user", "")
    FakeSMTP.calls = []
    assert email.send_email("user@mail.ru", "Тема", "Текст")
    assert [c[0] for c in FakeSMTP.calls] == ["connect", "send"]
