import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User
from core.auth import get_current_user, is_admin, create_user, reset_password, hash_password
import pandas as pd

def show_user_management():
    st.title("👥 User Management")
    st.markdown("Kelola akun user dan PIC Recruiter.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    if not is_admin(db):
        st.error("Halaman ini hanya untuk Admin.")
        return
    
    # List users
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()
    
    if users:
        data = []
        for u in users:
            data.append({
                "ID": u.id,
                "Username": u.username,
                "Role": u.role,
                "PIC Recruiter": u.pic_recruiter or "-",
                "Display Name": u.display_name or u.username,
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-"
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    
    # Add new user
    st.markdown("---")
    st.subheader("➕ Tambah User Baru")
    
    with st.form("add_user"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_username = st.text_input("Username *")
        with col2:
            new_password = st.text_input("Password *", type="password")
        with col3:
            new_role = st.selectbox("Role", ["user", "admin"])
        
        new_pic = st.text_input("PIC Recruiter (untuk user role)", placeholder="Contoh: Pauline, Karin, dll")
        new_display = st.text_input("Display Name", placeholder="Nama tampilan (opsional)")
        
        if st.form_submit_button("Tambah User"):
            if new_username and new_password and len(new_password) >= 6:
                result = create_user(db, new_username, new_password, new_role, new_pic, new_display)
                if result:
                    st.success(f"✅ User '{new_username}' berhasil dibuat!")
                    st.rerun()
                else:
                    st.error("Username sudah digunakan atau password tidak valid")
            else:
                st.error("Username dan password (min 6 karakter) wajib diisi")
    
    # Reset password
    st.markdown("---")
    st.subheader("🔑 Reset Password User")
    
    user_options = {f"{u.username} ({u.display_name})": u.id for u in users if u.role == "user"}
    selected_user = st.selectbox("Pilih User", list(user_options.keys()))
    
    if selected_user:
        user_id = user_options[selected_user]
        new_pw = st.text_input("Password Baru", type="password")
        if st.button("Reset Password"):
            if new_pw and len(new_pw) >= 6:
                if reset_password(db, user_id, new_pw):
                    st.success("Password berhasil direset!")
                else:
                    st.error("Gagal reset password")
            else:
                st.error("Password baru minimal 6 karakter")