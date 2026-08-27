import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence
from core.auth import get_current_user, is_admin, create_user, reset_password, hash_password
import pandas as pd
from datetime import datetime

# ============================================================
# DIALOG KONFIRMASI NONAKTIFKAN USER
# ============================================================
@st.dialog("⚠️ Konfirmasi Nonaktifkan User")
def confirm_deactivate_user(user_id: int, username: str):
    st.warning(f"Yakin ingin **nonaktifkan** user **{username}**?")
    st.caption("User akan kehilangan akses login. **Semua data (FPTK, Sourcing, Evidence, Upload Logs) TETAP TERSIMPAN**.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Ya, Nonaktifkan", type="primary", use_container_width=True):
            db = next(get_db())
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.username = f"inactive_{user.username}_{datetime.now().strftime('%Y%m%d')}"
                    user.password_hash = "DISABLED"
                    db.commit()
                    st.success(f"✅ User '{username}' berhasil dinonaktifkan!")
                    st.rerun()
                else:
                    st.error("User tidak ditemukan!")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
            finally:
                db.close()
    
    with col2:
        if st.button("❌ Batal", use_container_width=True):
            st.rerun()


# ============================================================
# DIALOG AKTIFKAN USER
# ============================================================
@st.dialog("🔄 Aktifkan User Kembali")
def confirm_activate_user(user_id: int, username: str):
    st.info(f"Aktifkan user **{username}** kembali?")
    st.caption("Password akan direset ke **password123**.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Ya, Aktifkan", type="primary", use_container_width=True):
            db = next(get_db())
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    clean_username = user.username
                    if clean_username.startswith("inactive_"):
                        parts = clean_username.split("_")
                        original = parts[1] if len(parts) >= 2 else clean_username.replace("inactive_", "")
                        existing = db.query(User).filter(User.username == original).first()
                        if existing and existing.id != user_id:
                            st.error(f"Username '{original}' sudah digunakan!")
                            db.close()
                            st.stop()
                        user.username = original
                    user.password_hash = hash_password("password123")
                    db.commit()
                    st.success(f"✅ User '{username}' berhasil diaktifkan! Password: **password123**")
                    st.rerun()
                else:
                    st.error("User tidak ditemukan!")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
            finally:
                db.close()
    
    with col2:
        if st.button("❌ Batal", use_container_width=True):
            st.rerun()


