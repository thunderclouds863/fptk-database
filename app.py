# app.py
import html
import importlib
import logging
from contextlib import contextmanager
from datetime import datetime

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from core.session_manager import get_session_manager, check_idle_timeout, touch_session
from core import database
from core.database import SessionLocal, init_db
from core.auth import (
    attempt_login, is_admin, init_default_users, verify_password,
    init_master_dropdown, validate_new_password, set_user_password,
    LOGIN_LOCK_MINUTES,
)
from core.models import User
from core.demo import is_demo
from core.ui import apply_base_styles, apply_auth_styles, run_page, install_client_hooks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fptk")

LOGO_PATH = "asset/cimory_logo.png"

st.set_page_config(
    page_title="FPTK & Sourcing",
    page_icon=LOGO_PATH,
    layout="wide",
    initial_sidebar_state="auto",
)


def get_cached_db():
    return SessionLocal()


@st.cache_resource
def initialize_system():
    """Runs once per server process (failures are not cached, so a retry re-runs it)."""
    database.check_connection()
    init_db()
    db = SessionLocal()
    try:
        init_default_users(db)
        init_master_dropdown(db)
        if is_demo():
            from core.demo import seed_demo_data
            seed_demo_data(db)
        from core.first_run import issue_code
        issue_code(db)  # writes a setup code to the server log only if setup is needed
    finally:
        db.close()
    return True


# Non-technical copy per failure category. Details (never credentials) go to the server log.
_SYSTEM_PROBLEMS = {
    "missing_url": ("Aplikasi belum terhubung ke database",
                    "Pengaturan koneksi database belum diisi di server.", "DB-CONFIG"),
    "invalid_url": ("Aplikasi belum terhubung ke database",
                    "Pengaturan koneksi database di server tidak valid.", "DB-CONFIG"),
    "auth_failed": ("Aplikasi tidak dapat masuk ke database",
                    "Server database menolak akses aplikasi.", "DB-AUTH"),
    "unreachable": ("Database sedang tidak dapat dihubungi",
                    "Server database tidak merespons. Biasanya ini sementara.", "DB-UNREACHABLE"),
    "db_missing": ("Database belum siap",
                   "Database tujuan belum dibuat di server.", "DB-INIT"),
    "init_failed": ("Database belum siap",
                    "Persiapan awal database gagal.", "DB-INIT"),
}


def render_system_problem(category):
    title, detail, code = _SYSTEM_PROBLEMS.get(category, _SYSTEM_PROBLEMS["init_failed"])
    apply_auth_styles()
    st.image(LOGO_PATH, width=132)
    st.header(title, anchor=False)
    st.write(f"{detail} Data Anda tidak terpengaruh.")
    st.caption(f"Kode: {code}. Jika masalah berlanjut, sampaikan kode ini ke administrator sistem.")
    if st.button("Coba lagi", type="primary", width="stretch"):
        st.rerun()
    st.stop()


@contextmanager
def db_guard(slot=None):
    """Turn a database failure during a run into the system-problem screen instead of a
    raw exception or a misleading message. `slot` (an st.empty) is cleared first."""
    try:
        yield
    except SQLAlchemyError as exc:
        category = database.classify_db_error(exc)
        log.error("Database error during request (%s): %s", category, type(exc).__name__, exc_info=exc)
        if slot is not None:
            slot.empty()
        render_system_problem(category)


if database.CONFIG_ERROR:
    log.error("Database configuration problem: %s", database.CONFIG_ERROR)
    render_system_problem(database.CONFIG_ERROR)

try:
    initialize_system()
except Exception as _exc:  # noqa: BLE001 - startup boundary
    if type(_exc).__module__.startswith("streamlit"):
        raise
    _category = database.classify_db_error(_exc)
    log.error("Database startup failed (%s) target=%s: %s", _category, database.describe_target(),
              type(_exc).__name__, exc_info=_exc)
    render_system_problem(_category)


session_mgr = get_session_manager()

