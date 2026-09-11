import streamlit as st
from datetime import datetime, timedelta
from core.database import SessionLocal
from core.models import User


# ============================================================
# CONFIG
# ============================================================

IDLE_TIMEOUT_MINUTES = 30
IDLE_TIMEOUT_SECONDS = IDLE_TIMEOUT_MINUTES * 60


# ============================================================
# SESSION MANAGER
# ============================================================

def get_session_manager():
    """Session manager per browser/user."""
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = SessionManager()
    return st.session_state.session_manager


class SessionManager:

    def __init__(self):
        self._init_state()

    def _init_state(self):
        """Inisialisasi session state."""
        defaults = {
            "user_id": None,
            "username": None,
            "role": None,
            "user_display": None,
            "last_activity": None,
            "current_page": "dashboard",
        }
        for key, val in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = val

    def login(self, user_id, username, role, display_name):
        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.user_display = display_name
        st.session_state.last_activity = datetime.now()
        st.session_state.current_page = "dashboard"

    def logout(self):
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.user_display = None
        st.session_state.last_activity = None
        st.session_state.current_page = "dashboard"

    def touch(self):
        if self.is_logged_in:
            st.session_state.last_activity = datetime.now()

    def set_page(self, page_key):
        st.session_state.current_page = page_key

    @property
    def current_page(self):
        return st.session_state.get("current_page", "dashboard")

    def is_idle_expired(self):
        if not self.is_logged_in:
            return False
        last = st.session_state.get("last_activity")
        if not last:
            return True
        return (datetime.now() - last) > timedelta(minutes=IDLE_TIMEOUT_MINUTES)

    def get_idle_remaining_seconds(self):
        if not self.is_logged_in:
            return 0
        last = st.session_state.get("last_activity")
        if not last:
            return 0
        elapsed = (datetime.now() - last).total_seconds()
        return max(0, int(IDLE_TIMEOUT_SECONDS - elapsed))

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
# HELPERS
# ============================================================

def login_user(user_id, username, role, display_name):
    get_session_manager().login(user_id, username, role, display_name)


def logout_user():
    get_session_manager().logout()


def get_current_user(db):
    session = get_session_manager()
    if not session.is_logged_in:
        return None
    return db.query(User).filter(User.id == session.user_id).first()


def is_logged_in():
    return get_session_manager().is_logged_in


def get_current_role():
    return get_session_manager().role


def get_current_user_id():
    return get_session_manager().user_id


def check_idle_timeout():
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
    session = get_session_manager()
    if session.is_logged_in:
        session.touch()
