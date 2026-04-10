"""Optional SMTP email using only the Python standard library (smtplib)."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)


def send_email(app, *, subject: str, body_text: str, to_addr: str) -> bool:
    """Send one plain-text email. Returns True if sent, False if skipped or failed."""
    server = app.config.get("MAIL_SERVER")
    if not server:
        logger.info("MAIL_SERVER not set; email not sent. Subject=%r to=%r", subject, to_addr)
        return False

    port = int(app.config.get("MAIL_PORT") or 587)
    user = app.config.get("MAIL_USERNAME") or ""
    password = app.config.get("MAIL_PASSWORD") or ""
    use_tls = app.config.get("MAIL_USE_TLS", True)
    sender = app.config.get("MAIL_DEFAULT_SENDER") or user or "noreply@localhost"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(body_text)

    try:
        with smtplib.SMTP(server, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except OSError as e:
        logger.exception("SMTP send failed: %s", e)
        return False
