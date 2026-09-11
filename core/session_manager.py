import streamlit as st
from datetime import datetime, timedelta
from core.database import SessionLocal
from core.models import User


# ============================================================
# CONFIG
# ============================================================

# Idle timeout dalam menit — setelah ini user auto-logout
IDLE_TIMEOUT_MINUTES = 30
IDLE_TIMEOUT_SECONDS = IDLE_TIMEOUT_MINUTES * 60  # 1800 detik


# ============================================================
# SESSION MANAGER
# ============================================================

def get_session_manager():
    """
    Session manager per browser/user.
    Jangan gunakan st.cache_resource karena sifatnya global
    dan akan share login antar user.
    """
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = SessionManager()
    return st.session_state.session_manager


class SessionManager:

    def __init__(self):
        self._init_state()

    def _init_state(self):
        """Inisialisasi session state."""
        if "user_id" not in st.session_state:
            st.session_state.user_id = None

        if "username" not in st.session_state:
            st.session_state.username = None

        if "role" not in st.session_state:
            st.session_state.role = None

        if "user_display" not in st.session_state:
            st.session_state.user_display = None

        # Timestamp aktivitas terakhir
        if "last_activity" not in st.session_state:
            st.session_state.last_activity = None

        # ⚠️ Track halaman aktif biar gak reset ke dashboard
        if "current_page" not in st.session_state:
            st.session_state.current_page = "dashboard"

    # ------------------------------------------------------------
    # LOGIN / LOGOUT
    # ------------------------------------------------------------

    def login(self, user_id, username, role, display_name):
        """Simpan login user + set waktu aktivitas."""
        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.user_display = display_name
        st.session_state.last_activity = datetime.now()
        # Reset ke dashboard saat login baru
        st.session_state.current_page = "dashboard"

    def logout(self):
        """Hapus session login."""
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.user_display = None
        st.session_state.last_activity = None
        st.session_state.current_page = "dashboard"

    def touch(self):
        """Update waktu aktivitas terakhir."""
        if self.is_logged_in:
            st.session_state.last_activity = datetime.now()

    # ------------------------------------------------------------
    # PAGE TRACKING
    # ------------------------------------------------------------

    def set_page(self, page_key):
        """Simpan halaman aktif."""
        st.session_state.current_page = page_key

    @property
    def current_page(self):
        return st.session_state.get("current_page", "dashboard")

    # ------------------------------------------------------------
    # IDLE TIMEOUT
    # ------------------------------------------------------------

    def is_idle_expired(self):
        """Cek apakah user sudah idle lebih dari IDLE_TIMEOUT_MINUTES."""
        if not self.is_logged_in:
            return False

        last = st.session_state.get("last_activity")
        if not last:
            return True

        idle_duration = datetime.now() - last
        return idle_duration > timedelta(minutes=IDLE_TIMEOUT_MINUTES)

    def get_idle_remaining_seconds(self):
        """Sisa waktu sebelum auto-logout (dalam detik)."""
        if not self.is_logged_in:
            return 0

        last = st.session_state.get("last_activity")
        if not last:
            return 0

        elapsed = (datetime.now() - last).total_seconds()
        return max(0, int(IDLE_TIMEOUT_SECONDS - elapsed))

    # ------------------------------------------------------------
    # PROPERTIES
    # ------------------------------------------------------------

    @property
    def is_logged_in(self):
        return st.session_state.get("user_id") is not None

    @property
    def user_id(self):
        return st.session_state.get("user_id")

    @property
    def username(self):
        return st.session_state.get("username")

    @property
    def role(self):
        return st.session_state.get("role")

    @property
    def user_display(self):
        return st.session_state.get("user_display")


# ============================================================
# HELPER LOGIN
# ============================================================

def login_user(user_id, username, role, display_name):
    session = get_session_manager()
    session.login(user_id, username, role, display_name)


def logout_user():
    session = get_session_manager()
    session.logout()


def get_current_user(db):
    """Ambil user dari session."""
    session = get_session_manager()
    if not session.is_logged_in:
        return None
    user = db.query(User).filter(User.id == session.user_id).first()
    return user


def is_logged_in():
    session = get_session_manager()
    return session.is_logged_in


def get_current_role():
    session = get_session_manager()
    return session.role


def get_current_user_id():
    session = get_session_manager()
    return session.user_id


# ============================================================
# IDLE TIMEOUT HELPERS
# ============================================================

def check_idle_timeout():
    """
    Cek idle timeout. Kalau expired:
    - Clear session
    - Set flag di session_state supaya bisa tampilkan pesan
    - Return True kalau expired
    """
    session = get_session_manager()

    if not session.is_logged_in:
        return False

    if session.is_idle_expired():
        st.session_state.session_expired_username = st.session_state.get("username", "")
        session.logout()
        st.session_state.session_expired_message = (
            f"⏰ Session expired karena tidak ada aktivitas selama "
            f"{IDLE_TIMEOUT_MINUTES} menit. Silakan login lagi."
        )
        return True

    return False


def touch_session():
    """
    Update last_activity untuk reset idle timer.
    Panggil setiap kali user interaksi (klik, submit, dll).
    """
    session = get_session_manager()
    if session.is_logged_in:
        session.touch()
