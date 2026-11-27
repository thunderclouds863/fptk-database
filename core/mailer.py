# core/mailer.py
"""Minimal SMTP mailer. Configured through env vars or Streamlit secrets:

SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
SMTP_SECURITY = "starttls" (default) | "ssl" | "none".
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def _setting(name, default=None):
    val = os.getenv(name)
    if val:
        return val
    try:
        import streamlit as st
        val = st.secrets.get(name)
    except Exception:
        val = None
    return val if val else default


def is_configured() -> bool:
    return bool(_setting("SMTP_HOST") and _setting("SMTP_FROM"))


def send_email(to_address: str, subject: str, body: str) -> None:
    """Send a plain-text email. Raises on any SMTP failure."""
    host = _setting("SMTP_HOST")
    sender = _setting("SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("SMTP is not configured")
    port = int(_setting("SMTP_PORT", "587"))
    security = (_setting("SMTP_SECURITY", "starttls") or "starttls").lower()
    user = _setting("SMTP_USER")
    password = _setting("SMTP_PASSWORD")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    try:
        if security == "starttls":
            server.starttls(context=context)
        if user and password:
            server.login(user, password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass
