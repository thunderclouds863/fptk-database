import streamlit as st
import importlib
import time
import base64
from core.session_manager import get_session_manager
import os
import pandas as pd
from datetime import datetime

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
session_mgr = get_session_manager()


# ============================================================
# SESSION STATE - SYNC DENGAN SESSION MANAGER
# ============================================================

# Inisialisasi session_state dari session_manager
if "user_id" not in st.session_state:
    st.session_state.user_id = session_mgr.user_id

if "username" not in st.session_state:
    st.session_state.username = session_mgr.username

if "role" not in st.session_state:
    st.session_state.role = session_mgr.role

if "user_display" not in st.session_state:
    st.session_state.user_display = session_mgr.user_display

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "filter_stack" not in st.session_state:
    st.session_state.filter_stack = []

if "detail_id" not in st.session_state:
    st.session_state.detail_id = None

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

if "need_refresh" not in st.session_state:
    st.session_state.need_refresh = False

if "last_activity" not in st.session_state:
    st.session_state.last_activity = datetime.now()

# Inisialisasi timestamp untuk cache
if "last_fptk_load" not in st.session_state:
    st.session_state.last_fptk_load = datetime.now()

if "last_sourcing_load" not in st.session_state:
    st.session_state.last_sourcing_load = datetime.now()


# ============================================================
# SESSION TIMEOUT (30 MENIT)
# ============================================================

if st.session_state.user_id:
    time_diff = (datetime.now() - st.session_state.last_activity).seconds
    if time_diff > 1800:  # 30 menit
        session_mgr.logout()
        st.session_state.clear()
        st.rerun()
    else:
        st.session_state.last_activity = datetime.now()


# ============================================================
# SESSION PERSISTENCE
# ============================================================

if st.session_state.user_id and not session_mgr.is_logged_in:
    session_mgr.login(
        st.session_state.user_id,
        st.session_state.username,
        st.session_state.role,
        st.session_state.user_display
    )
elif not st.session_state.user_id and session_mgr.is_logged_in:
    st.session_state.user_id = session_mgr.user_id
    st.session_state.username = session_mgr.username
    st.session_state.role = session_mgr.role
    st.session_state.user_display = session_mgr.user_display


# ============================================================
# DEFAULT USER & MASTER DROPDOWN
# ============================================================

db = SessionLocal()
try:
    init_default_users(db)
    init_master_dropdown(db)
finally:
    db.close()


# ============================================================
# HANDLE REFRESH FLAG
# ============================================================

if st.session_state.get("need_refresh", False):
    st.session_state.need_refresh = False
    st.rerun()


# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.user_id:

    try:
        with open("asset/cimory_logo.png", "rb") as logo_file:
            logo_base64 = base64.b64encode(logo_file.read()).decode("utf-8")
    except FileNotFoundError:
        logo_base64 = ""

    st.markdown("""
    <style>
    .stApp { background: radial-gradient(ellipse at 50% 20%, #151b29 0%, #0d1119 45%, #080b10 100%); min-height: 100vh; }
    header { visibility: hidden; }
    .block-container { padding-top: 30px !important; padding-bottom: 50px !important; }
    .cimory-logo-container { width: 100vw !important; max-width: 100vw !important; position: relative !important; left: 50% !important; transform: translateX(-50%) !important; display: flex !important; justify-content: center !important; align-items: center !important; margin-top: 10px !important; margin-bottom: 55px !important; padding: 0 !important; box-sizing: border-box !important; text-align: center !important; }
    .cimory-logo { width: 260px !important; max-width: 260px !important; height: auto !important; display: block !important; margin: 0 auto !important; padding: 0 !important; object-fit: contain !important; }
    div[data-testid="stForm"] { width: 700px !important; max-width: calc(100vw - 40px) !important; margin-left: auto !important; margin-right: auto !important; padding: 42px 42px 38px 42px !important; background: linear-gradient(145deg, rgba(20,24,34,0.90), rgba(12,15,22,0.90)) !important; border: 1px solid rgba(125,140,170,0.28) !important; border-radius: 20px !important; box-shadow: 0 25px 70px rgba(0,0,0,0.45) !important; backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); box-sizing: border-box !important; }
    .login-title { display: flex; align-items: center; gap: 12px; color: #f5f7fb; font-size: 38px; font-weight: 700; line-height: 1; margin-bottom: 35px; letter-spacing: -1px; }
    .login-icon { font-size: 30px !important; line-height: 1 !important; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; }
    div[data-testid="stTextInput"] label { color: #f1f3f7 !important; font-size: 16px !important; font-weight: 600 !important; margin-bottom: 8px !important; }
    div[data-baseweb="input"] { height: 58px !important; background: linear-gradient(145deg, #242731, #1e212b) !important; border: 1px solid rgba(150,160,180,0.20) !important; border-radius: 12px !important; transition: border 0.2s ease, box-shadow 0.2s ease; }
    div[data-baseweb="input"]:focus-within { border: 1px solid rgba(255,255,255,0.38) !important; box-shadow: 0 0 0 2px rgba(255,255,255,0.04) !important; }
    div[data-baseweb="input"] input { height: 56px !important; color: #f5f5f7 !important; font-size: 16px !important; font-weight: 400 !important; }
    div[data-baseweb="input"] input::placeholder { color: #a0a3ad !important; opacity: 1 !important; }
    div[data-testid="stTextInput"] { margin-bottom: 20px; }
    div[data-testid="stFormSubmitButton"] { margin-top: 8px !important; }
    div[data-testid="stFormSubmitButton"] button { width: 100% !important; height: 62px !important; border: none !important; border-radius: 13px !important; background: linear-gradient(90deg, #ff3d48, #ff4d54) !important; color: white !important; font-size: 18px !important; font-weight: 700 !important; transition: transform 0.15s ease, box-shadow 0.15s ease; }
    div[data-testid="stFormSubmitButton"] button:hover { background: linear-gradient(90deg, #ff4751, #ff5960) !important; transform: translateY(-1px); box-shadow: 0 10px 25px rgba(255,60,70,0.25); }
    @media (max-width: 768px) { .block-container { padding-left: 15px !important; padding-right: 15px !important; padding-top: 20px !important; } .cimory-logo-container { width: 100vw !important; max-width: 100vw !important; left: 50% !important; transform: translateX(-50%) !important; margin-top: 10px !important; margin-bottom: 35px !important; } .cimory-logo { width: 220px !important; max-width: 220px !important; } div[data-testid="stForm"] { width: auto !important; max-width: calc(100vw - 30px) !important; padding: 30px 22px 28px 22px !important; border-radius: 17px !important; } .login-title { font-size: 32px; gap: 10px; } div[data-baseweb="input"] { height: 56px !important; } div[data-testid="stFormSubmitButton"] button { height: 56px !important; } }
    </style>
    """, unsafe_allow_html=True)

    if logo_base64:
        st.markdown(f"""
        <div class="cimory-logo-container">
            <img src="data:image/png;base64,{logo_base64}" class="cimory-logo" alt="Cimory Logo">
        </div>
        """, unsafe_allow_html=True)

    with st.form("login_form"):
        st.markdown('<div class="login-title"><span class="login-icon">🔐</span><span>Login</span></div>', unsafe_allow_html=True)
        username = st.text_input("Username", placeholder="Masukkan username")
        password = st.text_input("Password", type="password", placeholder="Masukkan password")
        submitted = st.form_submit_button("Login →", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Username dan password wajib diisi!")
            else:
                db = SessionLocal()
                try:
                    user = login_user(db, username, password)
                    if user:
                        session_mgr.login(user.id, user.username, user.role, user.display_name or user.username)
                        st.session_state.user_id = user.id
                        st.session_state.username = user.username
                        st.session_state.role = user.role
                        st.session_state.user_display = user.display_name or user.username
                        st.session_state.last_activity = datetime.now()
                        st.success(f"✅ Selamat datang, {st.session_state.user_display}!")
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
    st.markdown(f"### 👤 {st.session_state.user_display}")
    st.caption(f"Role: {st.session_state.role}")
    st.markdown("---")

    # ========================================================
    # NAVIGATION
    # ========================================================

    pages = {
        "📊 Dashboard": "dashboard",
        "📤 Upload & Compile FPTK": "upload_compile",
        "📋 FPTK View": "fptk_view",
        "👤 Sourcing Input": "sourcing_input",
        "👩🏻‍💻 Sourcing View": "sourcing_view",
        "🏢 DB Kode Posisi": "db_kode_posisi",
        "🔍 Funnel Report": "funnel_report",
        "📊 Monitoring Sourcing": "monitoring_sourcing",
        "📎 Upload Evidence": "upload_evidence",
        "📩 Transfer FPTK": "transfer_fptk"
    }

    db = SessionLocal()
    try:
        if is_admin(db):
            pages["🔄 Update Cycle"] = "upload_cycle"
            pages["👥 User Management"] = "user_management"
    finally:
        db.close()

    selected = st.radio("Navigasi", list(pages.keys()), index=0)
    st.session_state.page = pages[selected]
    st.markdown("---")

    # ========================================================
    # CACHE CONTROL (SEDERHANA & CEPAT)
    # ========================================================

    st.markdown("### ⚡ Cache Control")
    st.caption(f"🕐 Update: {datetime.now().strftime('%H:%M:%S')}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.session_state.last_fptk_load = datetime.now()
            st.session_state.last_sourcing_load = datetime.now()
            st.success("✅ Refreshing...")
            time.sleep(0.3)
            st.rerun()
    with col2:
        if st.button("🗑️ Clear Cache", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("✅ Cache cleared!")
            time.sleep(0.3)
            st.rerun()

    st.markdown("---")

    # ========================================================
    # CHANGE PASSWORD
    # ========================================================

    with st.expander("🔑 Ganti Password"):
        with st.form("change_password"):
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == st.session_state.user_id).first()
                old = st.text_input("Password Lama", type="password")
                new = st.text_input("Password Baru (min 6 karakter)", type="password")
                confirm = st.text_input("Konfirmasi", type="password")
                if st.form_submit_button("Update Password"):
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

    st.markdown("---")

    if st.button("🚪 Logout", use_container_width=True):
        session_mgr.logout()
        st.session_state.clear()
        st.rerun()


# ============================================================
# PAGE RENDERING DENGAN LOADING SPINNER
# ============================================================

page = st.session_state.page

# Tampilkan spinner loading dengan durasi singkat
with st.spinner(f"⏳ Memuat {page.replace('_', ' ').title()}..."):
    time.sleep(0.2)

# Render page
if page == "dashboard":
    from pages.dashboard import show_dashboard
    show_dashboard()
elif page == "upload_compile":
    from pages.02_upload_compile import show_upload_compile
    show_upload_compile()
elif page == "fptk_view":
    from pages.03_fptk_view import show_fptk_view
    show_fptk_view()
elif page == "sourcing_view":
    from pages.04_sourcing_view import show_sourcing_view
    show_sourcing_view()
elif page == "db_kode_posisi":
    from pages.05_db_kode_posisi import show_db_kode_posisi
    show_db_kode_posisi()
elif page == "upload_cycle":
    from pages.06_upload_cycle import show_upload_cycle
    show_upload_cycle()
elif page == "user_management":
    from pages.07_user_management import show_user_management
    show_user_management()
elif page == "sourcing_input":
    try:
        from pages.09_sourcing_input import show_sourcing_input
        show_sourcing_input()
    except ModuleNotFoundError:
        st.error("❌ File pages/09_sourcing_input.py tidak ditemukan!")
elif page == "funnel_report":
    try:
        from pages.funnel_report import show_funnel_report
        show_funnel_report()
    except ModuleNotFoundError:
        st.error("❌ File pages/funnel_report.py tidak ditemukan!")
elif page == "monitoring_sourcing":
    try:
        from pages.monitoring_sourcing import show_monitoring_sourcing
        show_monitoring_sourcing()
    except ModuleNotFoundError:
        st.error("❌ File pages/monitoring_sourcing.py tidak ditemukan!")
elif page == "upload_evidence":
    try:
        from pages.upload_evidence import show_upload_evidence
        show_upload_evidence()
    except ModuleNotFoundError:
        st.error("❌ File pages/upload_evidence.py tidak ditemukan!")
elif page == "transfer_fptk":
    try:
        from pages.transfer_fptk import show_transfer_fptk
        show_transfer_fptk()
    except ModuleNotFoundError:
        st.error("❌ File pages/transfer_fptk.py tidak ditemukan!")


# ============================================================
# EXPORT DATA (DI BAWAH KONTEN)
# ============================================================

st.markdown("---")
st.markdown("### 📥 Export Data")

col1, col2 = st.columns(2)

with col1:
    if st.button("📊 Export All Data", use_container_width=True):
        with st.spinner("⏳ Mengekspor data..."):
            db = SessionLocal()
            try:
                # Coba export via core.export_excel
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
                        use_container_width=True,
                        key="export_all_download"
                    )
                    st.success(f"✅ Export berhasil!")
                except ImportError:
                    # Fallback: export manual
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        # Export FPTK
                        fptk_df = pd.read_sql(db.query(FPTK).statement, db.bind)
                        fptk_df.to_excel(writer, sheet_name="FPTK", index=False)
                        # Export Sourcing
                        sourcing_df = pd.read_sql(db.query(DBSourcing).statement, db.bind)
                        sourcing_df.to_excel(writer, sheet_name="DB Sourcing", index=False)
                        # Export DB Kode Posisi
                        dbk_df = pd.read_sql(db.query(DBKodePosisi).statement, db.bind)
                        dbk_df.to_excel(writer, sheet_name="DB Kode Posisi", index=False)
                        # Export Master Dropdown
                        master_df = pd.read_sql(db.query(MasterDropdown).statement, db.bind)
                        master_df.to_excel(writer, sheet_name="Master Dropdown", index=False)
                    output.seek(0)
                    st.download_button(
                        label="📥 Download Excel",
                        data=output.getvalue(),
                        file_name=f"FPTK_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="export_all_fallback"
                    )
                    st.success("✅ Export berhasil!")
            except Exception as e:
                st.error(f"❌ Export gagal: {str(e)}")
            finally:
                db.close()

with col2:
    # Single sheet export
    with st.expander("📋 Export Sheet Spesifik"):
        from core.models import FPTK, DBSourcing, DBKodePosisi, MasterDropdown
        sheet_options = {
            "FPTK": FPTK,
            "DB Sourcing": DBSourcing,
            "DB Kode Posisi": DBKodePosisi,
            "Master Dropdown": MasterDropdown
        }
        selected_sheet = st.selectbox("Pilih Sheet", list(sheet_options.keys()))

        if st.button(f"📥 Download {selected_sheet}"):
            with st.spinner(f"⏳ Mengekspor {selected_sheet}..."):
                db = SessionLocal()
                try:
                    model = sheet_options[selected_sheet]
                    df = pd.read_sql(db.query(model).statement, db.bind)

                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name=selected_sheet, index=False)
                    output.seek(0)

                    st.download_button(
                        label=f"📥 Download {selected_sheet}.xlsx",
                        data=output.getvalue(),
                        file_name=f"{selected_sheet}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"export_{selected_sheet}"
                    )
                    st.success(f"✅ Export {selected_sheet} berhasil!")
                except Exception as e:
                    st.error(f"❌ Export {selected_sheet} gagal: {str(e)}")
                finally:
                    db.close()
