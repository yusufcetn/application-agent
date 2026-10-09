"""Send email over SMTP; the login defaults to the IMAP account used for job alerts."""

import smtplib
from email.message import EmailMessage

from app.config import get_settings


class MailNotConfiguredError(RuntimeError):
    pass


class MailError(RuntimeError):
    pass


def send_email(subject: str, text: str, html: str) -> str:
    """Returns the recipient."""
    config = get_settings()
    user = config.smtp_user or config.imap_user
    password = config.smtp_password or config.imap_password
    if not user or not password:
        raise MailNotConfiguredError(
            "E-posta gönderimi için .env içinde IMAP_USER / IMAP_PASSWORD (ya da SMTP_USER / "
            "SMTP_PASSWORD) tanımlı olmalı."
        )
    to = config.report_email_to or user
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = to
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    try:
        if config.smtp_port == 465:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.login(user, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Rapor e-postası gönderilemedi: {e}") from e
    return to
