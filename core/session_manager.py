import streamlit as st
from core.database import SessionLocal
from core.models import User

@st.cache_resource
def get_session_manager():
    """Cache session manager untuk persistent login"""
    return SessionManager()

class SessionManager:
    def __init__(self):
        self._user_id = None
        self._username = None
        self._role = None
        self._user_display = None
    
    def login(self, user_id, username, role, display_name):
        self._user_id = user_id
        self._username = username
        self._role = role
        self._user_display = display_name
    
    def logout(self):
        self._user_id = None
        self._username = None
        self._role = None
        self._user_display = None
    
    @property
    def is_logged_in(self):
        return self._user_id is not None
    
    @property
    def user_id(self):
        return self._user_id
    
    @property
    def username(self):
        return self._username
    
    @property
    def role(self):
        return self._role
    
    @property
    def user_display(self):
        return self._user_display