for _key, _default in (("user_id", session_mgr.user_id), ("username", session_mgr.username),
                       ("role", session_mgr.role), ("user_display", session_mgr.user_display),
                       ("last_fptk_load", datetime.now()), ("last_sourcing_load", datetime.now()),
                       ("last_activity", None)):
    if _key not in st.session_state:
        st.session_state[_key] = _default

if st.session_state.user_id:
    touch_session()
    if check_idle_timeout():
        st.rerun()

apply_base_styles()


# ---------------------------------------------------------------------------
# Unauthenticated views: login, forgot password, reset password
# ---------------------------------------------------------------------------
def _auth_header(title, subtitle=None):
    st.image(LOGO_PATH, width=132)
    st.header(title, anchor=False)
    if subtitle:
        st.markdown(f'<p class="auth-sub">{subtitle}</p>', unsafe_allow_html=True)


def _complete_login(user):
    session_mgr.login(user.id, user.username, user.role, user.display_name or user.username)
    st.session_state.user_id = user.id
    st.session_state.username = user.username
    st.session_state.role = user.role
    st.session_state.user_display = user.display_name or user.username
    st.session_state.last_activity = datetime.now()
    st.session_state.must_change_password = bool(user.must_change_password)
    st.session_state.pop("auth_view", None)


def _setup_needed():
    from core.first_run import setup_required
    db = get_cached_db()
    try:
        return setup_required(db)
    finally:
        db.close()


def render_login():
    _auth_header("Masuk", "FPTK & Sourcing System · Rekrutmen")
    if is_demo():
        st.markdown('<span class="auth-env">LINGKUNGAN DEMO</span>', unsafe_allow_html=True)

    if _setup_needed():
        st.info("Aplikasi belum disiapkan: belum ada akun administrator. "
                "Pengelola sistem perlu menyelesaikan pengaturan awal sebelum siapa pun bisa masuk.")
        if st.button("Pengaturan awal", type="primary", width="stretch"):
            st.session_state.auth_view = "setup"
            st.rerun()
        return

    flash = st.session_state.pop("auth_flash", None)
    if flash:
        st.success(flash)
    expired_msg = st.session_state.pop("session_expired_message", None)
    st.session_state.pop("session_expired_username", None)
    if expired_msg:
        st.warning(expired_msg)

    with st.form("login_form", border=True):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Masuk", type="primary", width="stretch")

    if submitted:
        if not username or not password:
            st.error("Isi username dan password.")
        else:
            db = get_cached_db()
            user = error = None
            try:
                with st.spinner("Memeriksa akun..."):
                    user, error = attempt_login(db, username, password)
                if user:
                    _complete_login(user)  # reads user attributes, so before db.close()
            except SQLAlchemyError:
                # Infrastructure failure: never reported as wrong credentials.
                log.exception("Login failed: database error")
                user, error = None, "unavailable"
            finally:
                db.close()
            if user:
                st.rerun()
            elif error == "locked":
                st.error(f"Terlalu banyak percobaan masuk yang gagal. Demi keamanan, coba lagi "
                         f"dalam {LOGIN_LOCK_MINUTES} menit atau gunakan Lupa password.")
            elif error == "unavailable":
                st.warning("Layanan sedang tidak dapat menghubungi database, jadi akun belum bisa "
                           "diperiksa. Coba lagi beberapa saat.")
            else:
                st.error("Username atau password salah. Periksa juga Caps Lock.")

    if st.button("Lupa password?", type="tertiary"):
        st.session_state.auth_view = "forgot"
        st.rerun()

    if is_demo():
        st.caption("Demo: **demo_admin** / **demo123** (admin) atau **recruiter1** / **demo123** "
                   "(recruiter). Data contoh.")


