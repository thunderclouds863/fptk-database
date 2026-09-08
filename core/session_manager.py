import streamlit as st
from core.database import SessionLocal
from core.models import User
import time

def get_session_manager():
    """
    Session manager per browser/user.
    Gunakan session_state untuk menghindari global state.
    """
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = SessionManager()
    
    return st.session_state.session_manager


class SessionManager:
    def __init__(self):
        self._init_state()
    
    def _init_state(self):
        """Inisialisasi session state dengan default values"""
        defaults = {
            "user_id": None,
            "username": None,
            "role": None,
            "user_display": None,
            "last_activity": time.time()
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def login(self, user_id, username, role, display_name):
        """Simpan login user ke session browser ini"""
        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.user_display = display_name
        st.session_state.last_activity = time.time()
    
    def logout(self):
        """Hapus session login"""
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.user_display = None
    
    def check_session_timeout(self, timeout_seconds=3600):  # 1 jam timeout
        """Cek apakah session sudah timeout"""
        if self.is_logged_in:
            last_activity = st.session_state.get("last_activity", time.time())
            if time.time() - last_activity > timeout_seconds:
                self.logout()
                return True
            # Update last activity
            st.session_state.last_activity = time.time()
        return False
    
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
# HELPER FUNCTIONS - OPTIMASI DENGAN CACHING
# ============================================================

@st.cache_data(ttl=300)  # Cache 5 menit
def get_user_by_id(db, user_id):
    """Cache user query untuk mengurangi query database"""
    return db.query(User).filter(User.id == user_id).first()


def get_current_user(db):
    """Get current user dengan cache"""
    session = get_session_manager()
    if not session.is_logged_in:
        return None
    
    # Cek timeout
    if session.check_session_timeout():
        return None
    
    return get_user_by_id(db, session.user_id)


def is_logged_in():
    session = get_session_manager()
    if session.check_session_timeout():
        return False
    return session.is_logged_in


def get_current_role():
    session = get_session_manager()
    return session.role if session.is_logged_in else None


def get_current_user_id():
    session = get_session_manager()
    return session.user_id if session.is_logged_in else None
