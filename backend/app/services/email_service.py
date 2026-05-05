"""
Email service — currently a dev stub that logs tokens to console.
To enable real email, set SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD in .env
and swap the _send() body with smtplib/sendgrid/etc.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html_body: str) -> None:
    if not settings.SMTP_HOST:
        # Dev mode: just log the content
        logger.info("[EMAIL DEV] To: %s | Subject: %s", to, subject)
        logger.info("[EMAIL DEV] Body: %s", html_body)
        print(f"\n[DEV EMAIL] To: {to}\nSubject: {subject}\n{html_body}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, to, msg.as_string())


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    subject = "Xác minh tài khoản PDPTW"
    body = f"""
    <h2>Xác minh tài khoản của bạn</h2>
    <p>Bấm vào link bên dưới để kích hoạt tài khoản:</p>
    <p><a href="{link}">{link}</a></p>
    <p>Link có hiệu lực trong {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} giờ.</p>
    """
    _send(to, subject, body)


def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    subject = "Đặt lại mật khẩu PDPTW"
    body = f"""
    <h2>Đặt lại mật khẩu</h2>
    <p>Bấm vào link bên dưới để đặt lại mật khẩu:</p>
    <p><a href="{link}">{link}</a></p>
    <p>Link có hiệu lực trong {settings.PASSWORD_RESET_EXPIRE_HOURS} giờ.</p>
    <p>Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này.</p>
    """
    _send(to, subject, body)
