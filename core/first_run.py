# core/first_run.py
"""First-run administrator setup.

Used only while no active administrator exists and setup has never completed.

- A one-time setup code (≈60 bits, from `secrets`) is generated server-side and
  written ONLY to the server log (stderr). The database stores its SHA-256 hash.
  It is never rendered in the UI or returned by any function the UI calls.
- Codes expire after SETUP_CODE_MINUTES, are single use, and are voided after
  MAX_CODE_ATTEMPTS wrong entries. Issuing a new code voids older ones.
- Completion is a single transaction guarded by two conditional UPDATEs (code not
  yet used, setup not yet completed), so concurrent submissions cannot create more
  than one initial administrator.
- After completion `setup_state.completed_at` is set and setup is permanently
  closed. Recovery when every admin is lost is a deliberate server-side action:
  set INITIAL_ADMIN_PASSWORD in the deployment settings (see core/auth.py).
"""
import datetime
import hashlib
import re
import secrets
import sys

from sqlalchemy import update

from core.auth import (
    active_admin_exists, hash_password, is_valid_email, normalize_email, validate_new_password,
)
from core.models import AuditLog, SetupCode, SetupState, User

SETUP_CODE_MINUTES = 60
MAX_CODE_ATTEMPTS = 5
REGENERATE_COOLDOWN_SECONDS = 60
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,49}$")


def _now():
    return datetime.datetime.now()


def _normalize_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def _hash(code: str) -> str:
    return hashlib.sha256(_normalize_code(code).encode()).hexdigest()


def _state(db) -> SetupState:
    state = db.get(SetupState, 1)
    if state is None:
        state = SetupState(id=1)
        db.add(state)
        db.flush()
    return state


def setup_required(db) -> bool:
    """True only while setup has never completed AND no active admin exists.
    If an admin already exists (existing deployments, INITIAL_ADMIN_PASSWORD, demo),
    setup is marked completed so it can never be opened later."""
    state = _state(db)
    if state.completed_at is not None:
        db.commit()
        return False
    if active_admin_exists(db):
        state.completed_at = _now()
        db.commit()
        return False
    db.commit()
    return True


def _valid_code_query(db, now):
    return db.query(SetupCode).filter(
        SetupCode.used_at.is_(None),
        SetupCode.expires_at > now,
        SetupCode.failed_attempts < MAX_CODE_ATTEMPTS,
    )


def _log_code(code: str, expires_at: datetime.datetime):
    # stderr only: visible in the server/hosting log, never in the browser.
    banner = "=" * 64
    print(f"\n{banner}\n[fptk] FIRST-RUN SETUP CODE: {code}\n"
          f"[fptk] Valid until {expires_at:%Y-%m-%d %H:%M} (server time), single use.\n"
          f"[fptk] Enter it on the app's 'Pengaturan awal' screen to create the first admin.\n"
          f"{banner}\n", file=sys.stderr, flush=True)


def issue_code(db, force: bool = False) -> str:
    """Make sure an operator can obtain a valid code from the server log.
    Returns 'not_required', 'existing', 'throttled' or 'issued'. Never returns the code."""
    if not setup_required(db):
        return "not_required"
    now = _now()
    current = _valid_code_query(db, now).order_by(SetupCode.created_at.desc()).first()
    if current and not force:
        return "existing"
    latest = db.query(SetupCode).order_by(SetupCode.created_at.desc()).first()
    if force and latest and (now - latest.created_at).total_seconds() < REGENERATE_COOLDOWN_SECONDS:
        return "throttled"
    db.query(SetupCode).filter(SetupCode.used_at.is_(None)).update(
        {SetupCode.used_at: now}, synchronize_session=False)
    code_raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    code = "-".join(code_raw[i:i + 4] for i in range(0, 12, 4))
    expires = now + datetime.timedelta(minutes=SETUP_CODE_MINUTES)
    db.add(SetupCode(code_hash=_hash(code), created_at=now, expires_at=expires, failed_attempts=0))
    db.commit()
    _log_code(code, expires)
    return "issued"


def _register_failure(db, now):
    db.query(SetupCode).filter(SetupCode.used_at.is_(None), SetupCode.expires_at > now).update(
        {SetupCode.failed_attempts: SetupCode.failed_attempts + 1}, synchronize_session=False)
    db.commit()


def validate_admin_fields(username, display_name, email, password, confirm):
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username):
        return "Username 3–50 karakter: huruf kecil, angka, titik, garis bawah atau tanda hubung."
    if not (display_name or "").strip():
        return "Nama tampilan wajib diisi."
    email = normalize_email(email)
    if email and not is_valid_email(email):
        return "Format email tidak valid."
    return validate_new_password(password, confirm)


def complete_setup(db, code, username, display_name, email, password, confirm):
    """Create the first administrator. Returns (ok, status) where status is
    'ok', 'closed', 'invalid_code', 'expired', 'used', 'too_many_attempts' or a
    field validation message."""
    error = validate_admin_fields(username, display_name, email, password, confirm)
    if error:
        return False, error
    if not setup_required(db):
        return False, "closed"

    now = _now()
    code_hash = _hash(code)
    row = db.query(SetupCode).filter(SetupCode.code_hash == code_hash).first()
    if row is None:
        _register_failure(db, now)
        return False, "invalid_code"
    if row.used_at is not None:
        return False, "used"
    if row.failed_attempts >= MAX_CODE_ATTEMPTS:
        return False, "too_many_attempts"
    if row.expires_at <= now:
        return False, "expired"

    try:
        # 1) Consume the code atomically: only one request can flip used_at.
        consumed = db.execute(
            update(SetupCode)
            .where(SetupCode.id == row.id, SetupCode.used_at.is_(None),
                   SetupCode.expires_at > now, SetupCode.failed_attempts < MAX_CODE_ATTEMPTS)
            .values(used_at=now)
        ).rowcount
        if consumed != 1:
            db.rollback()
            return False, "used"
        # 2) Close setup atomically: guards against races with a different code.
        closed = db.execute(
            update(SetupState).where(SetupState.id == 1, SetupState.completed_at.is_(None))
            .values(completed_at=now)
        ).rowcount
        if closed != 1 or active_admin_exists(db):
            db.rollback()
            return False, "closed"
        uname = username.strip().lower()
        if db.query(User.id).filter(User.username == uname).first():
            db.rollback()
            return False, "Username sudah dipakai."
        admin = User(username=uname, password_hash=hash_password(password), role="admin",
                     display_name=display_name.strip(), pic_recruiter="Admin",
                     business_unit="CORP", kode_pic="ADMIN", email=normalize_email(email),
                     must_change_password=False)
        db.add(admin)
        db.flush()
        db.execute(update(SetupState).where(SetupState.id == 1).values(completed_by_user_id=admin.id))
        db.add(AuditLog(user_id=admin.id, action="FIRST_RUN_SETUP", table_name="users",
                        record_id=admin.id, created_at=now))
        db.commit()
        return True, "ok"
    except Exception:
        db.rollback()
        raise
