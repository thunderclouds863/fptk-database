import streamlit as st
import importlib
from core.database import SessionLocal, init_db
from core.auth import (
    login_user,
    is_admin,
    init_default_users,
    verify_password,
    hash_password
)
from core.models import User
import time


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
# SESSION STATE
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

    # --------------------------------------------------------
    # LOGIN PAGE CSS
    # --------------------------------------------------------

    st.markdown(
        """
        <style>

        /* ==================================================
           GLOBAL
        ================================================== */

        .stApp {
            background:
                radial-gradient(
                    circle at 50% 35%,
                    rgba(35, 40, 55, 0.35) 0%,
                    rgba(14, 17, 23, 1) 55%
                );
        }


        /* Hide Streamlit header */
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
            padding-top: 60px;
        }


        /* ==================================================
           LOGO
        ================================================== */

        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;

            margin-bottom: 25px;
        }

        .logo-container img {
            width: 220px;
            height: auto;
            object-fit: contain;
        }


        /* ==================================================
           LOGIN CARD
        ================================================== */

        .login-card {
            background: rgba(18, 21, 29, 0.82);

            border: 1px solid rgba(255, 255, 255, 0.15);

            border-radius: 20px;

            padding: 38px 42px 30px 42px;

            box-shadow:
                0 20px 60px rgba(0, 0, 0, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.03);

            backdrop-filter: blur(12px);

            margin-bottom: 20px;
        }


        /* ==================================================
           LOGIN TITLE
        ================================================== */

        .login-title {
            display: flex;
            align-items: center;

            gap: 15px;

            margin-bottom: 28px;
        }

        .login-title .icon {
            font-size: 42px;
            line-height: 1;
        }

        .login-title .text {
            font-size: 38px;
            font-weight: 700;
            color: #f5f5f5;
        }


        /* ==================================================
           STREAMLIT INPUT
        ================================================== */

        div[data-baseweb="input"] {
            background-color: #242731 !important;

            border-radius: 12px !important;

            border: 1px solid transparent !important;
        }

        div[data-baseweb="input"]:focus-within {
            border: 1px solid rgba(255, 255, 255, 0.25) !important;
        }

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

        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {

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


        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {

            background: #ff5c5c;

            transform: translateY(-1px);

            box-shadow:
                0 8px 20px rgba(255, 75, 75, 0.25);
        }


        /* ==================================================
           REMOVE EXTRA FORM BORDER
        ================================================== */

        div[data-testid="stForm"] {
            border: none !important;

            padding: 0 !important;
        }


        /* ==================================================
           ERROR / SUCCESS
        ================================================== */

        div[data-testid="stAlert"] {
            border-radius: 10px;
        }


        /* ==================================================
           MOBILE
        ================================================== */

        @media (max-width: 768px) {

            .login-wrapper {
                padding: 30px 15px 0 15px;
            }

            .login-card {
                padding: 28px 22px 25px 22px;
            }

            .logo-container img {
                width: 170px;
            }

            .login-title .text {
                font-size: 30px;
            }

            .login-title .icon {
                font-size: 34px;
            }
        }

        </style>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # LOGIN WRAPPER
    # --------------------------------------------------------

    st.markdown(
        '<div class="login-wrapper">',
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # LOGO
    # --------------------------------------------------------

    st.markdown(
        '<div class="logo-container">',
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


    # --------------------------------------------------------
    # LOGIN CARD
    # --------------------------------------------------------

    st.markdown(
        '<div class="login-card">',
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # LOGIN TITLE
    # --------------------------------------------------------

    st.markdown(
        """
        <div class="login-title">

            <div class="icon">
                🔐
            </div>

            <div class="text">
                Login
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # LOGIN FORM
    # --------------------------------------------------------

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


        # ----------------------------------------------------
        # LOGIN PROCESS
        # ----------------------------------------------------

        if submitted:

            if not username or not password:

                st.error(
                    "Username dan password wajib diisi!"
                )

            else:

                db = SessionLocal()

                try:

                    user = login_user(
                        db,
                        username,
                        password
                    )

                    if user:

                        st.session_state.user_id = user.id

                        st.session_state.username = user.username

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

                    else:

                        st.error(
                            "❌ Username atau password salah!"
                        )

                finally:

                    db.close()


    # --------------------------------------------------------
    # CLOSE LOGIN CARD
    # --------------------------------------------------------

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # CLOSE LOGIN WRAPPER
    # --------------------------------------------------------

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


    st.stop()


# ============================================================
# SIDEBAR - LOGGED IN
# ============================================================

with st.sidebar:

    st.markdown(
        f"### 👤 {st.session_state.user_display}"
    )

    st.caption(
        f"Role: {st.session_state.role}"
    )

    st.markdown("---")


    # --------------------------------------------------------
    # NAVIGATION
    # --------------------------------------------------------

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


    db = SessionLocal()

    try:

        if is_admin(db):

            pages["🔄 Upload Cycle"] = "upload_cycle"

            pages["👥 User Management"] = "user_management"

    finally:

        db.close()


    selected = st.radio(
        "Navigasi",
        list(pages.keys()),
        index=0
    )

    st.session_state.page = pages[selected]


    st.markdown("---")


    # --------------------------------------------------------
    # CHANGE PASSWORD
    # --------------------------------------------------------

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


                if st.form_submit_button(
                    "Update Password"
                ):

                    if (
                        new
                        and new == confirm
                        and len(new) >= 6
                    ):

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


    st.markdown("---")


    # --------------------------------------------------------
    # LOGOUT
    # --------------------------------------------------------

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


if page == "dashboard":

    dashboard = importlib.import_module(
        "pages.01_dashboard"
    )

    dashboard.show_dashboard()


elif page == "upload_compile":

    upload_compile = importlib.import_module(
        "pages.02_upload_compile"
    )

    upload_compile.show_upload_compile()


elif page == "fptk_view":

    fptk_view = importlib.import_module(
        "pages.03_fptk_view"
    )

    fptk_view.show_fptk_view()


elif page == "sourcing_view":

    sourcing_view = importlib.import_module(
        "pages.04_sourcing_view"
    )

    sourcing_view.show_sourcing_view()


elif page == "db_kode_posisi":

    db_kode_posisi = importlib.import_module(
        "pages.05_db_kode_posisi"
    )

    db_kode_posisi.show_db_kode_posisi()


elif page == "upload_cycle":

    upload_cycle = importlib.import_module(
        "pages.06_upload_cycle"
    )

    upload_cycle.show_upload_cycle()


elif page == "user_management":

    user_management = importlib.import_module(
        "pages.07_user_management"
    )

    user_management.show_user_management()
