import streamlit as st
import importlib
from core.database import SessionLocal, init_db
from core.auth import login_user, get_current_user, is_admin, init_default_users, verify_password, hash_password
from core.upload_cycle import get_current_cycle
from core.models import User
import time

# Page config
st.set_page_config(
    page_title="FPTK & Sourcing System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database tables
init_db()

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "filter_stack" not in st.session_state:
    st.session_state.filter_stack = []

# Initialize default users if DB is empty
db = SessionLocal()
try:
    init_default_users(db)
finally:
    db.close()

# ============================================================
# LOGIN PAGE
# ============================================================
if not st.session_state.user_id:
    st.markdown(
        """
        <style>
        .login-container {
            max-width: 400px;
            margin: auto;
            padding: 40px 20px;
            border-radius: 10px;
            background: #f8f9fa;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 15px;">
            <img src="https://icon2.cleanpng.com/20180607/hct/aa82svjoo.webp" width="150">
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("## 🔐 Login")
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Masukkan username")
        password = st.text_input("Password", type="password", placeholder="Masukkan password")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
        
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
                        st.success(f"✅ Selamat datang, {st.session_state.user_display}!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Username atau password salah!")
                finally:
                    db.close()
    
    st.stop()

# ============================================================
# SIDEBAR (Logged in)
# ============================================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.user_display}")
    st.caption(f"Role: {st.session_state.role}")
    
    st.markdown("---")
    
    # Navigation
    pages = {
        "📊 Dashboard": "dashboard",
        "📤 Upload & Compile": "upload_compile",
        "📋 FPTK View": "fptk_view",
        "👤 Sourcing View": "sourcing_view",
        "🏢 DB Kode Posisi": "db_kode_posisi",
    }
    
    db = SessionLocal()
    if is_admin(db):
        pages["🔄 Upload Cycle"] = "upload_cycle"
        pages["👥 User Management"] = "user_management"
    db.close()
    
    selected = st.radio("Navigasi", list(pages.keys()), index=0)
    st.session_state.page = pages[selected]
    
    st.markdown("---")
    
    # Change password
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
        st.session_state.clear()
        st.rerun()

# ============================================================
# RENDER PAGE
# ============================================================
page = st.session_state.page

if page == "dashboard":
    dashboard = importlib.import_module("pages.01_dashboard")
    dashboard.show_dashboard()
elif page == "upload_compile":
    upload_compile = importlib.import_module("pages.02_upload_compile")
    upload_compile.show_upload_compile()
elif page == "fptk_view":
    fptk_view = importlib.import_module("pages.03_fptk_view")
    fptk_view.show_fptk_view()
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
