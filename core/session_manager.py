import streamlit as st
from core.database import SessionLocal
from core.models import User


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
        """
        Inisialisasi session state.
        Setiap browser punya state sendiri.
        """

        if "user_id" not in st.session_state:
            st.session_state.user_id = None

        if "username" not in st.session_state:
            st.session_state.username = None

        if "role" not in st.session_state:
            st.session_state.role = None

        if "user_display" not in st.session_state:
            st.session_state.user_display = None


    def login(
        self,
        user_id,
        username,
        role,
        display_name
    ):
        """
        Simpan login user ke session browser ini.
        """

        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.user_display = display_name



    def logout(self):
        """
        Hapus session login.
        """

        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.user_display = None



    @property
    def is_logged_in(self):
        return (
            st.session_state.user_id
            is not None
        )


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

def login_user(
    user_id,
    username,
    role,
    display_name
):
    session = get_session_manager()

    session.login(
        user_id=user_id,
        username=username,
        role=role,
        display_name=display_name
    )



def logout_user():

    session = get_session_manager()

    session.logout()



def get_current_user(db):

    session = get_session_manager()

    if not session.is_logged_in:
        return None

    user = db.query(User).filter(
        User.id == session.user_id
    ).first()

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
