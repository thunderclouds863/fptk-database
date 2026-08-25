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
# DATABASE
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
# DEFAULT USER
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

        /* ====================================================
           PAGE BACKGROUND
        ==================================================== */

        .stApp {
            background:
                radial-gradient(
                    ellipse at 50% 20%,
                    #151b29 0%,
                    #0d1119 45%,
                    #080b10 100%
                );

            min-height: 100vh;
        }


        /* ====================================================
           HIDE STREAMLIT HEADER
        ==================================================== */

        header {
            visibility: hidden;
        }


        /* ====================================================
           MAIN CONTAINER
        ==================================================== */

        .block-container {
            padding-top: 30px !important;
            padding-bottom: 50px !important;
        }


        /* ====================================================
           CIMORY LOGO
           TRUE CENTER OF VIEWPORT
        ==================================================== */

        div[data-testid="stImage"] {

            width: 260px !important;

            max-width: 260px !important;

            margin-left: auto !important;

            margin-right: auto !important;

            margin-top: 5px !important;

            margin-bottom: 55px !important;

            padding: 0 !important;

            display: block !important;

            text-align: center !important;

        }


        div[data-testid="stImage"] img {

            width: 260px !important;

            max-width: 260px !important;

            height: auto !important;

            display: block !important;

            margin-left: auto !important;

            margin-right: auto !important;

            object-fit: contain !important;

        }


        /* ====================================================
           LOGIN FORM / CARD
        ==================================================== */

        div[data-testid="stForm"] {

            width: 700px !important;

            max-width: calc(100vw - 40px) !important;

            margin-left: auto !important;

            margin-right: auto !important;

            padding: 42px 42px 38px 42px !important;

            background:
                linear-gradient(
                    145deg,
                    rgba(20, 24, 34, 0.90),
                    rgba(12, 15, 22, 0.90)
                ) !important;

            border:
                1px solid
                rgba(125, 140, 170, 0.28) !important;

            border-radius: 20px !important;

            box-shadow:
                0 25px 70px
                rgba(0, 0, 0, 0.45) !important;

            backdrop-filter: blur(15px);

            -webkit-backdrop-filter: blur(15px);

        }


        /* ====================================================
           LOGIN TITLE
        ==================================================== */

        .login-title {

            display: flex;

            align-items: center;

            gap: 12px;

            color: #f5f7fb;

            font-size: 38px;

            font-weight: 700;

            line-height: 1;

            margin-bottom: 35px;

            letter-spacing: -1px;

        }


        /* ====================================================
           LOGIN ICON
        ==================================================== */

        .login-icon {

            font-size: 30px !important;

            line-height: 1 !important;

            width: 38px;

            height: 38px;

            display: flex;

            align-items: center;

            justify-content: center;

        }


        /* ====================================================
           LABEL
        ==================================================== */

        div[data-testid="stTextInput"] label {

            color: #f1f3f7 !important;

            font-size: 16px !important;

            font-weight: 600 !important;

            margin-bottom: 8px !important;

        }


        /* ====================================================
           INPUT
        ==================================================== */

        div[data-baseweb="input"] {

            height: 58px !important;

            background:
                linear-gradient(
                    145deg,
                    #242731,
                    #1e212b
                ) !important;

            border:
                1px solid
                rgba(150, 160, 180, 0.20) !important;

            border-radius: 12px !important;

            transition:
                border 0.2s ease,
                box-shadow 0.2s ease;

        }


        /* ====================================================
           INPUT FOCUS
        ==================================================== */

        div[data-baseweb="input"]:focus-within {

            border:
                1px solid
                rgba(255, 255, 255, 0.38) !important;

            box-shadow:
                0 0 0 2px
                rgba(255, 255, 255, 0.04) !important;

        }


        /* ====================================================
           INPUT TEXT
        ==================================================== */

        div[data-baseweb="input"] input {

            height: 56px !important;

            color: #f5f5f7 !important;

            font-size: 16px !important;

            font-weight: 400 !important;

        }


        div[data-baseweb="input"] input::placeholder {

            color: #a0a3ad !important;

            opacity: 1 !important;

        }


        /* ====================================================
           PASSWORD EYE
        ==================================================== */

        div[data-baseweb="input"] button {

            color: #f4f5f8 !important;

        }


        /* ====================================================
           INPUT SPACING
        ==================================================== */

        div[data-testid="stTextInput"] {

            margin-bottom: 20px;

        }


        /* ====================================================
           LOGIN BUTTON
        ==================================================== */

        div[data-testid="stFormSubmitButton"] {

            margin-top: 8px !important;

        }


        div[data-testid="stFormSubmitButton"] button {

            width: 100% !important;

            height: 62px !important;

            border: none !important;

            border-radius: 13px !important;

            background:
                linear-gradient(
                    90deg,
                    #ff3d48,
                    #ff4d54
                ) !important;

            color: white !important;

            font-size: 18px !important;

            font-weight: 700 !important;

            transition:
                transform 0.15s ease,
                box-shadow 0.15s ease;

        }


        /* ====================================================
           BUTTON HOVER
        ==================================================== */

        div[data-testid="stFormSubmitButton"] button:hover {

            background:
                linear-gradient(
                    90deg,
                    #ff4751,
                    #ff5960
                ) !important;

            transform: translateY(-1px);

            box-shadow:
                0 10px 25px
                rgba(255, 60, 70, 0.25);

        }


        /* ====================================================
           BUTTON ACTIVE
        ==================================================== */

        div[data-testid="stFormSubmitButton"] button:active {

            transform: translateY(0);

        }


        /* ====================================================
           MOBILE
        ==================================================== */

        @media (max-width: 768px) {

            .block-container {

                padding-left: 15px !important;

                padding-right: 15px !important;

                padding-top: 20px !important;

            }


            div[data-testid="stImage"] {

                width: 220px !important;

                max-width: 220px !important;

                margin-bottom: 35px !important;

            }


            div[data-testid="stImage"] img {

                width: 220px !important;

                max-width: 220px !important;

            }


            div[data-testid="stForm"] {

                width: auto !important;

                max-width: calc(100vw - 30px) !important;

                padding:
                    30px 22px 28px 22px !important;

                border-radius: 17px !important;

            }


            .login-title {

                font-size: 32px;

                gap: 10px;

            }


            .login-icon {

                font-size: 26px !important;

                width: 34px;

                height: 34px;

            }


            div[data-baseweb="input"] {

                height: 56px !important;

            }


            div[data-baseweb="input"] input {

                height: 54px !important;

                font-size: 15px !important;

            }


            div[data-testid="stFormSubmitButton"] button {

                height: 56px !important;

            }

        }

        </style>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # CIMORY LOGO
    # ========================================================

    st.image(
        "asset/cimory_logo.png"
    )


    # ========================================================
    # LOGIN FORM
    # ========================================================

    with st.form("login_form"):

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        st.markdown(
            """
            <div class="login-title">
                <span class="login-icon">🔐</span>
                <span>Login</span>
            </div>
            """,
            unsafe_allow_html=True
        )


        # ----------------------------------------------------
        # USERNAME
        # ----------------------------------------------------

        username = st.text_input(
            "Username",
            placeholder="Masukkan username"
        )


        # ----------------------------------------------------
        # PASSWORD
        # ----------------------------------------------------

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Masukkan password"
        )


        # ----------------------------------------------------
        # BUTTON
        # ----------------------------------------------------

        submitted = st.form_submit_button(
            "Login  →",
            use_container_width=True
        )


        # ====================================================
        # LOGIN PROCESS
        # ====================================================

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

                    else:

                        st.error(
                            "❌ Username atau password salah!"
                        )

                finally:

                    db.close()


    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

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
    # ADMIN MENU
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
    # NAVIGATION
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
# PAGE RENDERING
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