def render_setup():
    from core.first_run import (issue_code, complete_setup, SETUP_CODE_MINUTES,
                                REGENERATE_COOLDOWN_SECONDS)
    from core.auth import MIN_PASSWORD_LENGTH
    _auth_header("Pengaturan awal", "Buat akun administrator pertama.")
    db = get_cached_db()
    try:
        status = issue_code(db)
        if status == "not_required":
            st.session_state.pop("auth_view", None)
            st.session_state.auth_flash = "Pengaturan awal sudah selesai. Silakan masuk."
            st.rerun()

        st.caption("Kode pengaturan sekali pakai hanya tersedia bagi pengelola server, di log aplikasi "
                   f"(misalnya Streamlit Cloud → Manage app → Logs). Kode berlaku {SETUP_CODE_MINUTES} menit.")
        with st.form("setup_form", border=True):
            code = st.text_input("Kode pengaturan", placeholder="XXXX-XXXX-XXXX", autocomplete="off")
            username = st.text_input("Username admin", autocomplete="username")
            display_name = st.text_input("Nama tampilan")
            email = st.text_input("Email (untuk reset password, opsional)", autocomplete="email")
            st.caption(f"Password minimal {MIN_PASSWORD_LENGTH} karakter, berisi huruf dan angka.")
            password = st.text_input("Password", type="password", autocomplete="new-password")
            confirm = st.text_input("Ulangi password", type="password", autocomplete="new-password")
            submitted = st.form_submit_button("Buat akun admin", type="primary", width="stretch")
        if submitted:
            with st.spinner("Membuat akun..."):
                ok, result = complete_setup(db, code, username, display_name, email, password, confirm)
            if ok:
                st.session_state.pop("auth_view", None)
                st.session_state.auth_flash = "Akun administrator dibuat. Silakan masuk."
                st.rerun()
            messages = {
                "invalid_code": "Kode pengaturan tidak valid.",
                "used": "Kode ini sudah dipakai. Buat kode baru.",
                "expired": "Kode sudah kedaluwarsa. Buat kode baru.",
                "too_many_attempts": "Terlalu banyak kode salah; kode dinonaktifkan. Buat kode baru.",
                "closed": "Pengaturan awal sudah selesai. Silakan masuk.",
            }
            st.error(messages.get(result, result))

        if st.button("Buat kode baru", type="tertiary",
                     help="Kode baru ditulis ke log server; kode lama tidak berlaku lagi."):
            result = issue_code(db, force=True)
            if result == "throttled":
                st.warning(f"Tunggu {REGENERATE_COOLDOWN_SECONDS} detik sebelum membuat kode baru.")
            elif result == "issued":
                st.success("Kode baru sudah ditulis ke log server.")
    finally:
        db.close()

    if st.button("Kembali ke halaman masuk", type="tertiary"):
        st.session_state.pop("auth_view", None)
        st.rerun()


def render_forgot():
    from core.password_reset import request_password_reset, is_available
    _auth_header("Lupa password", "Masukkan email yang terdaftar di akun Anda. "
                                  "Kami akan mengirim tautan untuk membuat password baru.")
    if not is_available():
        st.info("Reset password lewat email belum diaktifkan di server ini. "
                "Hubungi admin untuk mengatur ulang password Anda.")
    else:
        with st.form("forgot_form", border=True):
            email = st.text_input("Email", autocomplete="email")
            submitted = st.form_submit_button("Kirim tautan reset", type="primary", width="stretch")
        if submitted:
            db = get_cached_db()
            try:
                with st.spinner("Memproses..."):
                    result = request_password_reset(db, email)
            finally:
                db.close()
            if result == "invalid_email":
                st.error("Format email tidak valid.")
            elif result == "unavailable":
                st.info("Reset password lewat email belum diaktifkan. Hubungi admin.")
            else:
                st.success("Jika email tersebut terdaftar, tautan reset sudah dikirim dan berlaku 30 menit. "
                           "Tidak menerima email dalam beberapa menit? Periksa folder spam atau hubungi admin.")
    if st.button("Kembali ke halaman masuk", type="tertiary"):
        st.session_state.pop("auth_view", None)
        st.rerun()


