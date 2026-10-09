"""Отправка писем. В docker-compose письма уходят в Mailpit (веб-интерфейс http://localhost:8025), без SMTP — пишутся
в лог (удобно для локального запуска); внешний почтовый сервер — с STARTTLS и логином (SMTP_STARTTLS, SMTP_USER)."""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("email")


def send_email(to: str, subject: str, body: str) -> bool:
    if to.lower().endswith(".example"):  # служебные адреса демо-гостей и синтетических кандидатов (RFC 2606)
        return False
    if not settings.smtp_host:
        log.warning("EMAIL (dev) to=%s subject=%s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
            if settings.smtp_starttls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)
        return True
    except OSError as exc:  # почта не должна ронять бизнес-операцию
        log.error("Не удалось отправить письмо %s: %s", to, exc)
        return False
