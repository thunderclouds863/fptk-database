import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence
from core.auth import get_current_user, is_admin, create_user, reset_password, hash_password
import pandas as pd
from datetime import datetime

# ============================================================
# DIALOG KONFIRMASI HAPUS (POP-UP)
# ============================================================
@st.dialog("⚠️ Konfirmasi Hapus User")
def confirm_delete_user(user_id: int, username: str):
    st.warning(f"Yakin ingin menghapus user **{username}**?")
    st.caption("Semua data terkait (FPTK, Sourcing, Evidence, Upload Logs, dll) akan ikut terhapus.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Ya, Hapus", type="primary", use_container_width=True):
            db = next(get_db())
            try:
                # Hapus data terkait
                db.query(Evidence).filter(Evidence.user_id == user_id).delete()
                db.query(AuditLog).filter(AuditLog.user_id == user_id).delete()
                db.query(UploadStatus).filter(UploadStatus.user_id == user_id).delete()
                db.query(UploadLog).filter(UploadLog.user_id == user_id).delete()
                db.query(DBSourcing).filter(DBSourcing.source_user_id == user_id).delete()
                db.query(FPTK).filter(FPTK.source_user_id == user_id).delete()
                
                user_to_delete = db.query(User).filter(User.id == user_id).first()
                if user_to_delete:
                    db.delete(user_to_delete)
                    db.commit()
                    st.success(f"✅ User '{username}' berhasil dihapus!")
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
# DIALOG EDIT USER (POP-UP)
# ============================================================
@st.dialog("✏️ Edit User")
def edit_user_dialog(user_id: int):
    db = next(get_db())
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        st.error("User tidak ditemukan!")
        db.close()
        return
    
    with st.form("edit_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username", value=user.username)
            new_display = st.text_input("Display Name", value=user.display_name or "")
            new_role = st.selectbox("Role", ["user", "admin"], index=0 if user.role == "user" else 1)
        with col2:
            new_pic = st.text_input("PIC Recruiter", value=user.pic_recruiter or "")
            reset_pw = st.checkbox("Reset Password")
            new_password = st.text_input("Password Baru (min 6 karakter)", type="password", disabled=not reset_pw)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Simpan", type="primary", use_container_width=True):
                try:
                    # Cek username duplikat
                    if new_username != user.username:
                        existing = db.query(User).filter(User.username == new_username).first()
                        if existing:
                            st.error(f"Username '{new_username}' sudah digunakan!")
                            st.stop()
                    
                    user.username = new_username
                    user.display_name = new_display
                    user.role = new_role
                    user.pic_recruiter = new_pic
                    
                    if reset_pw and new_password and len(new_password) >= 6:
                        user.password_hash = hash_password(new_password)
                    
                    db.commit()
                    st.success("✅ User berhasil diupdate!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
        
        with col2:
            if st.form_submit_button("❌ Batal", use_container_width=True):
                st.rerun()
    
    db.close()

# ============================================================
# MAIN FUNCTION
# ============================================================
def show_user_management():
    st.title("👥 User Management")
    st.markdown("Kelola akun user (Edit, Reset Password, Hapus).")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    if not is_admin(db):
        st.error("Halaman ini hanya untuk Admin.")
        return
    
    # ============================================================
    # DAFTAR USER DENGAN TABEL RAPI
    # ============================================================
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()
    
    if users:
        # Buat data untuk ditampilkan
        data = []
        for u in users:
            data.append({
                "ID": u.id,
                "Username": u.username,
                "Role": u.role,
                "Display Name": u.display_name or u.username,
                "PIC": u.pic_recruiter or "-",
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-",
            })
        df = pd.DataFrame(data)
        
        # Gunakan st.dataframe dengan column_config untuk tombol custom
        # Karena st.dataframe tidak support tombol, kita pakai kombinasi
        # Tampilkan tabel dengan st.columns untuk setiap baris
        
        # Header
        cols = st.columns([0.5, 1.2, 0.7, 1.2, 0.8, 1.2, 1.2, 0.8, 0.8])
        with cols[0]: st.markdown("**ID**")
        with cols[1]: st.markdown("**Username**")
        with cols[2]: st.markdown("**Role**")
        with cols[3]: st.markdown("**Display Name**")
        with cols[4]: st.markdown("**PIC**")
        with cols[5]: st.markdown("**Last Login**")
        with cols[6]: st.markdown("**Created**")
        with cols[7]: st.markdown("**Edit**")
        with cols[8]: st.markdown("**Hapus**")
        
        st.divider()
        
        # Data rows
        for idx, row in df.iterrows():
            cols = st.columns([0.5, 1.2, 0.7, 1.2, 0.8, 1.2, 1.2, 0.8, 0.8])
            
            with cols[0]:
                st.write(row["ID"])
            with cols[1]:
                st.write(row["Username"])
            with cols[2]:
                st.write(row["Role"])
            with cols[3]:
                st.write(row["Display Name"])
            with cols[4]:
                st.write(row["PIC"])
            with cols[5]:
                st.write(row["Last Login"])
            with cols[6]:
                st.write(row["Created"])
            
            # Tombol Edit
            with cols[7]:
                if st.button("✏️", key=f"edit_{row['ID']}", help="Edit user", use_container_width=True):
                    edit_user_dialog(row["ID"])
            
            # Tombol Hapus (jangan hapus diri sendiri)
            with cols[8]:
                if row["ID"] != user.id:
                    if st.button("🗑️", key=f"delete_{row['ID']}", help="Hapus user", use_container_width=True):
                        confirm_delete_user(row["ID"], row["Username"])
                else:
                    st.write("-")
            
            # st.divider() tipis
            st.markdown("---")
        
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
                new_password = st.text_input("Password *", type="password")
            with col3:
                new_role = st.selectbox("Role", ["user", "admin"])
            
            col1, col2 = st.columns(2)
            with col1:
                new_display = st.text_input("Display Name", placeholder="Nama tampilan (opsional)")
            with col2:
                new_pic = st.text_input("PIC Recruiter", placeholder="Untuk user role (opsional)")
            
            if st.form_submit_button("Tambah User", type="primary"):
                errors = []
                if not new_username:
                    errors.append("Username wajib diisi")
                if not new_password or len(new_password) < 6:
                    errors.append("Password minimal 6 karakter")
                
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    result = create_user(db, new_username, new_password, new_role, new_pic, new_display)
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
    
    total_users = len(users) if users else 0
    admin_count = len([u for u in users if u.role == "admin"]) if users else 0
    user_count = len([u for u in users if u.role == "user"]) if users else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total User", total_users)
    col2.metric("Admin", admin_count)
    col3.metric("User", user_count)
    
    db.close()
