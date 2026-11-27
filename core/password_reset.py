# core/password_reset.py
"""Email-based password recovery.

- Tokens: 32 random bytes (secrets.token_urlsafe), only the SHA-256 hash is stored.
- Expire after RESET_TOKEN_MINUTES, single use; issuing a new token voids older ones.
- Requests are throttled per account and the response never reveals whether
  an email is registered.
"""
import datetime
import hashlib
import logging
import secrets

from sqlalchemy import func

from core import mailer
from core.auth import (
    hash_password, normalize_email, is_valid_email, validate_new_password, _get_setting,
)
from core.models import AuditLog, PasswordResetToken, User

log = logging.getLogger(__name__)

RESET_TOKEN_MINUTES = 30
MAX_REQUESTS_PER_HOUR = 3


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def build_reset_url(raw_token: str) -> str:
    base = (_get_setting("APP_BASE_URL") or "http://localhost:8501").rstrip("/")
    return f"{base}/?reset_token={raw_token}"


def is_available() -> bool:
    return mailer.is_configured()


def request_password_reset(db, email: str) -> str:
    """Returns 'invalid_email', 'unavailable' or 'accepted'.
    'accepted' is returned whether or not the email belongs to an account."""
    email = normalize_email(email)
    if not is_valid_email(email):
        return "invalid_email"
    if not mailer.is_configured():
        return "unavailable"

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or user.username.startswith("inactive_") or user.password_hash == "DISABLED":
        return "accepted"

    now = datetime.datetime.now()
    recent = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at > now - datetime.timedelta(hours=1))
        .count()
    )
    if recent >= MAX_REQUESTS_PER_HOUR:
        return "accepted"

    # Void any outstanding token, then issue a fresh one.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)

    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=_hash(raw), created_at=now,
        expires_at=now + datetime.timedelta(minutes=RESET_TOKEN_MINUTES),
    ))
    db.add(AuditLog(user_id=user.id, action="PASSWORD_RESET_REQUEST", table_name="users",
                    record_id=user.id, created_at=now))
    db.commit()

    body = (
        f"Halo {user.display_name or user.username},\n\n"
        "Kami menerima permintaan untuk mengatur ulang password akun FPTK & Sourcing Anda "
        f"(username: {user.username}).\n\n"
        f"Buka tautan berikut dalam {RESET_TOKEN_MINUTES} menit untuk membuat password baru:\n"
        f"{build_reset_url(raw)}\n\n"
        "Tautan hanya bisa dipakai sekali. Jika Anda tidak meminta reset password, abaikan email ini; "
        "password Anda tidak berubah.\n"
    )
    try:
        mailer.send_email(user.email, "Reset password FPTK & Sourcing", body)
    except Exception:
        # Do not leak SMTP details to the browser; keep them in server logs.
        log.exception("Password reset email failed for user_id=%s", user.id)
        return "send_failed"
    return "accepted"


def check_token(db, raw_token: str):
    """Returns (token_row, status) with status 'valid', 'invalid', 'expired' or 'used'."""
    if not raw_token or len(raw_token) > 200:
        return None, "invalid"
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == _hash(raw_token)).first()
    if not row:
        return None, "invalid"
    if row.used_at is not None:
        return row, "used"
    if row.expires_at < datetime.datetime.now():
        return row, "expired"
    return row, "valid"


def reset_password_with_token(db, raw_token: str, new_password: str, confirm: str):
    """Returns (ok, message_or_status)."""
    row, status = check_token(db, raw_token)
    if status != "valid":
        return False, status
    error = validate_new_password(new_password, confirm)
    if error:
        return False, error
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        return False, "invalid"
    now = datetime.datetime.now()
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    row.used_at = now
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    db.add(AuditLog(user_id=user.id, action="PASSWORD_RESET", table_name="users",
                    record_id=user.id, created_at=now))
    db.commit()
    return True, "ok"
