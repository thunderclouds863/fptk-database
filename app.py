import streamlit as st
import time
import base64
from datetime import datetime

from core.database import SessionLocal, init_db
from core.auth import (
    login_user,
    is_admin,
    init_default_users,
    verify_password,
    hash_password,
    init_master_dropdown,
    get_current_user
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
# DATABASE INIT
# ============================================================

init_db()

# ============================================================
# SESSION STATE INIT
# ============================================================

defaults = {
    "user_id": None,
    "username": None,
    "role": None,
    "user_display": None,
    "page": "Dashboard",
    "filter_stack": [],
    "detail_id": None,
    "edit_id": None,
    "last_activity": datetime.now(),
    "need_refresh": False
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ============================================================
# INIT DEFAULT USERS & MASTER DATA
# ============================================================

db = SessionLocal()
try:
    init_default_users(db)
    init_master_dropdown(db)
finally:
    db.close()

# ============================================================
# LOADING HELPER
# ============================================================

def show_loading(message="⏳ Memuat..."):
    with st.spinner(message):
        time.sleep(0.2)

# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.user_id:
    try:
        with open("asset/cimory_logo.png", "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")
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
    @media (max-width: 768px) { .block-container { padding-left: 15px !important; padding-right: 15px !important; padding-top: 20px !important; } .cimory-logo-container { width: 100vw !important; max-width: 100vw !important; left: 50% !important; transform: translateX(-50%) !important; margin-top: 10px !important; margin-bottom: 35px !important; } .cimory-logo { width: 220px !important; max-width: 220px !important; } div[data-testid="stForm"] { width: auto !important; max-width: calc(100vw - 30px) !important; padding: 30px 22px 28px 22px !important; border-radius: 17px !important; } .login-title { font-size: 32px; gap: 10px; } .login-icon { font-size: 26px !important; width: 34px; height: 34px; } div[data-baseweb="input"] { height: 56px !important; } div[data-baseweb="input"] input { height: 54px !important; font-size: 15px !important; } div[data-testid="stFormSubmitButton"] button { height: 56px !important; } }
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

    # NAVIGATION
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

    # CACHE CONTROL
    st.markdown("### ⚡ Quick Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.session_state.need_refresh = True
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

    # CHANGE PASSWORD
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
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================
# HANDLE REFRESH FLAG
# ============================================================

if st.session_state.get("need_refresh", False):
    st.session_state.need_refresh = False
    st.rerun()

# ============================================================
# PAGE LOADING & RENDER
# ============================================================

page = st.session_state.page

# Dictionary untuk mapping page ke fungsi
page_map = {
    "dashboard": ("pages.dashboard", "show_dashboard"),
    "upload_compile": ("pages.02_upload_compile", "show_upload_compile"),
    "fptk_view": ("pages.03_fptk_view", "show_fptk_view"),
    "sourcing_view": ("pages.04_sourcing_view", "show_sourcing_view"),
    "db_kode_posisi": ("pages.05_db_kode_posisi", "show_db_kode_posisi"),
    "upload_cycle": ("pages.06_upload_cycle", "show_upload_cycle"),
    "user_management": ("pages.07_user_management", "show_user_management"),
    "sourcing_input": ("pages.09_sourcing_input", "show_sourcing_input"),
    "funnel_report": ("pages.funnel_report", "show_funnel_report"),
    "monitoring_sourcing": ("pages.monitoring_sourcing", "show_monitoring_sourcing"),
    "upload_evidence": ("pages.upload_evidence", "show_upload_evidence"),
    "transfer_fptk": ("pages.transfer_fptk", "show_transfer_fptk"),
}

# Tampilkan loading spinner dulu
with st.spinner(f"⏳ Memuat {page.replace('_', ' ').title()}..."):
    time.sleep(0.1)

# Render page
if page in page_map:
    module_name, func_name = page_map[page]
    try:
        module = __import__(module_name, fromlist=[func_name])
        func = getattr(module, func_name)
        func()
    except ModuleNotFoundError:
        st.error(f"❌ File {module_name}.py tidak ditemukan!")
    except AttributeError:
        st.error(f"❌ Fungsi {func_name} tidak ditemukan di {module_name}.py!")
else:
    st.error(f"❌ Page '{page}' tidak dikenal!")

# ============================================================
# EXPORT MENU (Di Bawah Konten Utama)
# ============================================================

st.markdown("---")
st.markdown("### 📥 Export Data")

if st.button("📊 Export All Data", use_container_width=True):
    with st.spinner("Mengekspor data..."):
        db = SessionLocal()
        try:
            from core.export_excel import export_database_to_excel
            import os
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
        except Exception as e:
            st.error(f"❌ Export gagal: {str(e)}")
        finally:
            db.close()

# ============================================================
# SINGLE SHEET EXPORT
# ============================================================

with st.expander("📋 Export Sheet Spesifik"):
    sheet_options = ["Blacklist Candidate", "DB Kode Posisi", "FPTK", "DB Sourcing", "Master Dropdown", "Evidence"]
    selected_sheet = st.selectbox("Pilih Sheet", sheet_options)

    if st.button(f"Export {selected_sheet}"):
        with st.spinner(f"Mengekspor {selected_sheet}..."):
            db = SessionLocal()
            try:
                from core.export_excel import export_single_sheet
                import pandas as pd
                from io import BytesIO

                df = export_single_sheet(db, selected_sheet)
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
            except Exception as e:
                st.error(f"❌ Export gagal: {str(e)}")
            finally:
                db.close()
