import datetime
import re
import threading

import pytest

from core import auth, first_run
from core.models import SetupCode, SetupState, User

GOOD = dict(username="kepala.hr", display_name="Kepala HR", email="hr@example.com",
            password="Admin12345", confirm="Admin12345")


def issue(db, capsys, force=False):
    status = first_run.issue_code(db, force=force)
    err = capsys.readouterr().err
    m = re.search(r"FIRST-RUN SETUP CODE: ([A-Z0-9-]+)", err)
    return status, (m.group(1) if m else None)


def test_fresh_db_requires_setup_and_code_only_in_server_log(db, capsys):
    assert first_run.setup_required(db)
    status, code = issue(db, capsys)
    assert status == "issued" and re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code)
    row = db.query(SetupCode).one()
    assert code.replace("-", "") not in row.code_hash and len(row.code_hash) == 64
    # A second call must not reveal or reissue anything.
    assert issue(db, capsys) == ("existing", None)


def test_setup_creates_admin_then_closes_permanently(db, capsys):
    _, code = issue(db, capsys)
    ok, status = first_run.complete_setup(db, code.lower(), **GOOD)  # case/format tolerant
    assert ok, status
    admin = db.query(User).filter(User.username == "kepala.hr").one()
    assert admin.role == "admin" and auth.verify_password("Admin12345", admin.password_hash)
    assert db.get(SetupState, 1).completed_by_user_id == admin.id
    assert auth.attempt_login(db, "kepala.hr", "Admin12345")[0] is not None
    # Closed for good, even if every admin disappears later.
    admin.password_hash = "DISABLED"; db.commit()  # admin deactivated
    assert not first_run.setup_required(db)
    assert issue(db, capsys) == ("not_required", None)
    assert first_run.complete_setup(db, code, **GOOD) == (False, "closed")


def test_reused_code(db, capsys):
    _, code = issue(db, capsys)
    row = db.query(SetupCode).one()
    row.used_at = datetime.datetime.now(); db.commit()
    assert first_run.complete_setup(db, code, **GOOD) == (False, "used")


def test_invalid_code_and_attempt_limit(db, capsys):
    _, code = issue(db, capsys)
    for _ in range(first_run.MAX_CODE_ATTEMPTS):
        assert first_run.complete_setup(db, "AAAA-BBBB-CCCC", **GOOD) == (False, "invalid_code")
    # The real code is now voided as well.
    assert first_run.complete_setup(db, code, **GOOD) == (False, "too_many_attempts")
    assert db.query(User).filter(User.role == "admin").count() == 0


def test_expired_code(db, capsys):
    _, code = issue(db, capsys)
    row = db.query(SetupCode).one()
    row.expires_at = datetime.datetime.now() - datetime.timedelta(seconds=1); db.commit()
    assert first_run.complete_setup(db, code, **GOOD) == (False, "expired")


def test_regenerate_voids_old_code_and_is_throttled(db, capsys):
    _, old = issue(db, capsys)
    assert issue(db, capsys, force=True)[0] == "throttled"
    row = db.query(SetupCode).one()
    row.created_at -= datetime.timedelta(seconds=first_run.REGENERATE_COOLDOWN_SECONDS + 1); db.commit()
    status, new = issue(db, capsys, force=True)
    assert status == "issued" and new != old
    assert first_run.complete_setup(db, old, **GOOD) == (False, "used")
    assert first_run.complete_setup(db, new, **GOOD)[0]


def test_setup_not_available_when_admin_exists(db, capsys):
    db.add(User(username="boss", password_hash=auth.hash_password("Boss12345"), role="admin")); db.commit()
    assert not first_run.setup_required(db)
    assert issue(db, capsys) == ("not_required", None)
    assert db.query(SetupCode).count() == 0
    assert first_run.complete_setup(db, "AAAA-BBBB-CCCC", **GOOD) == (False, "closed")


def test_disabled_admin_does_not_count_as_admin(db):
    db.add(User(username="old", password_hash="DISABLED", role="admin")); db.commit()
    assert first_run.setup_required(db)


@pytest.mark.parametrize("field,value", [
    ("username", "A B"), ("display_name", " "), ("email", "nope"), ("password", "short"),
])
def test_field_validation(db, capsys, field, value):
    _, code = issue(db, capsys)
    data = dict(GOOD, **{field: value})
    if field == "password":
        data["confirm"] = value
    ok, msg = first_run.complete_setup(db, code, **data)
    assert not ok and msg not in ("ok", "closed")
    assert db.query(SetupCode).one().used_at is None  # validation errors do not burn the code


def test_concurrent_setup_creates_exactly_one_admin(db, capsys):
    from core.database import SessionLocal
    _, code = issue(db, capsys)
    results, barrier = [], threading.Barrier(8)

    def worker(i):
        s = SessionLocal()
        try:
            barrier.wait()
            try:
                results.append(first_run.complete_setup(
                    s, code, **dict(GOOD, username=f"admin{i}")))
            except Exception as exc:  # a DB-level conflict is an acceptable loser outcome
                results.append((False, type(exc).__name__))
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    db.expire_all()
    assert sum(1 for ok, _ in results if ok) == 1, results
    assert db.query(User).filter(User.role == "admin").count() == 1


def test_initial_admin_password_is_recovery_path(db, monkeypatch, capsys):
    # Setup completed earlier, then every admin was lost: only the server-side setting helps.
    _, code = issue(db, capsys)
    first_run.complete_setup(db, code, **GOOD)
    for u in db.query(User).all():
        u.password_hash = "DISABLED"
    db.commit()
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Pulih12345")
    auth.init_default_users(db)
    admin = db.query(User).filter(User.username == "admin").one()
    assert admin.must_change_password and not first_run.setup_required(db)


# --- database failure classification ----------------------------------------
def test_classify_unreachable_and_bad_url():
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import ArgumentError
    from core.database import classify_db_error
    eng = create_engine("postgresql://u:p@127.0.0.1:1/x?connect_timeout=2")
    with pytest.raises(Exception) as ei:
        with eng.connect() as c:
            c.execute(text("select 1"))
    assert classify_db_error(ei.value) == "unreachable"
    with pytest.raises(ArgumentError) as ei2:
        create_engine("not a url")
    assert classify_db_error(ei2.value) == "invalid_url"


def test_missing_database_url_is_reported_not_raised(tmp_path):
    import subprocess, sys, os
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "DEMO_MODE")}
    code = "import core.database as d; print(d.CONFIG_ERROR, d.engine)"
    out = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.dirname(__file__)),
                         env=env, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "missing_url None", out.stderr
    env["DATABASE_URL"] = "nonsense://x"
    out = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.dirname(__file__)),
                         env=env, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "invalid_url None", out.stderr
