import streamlit as st
import importlib
import time
import base64
import os
import pandas as pd
from datetime import datetime, timedelta

from core.session_manager import get_session_manager, check_idle_timeout, touch_session
from core.database import SessionLocal, init_db
from core.auth import (
    login_user,
    is_admin,
    init_default_users,
    verify_password,
    hash_password,
    init_master_dropdown
)
from core.models import User


# ============================================================
# PAGE CONFIG - HARUS PALING ATAS
# ============================================================

st.set_page_config(
    page_title="FPTK & Sourcing System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# DATABASE SESSION
# ============================================================

def get_cached_db():
    """Buat session database baru."""
    return SessionLocal()


@st.cache_resource
def initialize_system():
    """Inisialisasi sistem sekali saja."""
    init_db()
    db = SessionLocal()
    try:
        init_default_users(db)
        init_master_dropdown(db)
    finally:
        db.close()
    return True


# Initialize system
if 'system_initialized' not in st.session_state:
    initialize_system()
    st.session_state.system_initialized = True


# ============================================================
# SESSION MANAGER
# ============================================================

session_mgr = get_session_manager()


# ============================================================
# SESSION STATE - FULL INISIALISASI
# ============================================================

if "user_id" not in st.session_state:
    st.session_state.user_id = session_mgr.user_id

if "username" not in st.session_state:
    st.session_state.username = session_mgr.username

if "role" not in st.session_state:
    st.session_state.role = session_mgr.role

if "user_display" not in st.session_state:
    st.session_state.user_display = session_mgr.user_display

# ⚠️ CRITICAL: JANGAN reset page kalau user masih login!
# Cuma set default kalau bener-bener fresh
if "page" not in st.session_state or not st.session_state.page:
    st.session_state.page = session_mgr.current_page or "dashboard"

if "filter_stack" not in st.session_state:
    st.session_state.filter_stack = []

if "detail_id" not in st.session_state:
    st.session_state.detail_id = None

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

if "last_fptk_load" not in st.session_state:
    st.session_state.last_fptk_load = datetime.now()

if "last_sourcing_load" not in st.session_state:
    st.session_state.last_sourcing_load = datetime.now()

if "sort_column" not in st.session_state:
    st.session_state.sort_column = None

if "sort_ascending" not in st.session_state:
    st.session_state.sort_ascending = True

if "date_filter_start" not in st.session_state:
    st.session_state.date_filter_start = None

if "date_filter_end" not in st.session_state:
    st.session_state.date_filter_end = None

if "status_filter" not in st.session_state:
    st.session_state.status_filter = []

if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""

if "filter_applied" not in st.session_state:
    st.session_state.filter_applied = False

if "last_activity" not in st.session_state:
    st.session_state.last_activity = None


# ============================================================
# SESSION PERSISTENCE (SYNC DENGAN SESSION MANAGER)
# ============================================================

if st.session_state.user_id and not session_mgr.is_logged_in:
    session_mgr.login(
        st.session_state.user_id,
        st.session_state.username,
        st.session_state.role,
        st.session_state.user_display
    )

elif not st.session_state.user_id and session_mgr.is_logged_in:
    # ⚠️ JANGAN override page di sini! Biarkan apa adanya.
    st.session_state.user_id = session_mgr.user_id
    st.session_state.username = session_mgr.username
    st.session_state.role = session_mgr.role
    st.session_state.user_display = session_mgr.user_display
    # page TIDAK di-reset


# ============================================================
# IDLE TIMEOUT CHECK + TOUCH SESSION
# ============================================================

if st.session_state.user_id:
    expired = check_idle_timeout()
    if expired:
        st.rerun()
    else:
        # ⚠️ Update last_activity setiap rerun (karena user interact)
        touch_session()


# Tampilkan pesan session expired
if "session_expired_message" in st.session_state and not st.session_state.user_id:
    st.warning(st.session_state.session_expired_message)
    del st.session_state.session_expired_message
    if "session_expired_username" in st.session_state:
        del st.session_state.session_expired_username


# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.user_id:

    @st.cache_data(ttl=3600)
    def load_logo():
        try:
            with open("asset/cimory_logo.png", "rb") as logo_file:
                return base64.b64encode(logo_file.read()).decode("utf-8")
        except FileNotFoundError:
            return ""

    logo_base64 = load_logo()

    st.markdown(
        """
        <style>
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

        header {
            visibility: hidden;
        }

        .block-container {
            padding-top: 30px !important;
            padding-bottom: 50px !important;
        }

        .cimory-logo-container {
            width: 100vw !important;
            max-width: 100vw !important;
            position: relative !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            margin-top: 10px !important;
            margin-bottom: 55px !important;
            padding: 0 !important;
            box-sizing: border-box !important;
            text-align: center !important;
        }

        .cimory-logo {
            width: 260px !important;
            max-width: 260px !important;
            height: auto !important;
            display: block !important;
            margin: 0 auto !important;
            padding: 0 !important;
            object-fit: contain !important;
        }

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
            box-sizing: border-box !important;
        }

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

        .login-icon {
            font-size: 30px !important;
            line-height: 1 !important;
            width: 38px;
            height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        div[data-testid="stTextInput"] label {
            color: #f1f3f7 !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            margin-bottom: 8px !important;
        }

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

        div[data-baseweb="input"]:focus-within {
            border:
                1px solid
                rgba(255, 255, 255, 0.38) !important;
            box-shadow:
                0 0 0 2px
                rgba(255, 255, 255, 0.04) !important;
        }

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

        div[data-baseweb="input"] button {
            color: #f4f5f8 !important;
        }

        div[data-testid="stTextInput"] {
            margin-bottom: 20px;
        }

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

        div[data-testid="stFormSubmitButton"] button:active {
            transform: translateY(0);
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 15px !important;
                padding-right: 15px !important;
                padding-top: 20px !important;
            }

            .cimory-logo-container {
                width: 100vw !important;
                max-width: 100vw !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
                margin-top: 10px !important;
                margin-bottom: 35px !important;
            }

            .cimory-logo {
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

    if logo_base64:
        st.markdown(
            f"""
            <div class="cimory-logo-container">
                <img
                    src="data:image/png;base64,{logo_base64}"
                    class="cimory-logo"
                    alt="Cimory Logo"
                >
            </div>
            """,
            unsafe_allow_html=True
        )

    with st.form("login_form"):

        st.markdown(
            """
            <div class="login-title">
                <span class="login-icon">🔐</span>
                <span>Login</span>
            </div>
            """,
            unsafe_allow_html=True
        )

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
            "Login  →",
            use_container_width=True
        )

        if submitted:
            if not username or not password:
                st.error("Username dan password wajib diisi!")
            else:
                db = get_cached_db()
                try:
                    user = login_user(db, username, password)
                    if user:
                        session_mgr.login(
                            user.id,
                            user.username,
                            user.role,
                            user.display_name or user.username
                        )
                        st.session_state.user_id = user.id
                        st.session_state.username = user.username
                        st.session_state.role = user.role
                        st.session_state.user_display = (
                            user.display_name
                            or user.username
                        )
                        st.session_state.last_activity = datetime.now()
                        # Reset halaman ke dashboard saat login baru
                        st.session_state.page = "dashboard"

                        # Clear pages_dict biar di-rebuild dengan user baru
                        if "pages_dict" in st.session_state:
                            del st.session_state.pages_dict
                        if "user_is_admin" in st.session_state:
                            del st.session_state.user_is_admin

                        st.success(
                            f"✅ Selamat datang, "
                            f"{st.session_state.user_display}!"
                        )
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.error("❌ Username atau password salah!")
                finally:
                    db.close()

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    # ========================================================
    # USER INFO
    # ========================================================

    st.markdown(f"### 👤 {st.session_state.user_display}")
    st.caption(f"Role: {st.session_state.role}")

    # Countdown idle timer
    if session_mgr.is_logged_in:
        remaining = session_mgr.get_idle_remaining_seconds()
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            if remaining < 300:
                st.caption(f"⏰ Auto-logout dalam **{mins}m {secs}s**")
            else:
                st.caption(f"⏰ Auto-logout dalam {mins}m {secs}s")

    st.markdown("---")

    # ========================================================
    # BUILD PAGES DICT — SEKALI SAJA (STABLE)
    # ========================================================

    if "pages_dict" not in st.session_state:

        base_pages = {
            "📊 Dashboard": "dashboard",
            "📤 Upload & Compile FPTK": "upload_compile",
            "📋 FPTK View": "fptk_view",
            "📝 Update Progres Recruitment": "update_progres",
            "👤 Sourcing Input": "sourcing_input",
            "👩🏻‍💻 Sourcing View": "sourcing_view",
            "🏢 DB Kode Posisi": "db_kode_posisi",
            "🔍 Funnel Report": "funnel_report",
            "📊 Monitoring Sourcing": "monitoring_sourcing",
            "📎 Upload Evidence": "upload_evidence",
            "📩 Transfer FPTK": "transfer_fptk",
        }

        # Cek admin SEKALI saja (tanpa cache_data)
        db = get_cached_db()
        try:
            user_is_admin = is_admin(db)
        finally:
            db.close()

        st.session_state["user_is_admin"] = user_is_admin

        if user_is_admin:
            base_pages["🔄 Update Cycle"] = "upload_cycle"
            base_pages["👥 User Management"] = "user_management"
            base_pages["📩 Request Hapus FPTK"] = "admin_delete_requests"

        st.session_state.pages_dict = base_pages

    pages = st.session_state.pages_dict

    # ========================================================
    # NAVIGATION — PAKAI RADIO + KEY (PALING STABIL)
    # ========================================================

    st.markdown("### 📋 Navigasi")

    page_labels = list(pages.keys())
    page_keys = list(pages.values())

    current_page = st.session_state.get("page", "dashboard")

    # Cari index current page
    try:
        current_index = page_keys.index(current_page)
    except ValueError:
        current_index = 0

    # Radio dengan key unik — Streamlit akan manage state sendiri
    selected_label = st.radio(
        "Pilih halaman:",
        options=page_labels,
        index=current_index,
        key="nav_radio_main",  # ⚠️ KEY INI KRUSIAL
        label_visibility="collapsed"
    )

    # Update page HANYA kalau berubah
    selected_page_key = pages[selected_label]
    if selected_page_key != st.session_state.page:
        st.session_state.page = selected_page_key
        session_mgr.set_page(selected_page_key)
        st.rerun()

    st.markdown("---")

    # ========================================================
    # CACHE CONTROL
    # ========================================================

    st.markdown("### ⚡ Cache Control")

    def get_cache_functions():
        try:
            from pages.dashboard import (
                load_fptk_data,
                load_sourcing_data,
                calculate_metrics,
                get_upload_cycle_progress,
            )
            from core.utils import get_filter_options_from_db
            return {
                'load_fptk_data': load_fptk_data,
                'load_sourcing_data': load_sourcing_data,
                'calculate_metrics': calculate_metrics,
                'get_upload_cycle_progress': get_upload_cycle_progress,
                'get_filter_options_from_db': get_filter_options_from_db,
            }
        except ImportError as e:
            st.caption(f"⚠️ Cache functions not available: {str(e)}")
            return None

    cache_funcs = get_cache_functions()

    if cache_funcs:
        load_fptk_data = cache_funcs['load_fptk_data']
        load_sourcing_data = cache_funcs['load_sourcing_data']
        calculate_metrics = cache_funcs['calculate_metrics']
        get_upload_cycle_progress = cache_funcs['get_upload_cycle_progress']
        get_filter_options_from_db = cache_funcs['get_filter_options_from_db']

        last_fptk = st.session_state.get('last_fptk_load', datetime.now())
        last_sourcing = st.session_state.get('last_sourcing_load', datetime.now())

        st.caption(f"🕐 FPTK: {last_fptk.strftime('%H:%M:%S')}")
        st.caption(f"🕐 Sourcing: {last_sourcing.strftime('%H:%M:%S')}")

        time_diff = (datetime.now() - last_fptk).seconds
        remaining = max(0, 300 - time_diff)
        if remaining > 0:
            st.caption(f"⏳ Auto refresh in {remaining//60}m {remaining%60}s")
        else:
            st.caption("🔄 Auto refreshing...")

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh All", use_container_width=True, type="primary"):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.session_state.last_fptk_load = datetime.now()
                st.session_state.last_sourcing_load = datetime.now()
                st.success("✅ All cache cleared! Reloading...")
                time.sleep(0.5)
                st.rerun()

        with col2:
            if st.button("🗑️ Clear Cache", use_container_width=True):
                load_fptk_data.clear()
                load_sourcing_data.clear()
                calculate_metrics.clear()
                get_upload_cycle_progress.clear()
                st.success("✅ Data cache cleared! Reloading...")
                time.sleep(0.5)
                st.rerun()

        with st.expander("🔧 Advanced Cache Control", expanded=False):
            if st.button("🧹 Clear FPTK Cache", use_container_width=True):
                load_fptk_data.clear()
                calculate_metrics.clear()
                st.session_state.last_fptk_load = datetime.now()
                st.success("✅ FPTK cache cleared!")
                st.rerun()

            if st.button("🧹 Clear Sourcing Cache", use_container_width=True):
                load_sourcing_data.clear()
                st.session_state.last_sourcing_load = datetime.now()
                st.success("✅ Sourcing cache cleared!")
                st.rerun()

            if st.button("🧹 Clear Filter Options", use_container_width=True):
                get_filter_options_from_db.clear()
                st.success("✅ Filter options cache cleared!")
                time.sleep(0.5)
                st.rerun()

            if st.button("🧹 Clear All Cache", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.session_state.last_fptk_load = datetime.now()
                st.session_state.last_sourcing_load = datetime.now()
                st.success("✅ All cache cleared!")
                st.rerun()

        st.markdown("---")
    else:
        st.caption("⚠️ Cache functions not available")
        st.markdown("---")

    # ========================================================
    # CHANGE PASSWORD
    # ========================================================

    with st.expander("🔑 Ganti Password"):

        with st.form("change_password"):

            db = get_cached_db()

            try:
                user = (
                    db.query(User)
                    .filter(User.id == st.session_state.user_id)
                    .first()
                )

                old = st.text_input("Password Lama", type="password")
                new = st.text_input("Password Baru (min 6 karakter)", type="password")
                confirm = st.text_input("Konfirmasi", type="password")

                update_password = st.form_submit_button("Update Password")

                if update_password:
                    if new and new == confirm and len(new) >= 6:
                        if user and verify_password(old, user.password_hash):
                            user.password_hash = hash_password(new)
                            db.commit()
                            st.success("✅ Password berhasil diubah!")
                        else:
                            st.error("❌ Password lama salah!")
                    else:
                        st.error("Password baru minimal 6 karakter dan harus sama!")

            finally:
                db.close()

    # ========================================================
    # LOGOUT
    # ========================================================

    st.markdown("---")

    if st.button("🚪 Logout", use_container_width=True):
        session_mgr.logout()
        st.session_state.clear()
        st.rerun()


# ============================================================
# SYNC SESSION STATE DENGAN SESSION MANAGER (FINAL)
# ============================================================

if st.session_state.user_id and not session_mgr.is_logged_in:
    session_mgr.login(
        st.session_state.user_id,
        st.session_state.username,
        st.session_state.role,
        st.session_state.user_display
    )
elif not st.session_state.user_id and session_mgr.is_logged_in:
    # ⚠️ JANGAN override page di sini!
    st.session_state.user_id = session_mgr.user_id
    st.session_state.username = session_mgr.username
    st.session_state.role = session_mgr.role
    st.session_state.user_display = session_mgr.user_display
    # page TIDAK di-reset


# ============================================================
# PAGE RENDERING
# ============================================================

page = st.session_state.get("page", "dashboard")


if page == "dashboard":
    dashboard = importlib.import_module("pages.dashboard")
    dashboard.show_dashboard()

elif page == "upload_compile":
    upload_compile = importlib.import_module("pages.02_upload_compile")
    upload_compile.show_upload_compile()

elif page == "fptk_view":
    fptk_view = importlib.import_module("pages.03_fptk_view")
    fptk_view.show_fptk_view()

elif page == "update_progres":
    try:
        update_progres = importlib.import_module("pages.11_update_progres")
        update_progres.show_update_progres()
    except ModuleNotFoundError:
        st.error("❌ File pages/11_update_progres.py tidak ditemukan!")

elif page == "sourcing_view":
    sourcing_view = importlib.import_module("pages.04_sourcing_view")
    sourcing_view.show_sourcing_view()

elif page == "db_kode_posisi":
    db_kode_posisi = importlib.import_module("pages.05_db_kode_posisi")
    db_kode_posisi.show_db_kode_posisi()

elif page == "upload_cycle":
    upload_cycle = importlib.import_module("pages.06_upload_cycle")
    upload_cycle.show_upload_cycle()

elif page == "user_management":
    user_management = importlib.import_module("pages.07_user_management")
    user_management.show_user_management()

elif page == "admin_delete_requests":
    try:
        admin_delete_requests = importlib.import_module("pages.10_admin_delete_requests")
        admin_delete_requests.show_admin_delete_requests()
    except ModuleNotFoundError:
        st.error("❌ File pages/10_admin_delete_requests.py tidak ditemukan!")

elif page == "sourcing_input":
    try:
        sourcing_input = importlib.import_module("pages.09_sourcing_input")
        sourcing_input.show_sourcing_input()
    except ModuleNotFoundError:
        st.error("❌ File pages/09_sourcing_input.py tidak ditemukan!")

elif page == "funnel_report":
    try:
        funnel_report = importlib.import_module("pages.funnel_report")
        funnel_report.show_funnel_report()
    except ModuleNotFoundError:
        st.error("❌ File pages/funnel_report.py tidak ditemukan!")

elif page == "monitoring_sourcing":
    try:
        monitoring_sourcing = importlib.import_module("pages.monitoring_sourcing")
        monitoring_sourcing.show_monitoring_sourcing()
    except ModuleNotFoundError:
        st.error("❌ File pages/monitoring_sourcing.py tidak ditemukan!")

elif page == "upload_evidence":
    try:
        upload_evidence = importlib.import_module("pages.upload_evidence")
        upload_evidence.show_upload_evidence()
    except ModuleNotFoundError:
        st.error("❌ File pages/upload_evidence.py tidak ditemukan!")

elif page == "transfer_fptk":
    try:
        transfer_fptk = importlib.import_module("pages.transfer_fptk")
        transfer_fptk.show_transfer_fptk()
    except ModuleNotFoundError:
        st.error("❌ File pages/transfer_fptk.py tidak ditemukan!")


# ============================================================
# EXPORT MENU
# ============================================================

st.markdown("---")
st.markdown("### 📥 Export Data")

if st.button("📊 Export All Data", use_container_width=True):
    with st.spinner("Mengekspor data..."):
        db = get_cached_db()
        try:
            from core.export_excel import export_database_to_excel
            filepath = export_database_to_excel(db)

            with open(filepath, "rb") as f:
                file_data = f.read()

            st.download_button(
                label="📥 Download Excel",
                data=file_data,
                file_name=os.path.basename(filepath),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.success(f"✅ Export berhasil! File: {os.path.basename(filepath)}")
        finally:
            db.close()

with st.expander("📋 Export Sheet Spesifik"):
    sheet_options = [
        "Blacklist Candidate",
        "DB Kode Posisi",
        "FPTK",
        "DB Sourcing",
        "Master Dropdown",
        "Evidence"
    ]
    selected_sheet = st.selectbox("Pilih Sheet", sheet_options)

    if st.button(f"Export {selected_sheet}"):
        with st.spinner(f"Mengekspor {selected_sheet}..."):
            db = get_cached_db()
            try:
                from core.export_excel import export_single_sheet
                df = export_single_sheet(db, selected_sheet)

                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=selected_sheet, index=False)
                output.seek(0)

                st.download_button(
                    label=f"📥 Download {selected_sheet}.xlsx",
                    data=output.getvalue(),
                    file_name=f"{selected_sheet}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success(f"✅ Export {selected_sheet} berhasil!")
            finally:
                db.close()
