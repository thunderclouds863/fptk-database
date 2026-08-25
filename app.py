import streamlit as st
import importlib
import time

from core.database import SessionLocal, init_db
from core.auth import (
    login_user,
    is_admin,
    init_default_users,
    verify_password,
    hash_password
)
from core.models import User


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FPTK & Sourcing System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

init_db()


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = None

if "role" not in st.session_state:
    st.session_state.role = None

if "user_display" not in st.session_state:
    st.session_state.user_display = None

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "filter_stack" not in st.session_state:
    st.session_state.filter_stack = []


# ============================================================
# INITIALIZE DEFAULT USERS
# ============================================================

db = SessionLocal()

try:
    init_default_users(db)
finally:
    db.close()


# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.user_id:

    # ========================================================
    # LOGIN CSS
    # ========================================================

    st.markdown(
        """
        <style>

        /* ==================================================
           GLOBAL BACKGROUND
        ================================================== */

        .stApp {
            background:
                radial-gradient(
                    circle at 50% 30%,
                    rgba(35, 40, 55, 0.35),
                    #0e1117 60%
                );
        }

        /* Hide Streamlit top header */
        header {
            visibility: hidden;
        }


        /* ==================================================
           LOGIN WRAPPER
        ================================================== */

        .login-wrapper {
            width: 100%;
            max-width: 850px;
            margin: 0 auto;
            padding-top: 40px;
        }


        /* ==================================================
           LOGO
        ================================================== */

        .logo-wrapper {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 15px;
        }


        /* ==================================================
           LOGIN TITLE
        ================================================== */

        .login-title {
            text-align: center;
            color: #f5f5f5;
            font-size: 38px;
            font-weight: 700;
            margin-top: 0;
            margin-bottom: 25px;
        }


        /* ==================================================
           LOGIN FORM CARD
        ================================================== */

        div[data-testid="stForm"] {
            background: rgba(18, 21, 29, 0.88);

            border: 1px solid rgba(255, 255, 255, 0.15);

            border-radius: 20px;

            padding: 35px 40px 30px 40px;

            box-shadow:
                0 20px 60px rgba(0, 0, 0, 0.35);

            backdrop-filter: blur(12px);
        }


        /* ==================================================
           INPUT CONTAINER
        ================================================== */

        div[data-baseweb="input"] {
            background-color: #242731 !important;

            border-radius: 12px !important;

            border: 1px solid transparent !important;
        }


        div[data-baseweb="input"]:focus-within {
            border: 1px solid rgba(255, 255, 255, 0.25)
                !important;
        }


        /* ==================================================
           INPUT TEXT
        ================================================== */

        div[data-baseweb="input"] input {
            color: #ffffff !important;

            font-size: 16px !important;
        }


        div[data-baseweb="input"] input::placeholder {
            color: #9b9da7 !important;
        }


        /* ==================================================
           LABEL
        ================================================== */

        div[data-testid="stTextInput"] label {
            color: #eeeeee !important;

            font-size: 16px !important;

            font-weight: 500 !important;
        }


        /* ==================================================
           LOGIN BUTTON
        ================================================== */

        div[data-testid="stFormSubmitButton"] button {
            width: 100%;

            min-height: 52px;

            border-radius: 12px;

            border: none;

            background: #ff4b4b;

            color: white;

            font-size: 17px;

            font-weight: 600;

            transition: all 0.2s ease;
        }


        div[data-testid="stFormSubmitButton"] button:hover {
            background: #ff5c5c;

            transform: translateY(-1px);

            box-shadow:
                0 8px 20px rgba(255, 75, 75, 0.25);
        }


        /* ==================================================
           ALERT
        ================================================== */

        div[data-testid="stAlert"] {
            border-radius: 10px;
        }


        /* ==================================================
           MOBILE
        ================================================== */

        @media (max-width: 768px) {

            .login-wrapper {
                padding: 25px 15px 0 15px;
            }

            div[data-testid="stForm"] {
                padding: 25px 20px;
            }

            .login-title {
                font-size: 30px;
            }

        }

        </style>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # LOGIN WRAPPER
    # ========================================================

    st.markdown(
        '<div class="login-wrapper">',
        unsafe_allow_html=True
    )


    # ========================================================
    # CIMORY LOGO
    # ========================================================

    logo_col1, logo_col2, logo_col3 = st.columns(
        [1, 2, 1]
    )

    with logo_col2:

        st.markdown(
            '<div class="logo-wrapper">',
            unsafe_allow_html=True
        )

        st.image(
            "asset/cimory_logo.png",
            width=220
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


    # ========================================================
    # LOGIN TITLE
    # ========================================================

    st.markdown(
        """
        <div class="login-title">
            🔐 Login
        </div>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # LOGIN FORM
    # ========================================================

    with st.form("login_form"):

        username = st.text_input(
            "Username",
            placeholder="Masukkan username"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Masukkan password"
        )

        submitted = st.form_submit_button(
            "Login",
            use_container_width=True
        )


        # ====================================================
        # LOGIN PROCESS
        # ====================================================

        if submitted:

            # -----------------------------------------------
            # EMPTY INPUT
            # -----------------------------------------------

            if not username or not password:

                st.error(
                    "Username dan password wajib diisi!"
                )

            else:

                db = SessionLocal()

                try:

                    # ---------------------------------------
                    # AUTHENTICATION
                    # ---------------------------------------

                    user = login_user(
                        db,
                        username,
                        password
                    )


                    # ---------------------------------------
                    # LOGIN SUCCESS
                    # ---------------------------------------

                    if user:

                        st.session_state.user_id = user.id

                        st.session_state.username = (
                            user.username
                        )

                        st.session_state.role = user.role

                        st.session_state.user_display = (
                            user.display_name
                            or user.username
                        )

                        st.success(
                            f"✅ Selamat datang, "
                            f"{st.session_state.user_display}!"
                        )

                        time.sleep(0.5)

                        st.rerun()


                    # ---------------------------------------
                    # LOGIN FAILED
                    # ---------------------------------------

                    else:

                        st.error(
                            "❌ Username atau password salah!"
                        )

                finally:

                    db.close()


    # ========================================================
    # CLOSE LOGIN WRAPPER
    # ========================================================

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


    # ========================================================
    # STOP APP
    # ========================================================

    st.stop()


# ============================================================
# SIDEBAR - LOGGED IN USER
# ============================================================

with st.sidebar:

    # ========================================================
    # USER INFORMATION
    # ========================================================

    st.markdown(
        f"### 👤 {st.session_state.user_display}"
    )

    st.caption(
        f"Role: {st.session_state.role}"
    )

    st.markdown("---")


    # ========================================================
    # NAVIGATION
    # ========================================================

    pages = {

        "📊 Dashboard":
            "dashboard",

        "📤 Upload & Compile":
            "upload_compile",

        "📋 FPTK View":
            "fptk_view",

        "👤 Sourcing View":
            "sourcing_view",

        "🏢 DB Kode Posisi":
            "db_kode_posisi",
    }


    # ========================================================
    # CHECK ADMIN ACCESS
    # ========================================================

    db = SessionLocal()

    try:

        if is_admin(db):

            pages["🔄 Upload Cycle"] = (
                "upload_cycle"
            )

            pages["👥 User Management"] = (
                "user_management"
            )

    finally:

        db.close()


    # ========================================================
    # NAVIGATION RADIO
    # ========================================================

    selected = st.radio(
        "Navigasi",
        list(pages.keys()),
        index=0
    )

    st.session_state.page = pages[selected]

    st.markdown("---")


    # ========================================================
    # CHANGE PASSWORD
    # ========================================================

    with st.expander("🔑 Ganti Password"):

        with st.form("change_password"):

            db = SessionLocal()

            try:

                user = (
                    db.query(User)
                    .filter(
                        User.id
                        == st.session_state.user_id
                    )
                    .first()
                )


                old = st.text_input(
                    "Password Lama",
                    type="password"
                )


                new = st.text_input(
                    "Password Baru (min 6 karakter)",
                    type="password"
                )


                confirm = st.text_input(
                    "Konfirmasi",
                    type="password"
                )


                update_password = (
                    st.form_submit_button(
                        "Update Password"
                    )
                )


                if update_password:

                    # ---------------------------------------
                    # VALIDATE NEW PASSWORD
                    # ---------------------------------------

                    if (
                        new
                        and new == confirm
                        and len(new) >= 6
                    ):

                        # -----------------------------------
                        # VERIFY OLD PASSWORD
                        # -----------------------------------

                        if (
                            user
                            and verify_password(
                                old,
                                user.password_hash
                            )
                        ):

                            user.password_hash = (
                                hash_password(new)
                            )

                            db.commit()

                            st.success(
                                "✅ Password berhasil diubah!"
                            )

                        else:

                            st.error(
                                "❌ Password lama salah!"
                            )

                    else:

                        st.error(
                            "Password baru minimal 6 "
                            "karakter dan harus sama!"
                        )

            finally:

                db.close()


    # ========================================================
    # LOGOUT
    # ========================================================

    st.markdown("---")

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        st.session_state.clear()

        st.rerun()


# ============================================================
# RENDER PAGE
# ============================================================

page = st.session_state.page


# ============================================================
# DASHBOARD
# ============================================================

if page == "dashboard":

    dashboard = importlib.import_module(
        "pages.01_dashboard"
    )

    dashboard.show_dashboard()


# ============================================================
# UPLOAD & COMPILE
# ============================================================

elif page == "upload_compile":

    upload_compile = importlib.import_module(
        "pages.02_upload_compile"
    )

    upload_compile.show_upload_compile()


# ============================================================
# FPTK VIEW
# ============================================================

elif page == "fptk_view":

    fptk_view = importlib.import_module(
        "pages.03_fptk_view"
    )

    fptk_view.show_fptk_view()


# ============================================================
# SOURCING VIEW
# ============================================================

elif page == "sourcing_view":

    sourcing_view = importlib.import_module(
        "pages.04_sourcing_view"
    )

    sourcing_view.show_sourcing_view()


# ============================================================
# DB KODE POSISI
# ============================================================

elif page == "db_kode_posisi":

    db_kode_posisi = importlib.import_module(
        "pages.05_db_kode_posisi"
    )

    db_kode_posisi.show_db_kode_posisi()


# ============================================================
# UPLOAD CYCLE
# ============================================================

elif page == "upload_cycle":

    upload_cycle = importlib.import_module(
        "pages.06_upload_cycle"
    )

    upload_cycle.show_upload_cycle()


# ============================================================
# USER MANAGEMENT
# ============================================================

elif page == "user_management":

    user_management = importlib.import_module(
        "pages.07_user_management"
    )

    user_management.show_user_management()