def render_reset(raw_token):
    from core.password_reset import check_token, reset_password_with_token
    from core.auth import MIN_PASSWORD_LENGTH
    _auth_header("Buat password baru")
    db = get_cached_db()
    try:
        _, status = check_token(db, raw_token)
        if status != "valid":
            messages = {
                "expired": "Tautan reset sudah kedaluwarsa. Minta tautan baru.",
                "used": "Tautan reset ini sudah dipakai. Minta tautan baru jika masih perlu.",
            }
            st.error(messages.get(status, "Tautan reset tidak valid. Pastikan Anda membuka tautan lengkap dari email."))
            if st.button("Minta tautan baru", type="primary", width="stretch"):
                st.query_params.clear()
                st.session_state.auth_view = "forgot"
                st.rerun()
            return

        with st.form("reset_form", border=True):
            st.caption(f"Minimal {MIN_PASSWORD_LENGTH} karakter, berisi huruf dan angka.")
            new_pw = st.text_input("Password baru", type="password", autocomplete="new-password")
            confirm = st.text_input("Ulangi password baru", type="password", autocomplete="new-password")
            submitted = st.form_submit_button("Simpan password", type="primary", width="stretch")
        if submitted:
            ok, msg = reset_password_with_token(db, raw_token, new_pw, confirm)
            if ok:
                st.query_params.clear()
                st.session_state.auth_flash = "Password berhasil diubah. Silakan masuk dengan password baru."
                st.rerun()
            elif msg in ("expired", "used", "invalid"):
                st.error("Tautan tidak berlaku lagi. Minta tautan baru.")
            else:
                st.error(msg)
    finally:
        db.close()

    if st.button("Kembali ke halaman masuk", type="tertiary"):
        st.query_params.clear()
        st.rerun()


if not st.session_state.user_id:
    apply_auth_styles()
    _slot = st.empty()
    with db_guard(_slot), _slot.container():
        reset_token = st.query_params.get("reset_token")
        if reset_token:
            render_reset(reset_token)
        elif st.session_state.get("auth_view") == "forgot":
            render_forgot()
        elif st.session_state.get("auth_view") == "setup":
            render_setup()
        else:
            render_login()
    install_client_hooks()
    st.stop()


# ---------------------------------------------------------------------------
# Forced password change (admin reset / known default password)
# ---------------------------------------------------------------------------
def render_forced_password_change():
    from core.auth import MIN_PASSWORD_LENGTH
    apply_auth_styles()
    _auth_header("Ganti password", "Password Anda adalah password sementara atau password default. "
                                   "Buat password baru untuk melanjutkan.")
    with st.form("forced_pw_form", border=True):
        st.caption(f"Minimal {MIN_PASSWORD_LENGTH} karakter, berisi huruf dan angka.")
        current = st.text_input("Password saat ini", type="password", autocomplete="current-password")
        new_pw = st.text_input("Password baru", type="password", autocomplete="new-password")
        confirm = st.text_input("Ulangi password baru", type="password", autocomplete="new-password")
        submitted = st.form_submit_button("Simpan dan lanjutkan", type="primary", width="stretch")
    if submitted:
        db = get_cached_db()
        try:
            user = db.query(User).filter(User.id == st.session_state.user_id).first()
            error = validate_new_password(new_pw, confirm)
            if not user or not verify_password(current, user.password_hash):
                st.error("Password saat ini salah.")
            elif error:
                st.error(error)
            elif new_pw == current:
                st.error("Password baru harus berbeda dari password saat ini.")
            else:
                set_user_password(db, user, new_pw, must_change=False)
                st.session_state.must_change_password = False
                st.rerun()
        finally:
            db.close()
    if st.button("Keluar", type="tertiary"):
        session_mgr.logout()
        st.session_state.clear()
        st.rerun()


if st.session_state.get("must_change_password"):
    _slot = st.empty()
    with db_guard(_slot), _slot.container():
        render_forced_password_change()
    install_client_hooks()
    st.stop()


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
if "user_is_admin" not in st.session_state or st.session_state.get("pages_dict_role") != st.session_state.role:
    _db = get_cached_db()
    try:
        with db_guard():
            st.session_state.user_is_admin = bool(is_admin(_db))
    finally:
        _db.close()
    st.session_state.pages_dict_role = st.session_state.role
user_is_admin = st.session_state.user_is_admin


def _page(module, func, title, icon, url_path, default=False):
    def render():
        run_page(lambda: getattr(importlib.import_module(module), func)(), is_admin_user=user_is_admin)
    render.__name__ = f"page_{url_path.replace('-', '_')}"
    return st.Page(render, title=title, icon=f":material/{icon}:", url_path=url_path, default=default)


