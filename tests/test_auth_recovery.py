import datetime
import hashlib
import threading

import pytest

from core import auth
from core.models import AuditLog, LoginAttempt, PasswordResetToken, User


def make_user(db, username="rina", password="Rahasia123", email="rina@example.com", **kw):
    u = User(username=username, password_hash=auth.hash_password(password), role=kw.pop("role", "user"),
             email=email, **kw)
    db.add(u)
    db.commit()
    return u


# --- password policy -------------------------------------------------------
@pytest.mark.parametrize("pw,ok", [
    ("short1", False), ("allletters", False), ("12345678", False),
    ("password123", False), ("Rahasia123", True),
])
def test_password_policy(pw, ok):
    assert (auth.validate_new_password(pw) is None) == ok


def test_password_confirmation_mismatch():
    assert auth.validate_new_password("Rahasia123", "Rahasia124")


# --- login + lockout ---------------------------------------------------------
def test_login_success_and_wrong_password(db):
    make_user(db)
    user, err = auth.attempt_login(db, "rina", "Rahasia123")
    assert user and err is None
    user, err = auth.attempt_login(db, "rina", "wrong")
    assert user is None and err == "invalid"
    assert auth.attempt_login(db, "nobody", "x") == (None, "invalid")


def test_lockout_after_repeated_failures(db):
    make_user(db)
    for _ in range(auth.MAX_FAILED_LOGINS):
        assert auth.attempt_login(db, "rina", "wrong")[1] == "invalid"
    # Even the correct password is refused while locked.
    assert auth.attempt_login(db, "rina", "Rahasia123") == (None, "locked")


def test_lockout_same_for_unknown_username(db):
    """Lockout must not reveal whether a username exists."""
    make_user(db)
    for name in ("rina", "tidak-ada"):
        for _ in range(auth.MAX_FAILED_LOGINS):
            assert auth.attempt_login(db, name, "wrong")[1] == "invalid"
        assert auth.attempt_login(db, name, "whatever")[1] == "locked"


def test_lockout_is_case_insensitive_and_success_resets(db):
    make_user(db)
    for _ in range(auth.MAX_FAILED_LOGINS - 1):
        auth.attempt_login(db, "RINA", "wrong")
    assert auth.attempt_login(db, "rina", "Rahasia123")[0] is not None
    for _ in range(auth.MAX_FAILED_LOGINS - 1):
        auth.attempt_login(db, "rina", "wrong")
    assert auth.attempt_login(db, "rina", "Rahasia123")[0] is not None


def test_lockout_expires(db):
    make_user(db)
    old = datetime.datetime.now() - datetime.timedelta(minutes=auth.LOGIN_LOCK_MINUTES + 1)
    for _ in range(auth.MAX_FAILED_LOGINS):
        db.add(LoginAttempt(username_key="rina", success=False, created_at=old))
    db.commit()
    user, err = auth.attempt_login(db, "rina", "Rahasia123")
    assert user and err is None


def test_known_default_password_forces_change(db):
    make_user(db, password="password123")
    user, _ = auth.attempt_login(db, "rina", "password123")
    assert user.must_change_password is True


def test_disabled_account_cannot_login(db):
    db.add(User(username="seed", password_hash="DISABLED", role="user"))
    db.commit()
    assert auth.attempt_login(db, "seed", "DISABLED") == (None, "invalid")


# --- seeding ---------------------------------------------------------------
def test_seed_has_no_known_passwords(db, monkeypatch):
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    auth.init_default_users(db)
    assert db.query(User).filter(User.role == "admin").count() == 0
    hashes = {u.password_hash for u in db.query(User).all()}
    assert hashes == {"DISABLED"}

    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Awal12345")
    auth.init_default_users(db)
    admin = db.query(User).filter(User.username == "admin").one()
    assert admin.must_change_password and auth.verify_password("Awal12345", admin.password_hash)