# ============================================================
# DIALOG EDIT USER
# ============================================================
@st.dialog("✏️ Edit User")
def edit_user_dialog(user_id: int):
    db = next(get_db())
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        st.error("User tidak ditemukan!")
        db.close()
        return
    
    is_active = not user.username.startswith("inactive_")
    
    with st.form("edit_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username", value=user.username, disabled=not is_active)
            new_display = st.text_input("Display Name / PIC Recruiter", value=user.display_name or "")
        with col2:
            new_role = st.selectbox("Role", ["user", "admin"], index=0 if user.role == "user" else 1)
            reset_pw = st.checkbox("Reset Password")
            new_password = st.text_input("Password Baru (min 6 karakter)", type="password", disabled=not reset_pw)
        
        if not is_active:
            st.warning("⚠️ User ini sudah nonaktif. Ubah username (hapus 'inactive_') untuk mengaktifkan.")
        
        if st.form_submit_button("💾 Simpan", type="primary", use_container_width=True):
            try:
                if new_username != user.username:
                    existing = db.query(User).filter(User.username == new_username).first()
                    if existing and existing.id != user_id:
                        st.error(f"Username '{new_username}' sudah digunakan!")
                        st.stop()
                
                user.username = new_username
                user.display_name = new_display
                user.pic_recruiter = new_display  # SAMA DENGAN DISPLAY NAME
                user.role = new_role
                
                if reset_pw and new_password and len(new_password) >= 6:
                    user.password_hash = hash_password(new_password)
                
                db.commit()
                st.success("✅ User berhasil diupdate!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
    
    db.close()


# ============================================================
# MAIN FUNCTION
# ============================================================
def show_user_management():
    st.title("👥 User Management")
    st.markdown("Kelola akun user (Edit, Reset Password, Nonaktifkan/Aktifkan).")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    if not is_admin(db):
        st.error("Halaman ini hanya untuk Admin.")
        return
    
    # ============================================================
    # DAFTAR USER - PAKAI st.dataframe (SORTABLE)
    # ============================================================
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()
    
    if users:
        data = []
        for u in users:
            is_active = not u.username.startswith("inactive_")
            data.append({
                "ID": u.id,
                "Username": u.username,
                "Display Name / PIC": u.display_name or u.username,
                "Role": u.role,
                "Status": "✅ Aktif" if is_active else "⛔ Nonaktif",
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-",
            })
        df = pd.DataFrame(data)
        
        st.dataframe(
            df,
            use_container_width=True,
            height=350,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Username": st.column_config.TextColumn("Username", width="medium"),
                "Display Name / PIC": st.column_config.TextColumn("Display Name / PIC", width="medium"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Last Login": st.column_config.TextColumn("Last Login", width="medium"),
                "Created": st.column_config.TextColumn("Created", width="medium"),
            }
        )
        
        # ============================================================
        # TOMBOL AKSI PER USER
        # ============================================================
        st.markdown("---")
        st.subheader("🔧 Aksi User")
        
        user_options = {f"{u.username} ({u.display_name or u.username})": u.id for u in users}
        selected_user = st.selectbox("Pilih User", list(user_options.keys()))
        selected_id = user_options[selected_user]
        selected_data = db.query(User).filter(User.id == selected_id).first()
        
        if selected_data:
            is_active = not selected_data.username.startswith("inactive_")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("✏️ Edit User", use_container_width=True):
                    edit_user_dialog(selected_id)
            
            with col2:
                if st.button("🔑 Reset Password", use_container_width=True):
                    if reset_password(db, selected_id, "password123"):
                        st.success(f"✅ Password user '{selected_data.username}' direset ke: **password123**")
                        st.rerun()
                    else:
                        st.error("Gagal reset password!")
            
            with col3:
                if is_active:
                    if st.button("⛔ Nonaktifkan", use_container_width=True):
                        confirm_deactivate_user(selected_id, selected_data.username)
                else:
                    if st.button("🔄 Aktifkan Kembali", use_container_width=True):
                        confirm_activate_user(selected_id, selected_data.username)
            
            with col4:
                if is_active:
                    st.success("✅ Aktif")
                else:
                    st.error("⛔ Nonaktif")
        
        # ============================================================
        # TAMBAH USER BARU
        # ============================================================
        st.markdown("---")
        st.subheader("➕ Tambah User Baru")
        
        with st.form("add_user"):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_username = st.text_input("Username *")
            with col2:
                new_password = st.text_input("Password *", type="password", value="password123")
            with col3:
                new_role = st.selectbox("Role", ["user", "admin"])
            
            new_display = st.text_input("Display Name / PIC Recruiter *", placeholder="Nama yang akan tampil (sama dengan PIC Recruiter)")
            
            if st.form_submit_button("Tambah User", type="primary"):
                errors = []
                if not new_username:
                    errors.append("Username wajib diisi")
                if not new_password or len(new_password) < 6:
                    errors.append("Password minimal 6 karakter")
                if not new_display:
                    errors.append("Display Name / PIC Recruiter wajib diisi")
                
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    # PIC Recruiter = Display Name
                    result = create_user(db, new_username, new_password, new_role, new_display, new_display)
                    if result:
                        st.success(f"✅ User '{new_username}' berhasil dibuat!")
                        st.rerun()
                    else:
                        st.error("Username sudah digunakan!")
    
    else:
        st.info("Belum ada user.")
    
    # ============================================================
    # SUMMARY STATISTICS
    # ============================================================
    st.markdown("---")
    st.subheader("📊 Statistik User")
    
    if users:
        total_users = len(users)
        admin_count = len([u for u in users if u.role == "admin"])
        user_count = len([u for u in users if u.role == "user"])
        active_count = len([u for u in users if not u.username.startswith("inactive_")])
    else:
        total_users = admin_count = user_count = active_count = 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total User", total_users)
    col2.metric("Admin", admin_count)
    col3.metric("User", user_count)
    col4.metric("Aktif", active_count)
    
    db.close()
