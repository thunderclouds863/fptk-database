import streamlit as st

class SessionManager:
    def __init__(self):
        self._init_session()

    def _init_session(self):
        if "user_id" not in st.session_state:
            st.session_state.user_id = None
        if "username" not in st.session_state:
            st.session_state.username = None
        if "role" not in st.session_state:
            st.session_state.role = None
        if "user_display" not in st.session_state:
            st.session_state.user_display = None
        if "is_logged_in" not in st.session_state:
            st.session_state.is_logged_in = False

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

    @property
    def is_logged_in(self):
        return st.session_state.is_logged_in

    def login(self, user_id, username, role, display_name):
        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.user_display = display_name
        st.session_state.is_logged_in = True

    def logout(self):
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.user_display = None
        st.session_state.is_logged_in = False

    def is_admin(self):
        return self.role == "admin"

    def is_user(self):
        return self.role == "user"

    def is_it(self):
        return self.role == "it"

# Singleton
_session_manager = None

def get_session_manager():
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