# --- additive migration ----------------------------------------------------
def test_migration_adds_columns_to_old_users_table(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    import core.database as database
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50), "
                       "password_hash VARCHAR(255), role VARCHAR(20))"))
        c.execute(text("INSERT INTO users VALUES (1, 'lama', 'x', 'user')"))
    monkeypatch.setattr(database, "engine", eng)
    database._add_missing_columns()
    database._add_missing_columns()  # idempotent
    cols = {c["name"] for c in inspect(eng).get_columns("users")}
    assert {"email", "must_change_password"} <= cols
    with eng.connect() as c:
        assert c.execute(text("SELECT username FROM users")).scalar() == "lama"


# --- password recovery -----------------------------------------------------
@pytest.fixture()
def smtp_inbox(monkeypatch):
    """Real SMTP round-trip against a local aiosmtpd server."""
    from aiosmtpd.controller import Controller

    inbox = []

    class Handler:
        async def handle_DATA(self, server, session, envelope):
            inbox.append(envelope)
            return "250 OK"

    ctrl = Controller(Handler(), hostname="127.0.0.1", port=8025)
    ctrl.start()
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "8025")
    monkeypatch.setenv("SMTP_SECURITY", "none")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("APP_BASE_URL", "https://fptk.example.com")
    yield inbox
    ctrl.stop()


def _token_from(inbox):
    from email import message_from_bytes, policy
    body = message_from_bytes(inbox[-1].content, policy=policy.default).get_content()
    line = next(l for l in body.splitlines() if "reset_token=" in l)
    assert line.startswith("https://fptk.example.com/?reset_token=")
    return line.split("reset_token=")[1].strip()


def test_reset_unavailable_without_smtp(db, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from core.password_reset import request_password_reset
    assert request_password_reset(db, "rina@example.com") == "unavailable"


def test_full_reset_flow(db, smtp_inbox):
    from core.password_reset import request_password_reset, check_token, reset_password_with_token
    u = make_user(db)
    assert request_password_reset(db, "invalid") == "invalid_email"
    assert request_password_reset(db, "RINA@example.com ") == "accepted"
    assert len(smtp_inbox) == 1 and smtp_inbox[0].rcpt_tos == ["rina@example.com"]
    raw = _token_from(smtp_inbox)

    row = db.query(PasswordResetToken).one()
    assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest() and raw not in row.token_hash
    assert check_token(db, raw)[1] == "valid"
    assert check_token(db, raw + "x")[1] == "invalid"

    ok, msg = reset_password_with_token(db, raw, "Baru12345", "Beda12345")
    assert not ok
    ok, msg = reset_password_with_token(db, raw, "Baru12345", "Baru12345")
    assert ok
    db.refresh(u)
    assert auth.verify_password("Baru12345", u.password_hash)
    assert check_token(db, raw)[1] == "used"
    assert reset_password_with_token(db, raw, "Lagi12345", "Lagi12345") == (False, "used")


def test_unknown_email_is_indistinguishable(db, smtp_inbox):
    from core.password_reset import request_password_reset
    assert request_password_reset(db, "ghost@example.com") == "accepted"
    assert smtp_inbox == []


def test_new_request_voids_previous_token_and_rate_limit(db, smtp_inbox):
    from core.password_reset import request_password_reset, check_token, MAX_REQUESTS_PER_HOUR
    make_user(db)
    request_password_reset(db, "rina@example.com")
    first = _token_from(smtp_inbox)
    request_password_reset(db, "rina@example.com")
    assert check_token(db, first)[1] == "used"
    for _ in range(MAX_REQUESTS_PER_HOUR):
        request_password_reset(db, "rina@example.com")
    assert len(smtp_inbox) == MAX_REQUESTS_PER_HOUR


def test_expired_token(db, smtp_inbox):
    from core.password_reset import request_password_reset, check_token
    make_user(db)
    request_password_reset(db, "rina@example.com")
    raw = _token_from(smtp_inbox)
    row = db.query(PasswordResetToken).one()
    row.expires_at = datetime.datetime.now() - datetime.timedelta(seconds=1)
    db.commit()
    assert check_token(db, raw)[1] == "expired"