sections = {
    "Ringkasan": [
        _page("pages.dashboard", "show_dashboard", "Dashboard", "space_dashboard", "dashboard", default=True),
    ],
    "FPTK": [
        _page("pages.02_upload_compile", "show_upload_compile", "Input FPTK", "upload_file", "input-fptk"),
        _page("pages.03_fptk_view", "show_fptk_view", "Database FPTK", "table_view", "fptk"),
        _page("pages.11_update_progres", "show_update_progres", "Progres Rekrutmen", "edit_note", "progres"),
        _page("pages.05_db_kode_posisi", "show_db_kode_posisi", "Kode Posisi", "badge", "kode-posisi"),
    ],
    "Sourcing": [
        _page("pages.09_sourcing_input", "show_sourcing_input", "Input Kandidat", "person_add", "input-kandidat"),
        _page("pages.04_sourcing_view", "show_sourcing_view", "Database Kandidat", "group", "kandidat"),
    ],
    "Laporan": [
        _page("pages.funnel_report", "show_funnel_report", "Funnel Report", "filter_alt", "funnel"),
        _page("pages.monitoring_sourcing", "show_monitoring_sourcing", "Monitoring & Evidence", "monitoring", "monitoring"),
    ],
}
if user_is_admin:
    sections["Admin"] = [
        _page("pages.07_user_management", "show_user_management", "Pengguna", "manage_accounts", "pengguna"),
        _page("pages.10_admin_delete_requests", "show_admin_delete_requests", "Permintaan", "inbox", "permintaan"),
        _page("pages.export_data", "show_export_data", "Export Data", "download", "export"),
    ]

st.logo(LOGO_PATH, size="large")
current = st.navigation(sections, position="sidebar")


# ---------------------------------------------------------------------------
# Sidebar: account block
# ---------------------------------------------------------------------------
with st.sidebar:
    role_label = {"admin": "Admin", "user": "Recruiter", "it": "IT (lihat saja)"}.get(
        st.session_state.role, st.session_state.role)
    remaining = session_mgr.get_idle_remaining_seconds()
    st.markdown(
        f'<p class="acct-name">{html.escape(str(st.session_state.user_display))}</p>'
        f'<p class="acct-meta">{role_label} · keluar otomatis setelah 30 menit tidak aktif</p>',
        unsafe_allow_html=True,
    )
    if 0 < remaining < 300:
        st.caption(f"Sesi berakhir dalam {remaining // 60}m {remaining % 60}s")

    if st.button("Muat ulang data", icon=":material/refresh:", width="stretch",
                 help="Ambil data terbaru dari database"):
        st.cache_data.clear()
        st.session_state.last_fptk_load = datetime.now()
        st.session_state.last_sourcing_load = datetime.now()
        st.toast("Data dimuat ulang.")
        st.rerun()

    if not is_demo():
        with st.expander("Ganti password", icon=":material/key:"):
            with st.form("change_password", border=False):
                old = st.text_input("Password saat ini", type="password", autocomplete="current-password")
                new = st.text_input("Password baru", type="password", autocomplete="new-password")
                confirm = st.text_input("Ulangi password baru", type="password", autocomplete="new-password")
                if st.form_submit_button("Simpan", width="stretch"):
                    db = get_cached_db()
                    try:
                        user = db.query(User).filter(User.id == st.session_state.user_id).first()
                        error = validate_new_password(new, confirm)
                        if not user or not verify_password(old, user.password_hash):
                            st.error("Password saat ini salah.")
                        elif error:
                            st.error(error)
                        else:
                            set_user_password(db, user, new, must_change=False)
                            st.success("Password berhasil diubah.")
                    except SQLAlchemyError:
                        log.exception("Change password failed: database error")
                        st.warning("Database sedang tidak dapat dihubungi. Password belum diubah; coba lagi.")
                    finally:
                        db.close()

    if st.button("Keluar", icon=":material/logout:", width="stretch"):
        session_mgr.logout()
        st.session_state.clear()
        st.rerun()

    install_client_hooks()


current.run()
