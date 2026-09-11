import streamlit as st
from datetime import datetime, timedelta
from core.database import SessionLocal
from core.models import User


# ============================================================
# CONFIG
# ============================================================

# Idle timeout dalam menit
IDLE_TIMEOUT_MINUTES = 30


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

        # ⭐ BARU: timestamp aktivitas terakhir
        if "last_activity" not in st.session_state:
            st.session_state.last_activity = None

    def login(self, user_id, username, role, display_name):
        """Simpan login user + set waktu aktivitas."""

        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.user_display = display_name
        st.session_state.last_activity = datetime.now()

    def logout(self):
        """Hapus session login."""

        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.user_display = None
        st.session_state.last_activity = None

    def touch(self):
        """Update waktu aktivitas terakhir. Dipanggil setiap interaksi."""
        if self.is_logged_in:
            st.session_state.last_activity = datetime.now()

    def is_idle_expired(self):
        """
        Cek apakah user sudah idle lebih dari IDLE_TIMEOUT_MINUTES.
        Return True kalau expired.
        """

        if not self.is_logged_in:
            return False

        last = st.session_state.get("last_activity")
        if not last:
            # Kalau gak ada timestamp, anggap expired
            return True

        # Cek idle
        idle_duration = datetime.now() - last
        return idle_duration > timedelta(minutes=IDLE_TIMEOUT_MINUTES)

    def get_idle_remaining_seconds(self):
        """Sisa waktu sebelum auto-logout (dalam detik)."""

        if not self.is_logged_in:
            return 0

        last = st.session_state.get("last_activity")
        if not last:
            return 0

        elapsed = (datetime.now() - last).seconds
        total = IDLE_TIMEOUT_MINUTES * 60
        return max(0, total - elapsed)

    @property
    def is_logged_in(self):
        return st.session_state.user_id is not None

    @property
    def user_id(self):
        return st.session_state.user_id

    @property
    def username(self):
        return st.session_state.username

    @property
    def role(self):
        return st.session_state.role

    @property
    def user_display(self):
        return st.session_state.user_display


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
# ⭐ BARU: AUTO-LOGOUT CHECKER
# ============================================================

def check_idle_timeout():
    """
    Cek idle timeout. Kalau expired:
    - Clear session
    - Set flag di session_state supaya bisa tampilkan pesan
    - Return True kalau expired

    Panggil fungsi ini di awal app.py setelah login check.
    """

    session = get_session_manager()

    if not session.is_logged_in:
        return False

    if session.is_idle_expired():
        # Simpan info username untuk pesan
        st.session_state.session_expired_username = st.session_state.get("username", "")
        session.logout()
        st.session_state.session_expired_message = (
            f"⏰ Session expired karena tidak ada aktivitas selama "
            f"{IDLE_TIMEOUT_MINUTES} menit. Silakan login lagi."
        )
        return True

    # Update aktivitas setiap kali dipanggil
    session.touch()
    return False
