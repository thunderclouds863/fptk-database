import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence
from core.auth import get_current_user, is_admin, create_user, reset_password, hash_password
import pandas as pd
from datetime import datetime

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
    # SESSION STATE UNTUK EDIT
    # ============================================================
    if "edit_user_id" not in st.session_state:
        st.session_state.edit_user_id = None
    if "show_edit_form" not in st.session_state:
        st.session_state.show_edit_form = False
    
    # ============================================================
    # DAFTAR USER DENGAN TOMBOL AKSI
    # ============================================================
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()
    
    if users:
        # Buat data untuk ditampilkan
        data = []
        for u in users:
            # Cek apakah user ini bisa dihapus (jangan hapus diri sendiri)
            can_delete = u.id != user.id
            # Cek apakah user ini bisa diedit (semua user bisa diedit)
            can_edit = True
            
            data.append({
                "ID": u.id,
                "Username": u.username,
                "Role": u.role,
                "Display Name": u.display_name or u.username,
                "PIC": u.pic_recruiter or "-",
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-",
                "Edit": f"✏️ Edit" if can_edit else "-",
                "Hapus": f"🗑️ Hapus" if can_delete else "-"
            })
        df = pd.DataFrame(data)
        
        # Tampilkan tabel dengan tombol aksi
        st.markdown("**Klik tombol Edit atau Hapus di kolom aksi.**")
        
        # Loop untuk menampilkan setiap baris dengan tombol
        for idx, row in df.iterrows():
            col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([0.5, 1.2, 0.7, 1.2, 0.8, 1, 1, 0.8, 0.8])
            
            with col1:
                st.write(row["ID"])
            with col2:
                st.write(row["Username"])
            with col3:
                st.write(row["Role"])
            with col4:
                st.write(row["Display Name"])
            with col5:
                st.write(row["PIC"])
            with col6:
                st.write(row["Last Login"])
            with col7:
                st.write(row["Created"])
            
            # Tombol Edit
            with col8:
                if row["Edit"] != "-":
                    if st.button("✏️", key=f"edit_{row['ID']}", help="Edit user"):
                        st.session_state.edit_user_id = row["ID"]
                        st.session_state.show_edit_form = True
                        st.rerun()
                else:
                    st.write("-")
            
            # Tombol Hapus
            with col9:
                if row["Hapus"] != "-":
                    if st.button("🗑️", key=f"delete_{row['ID']}", help="Hapus user"):
                        # Konfirmasi hapus
                        user_to_delete = db.query(User).filter(User.id == row["ID"]).first()
                        if user_to_delete:
                            with st.expander(f"⚠️ Konfirmasi hapus {user_to_delete.username}", expanded=True):
                                st.warning(f"Yakin ingin menghapus user **{user_to_delete.username}**?")
                                st.caption("Data terkait (FPTK, Sourcing, Evidence, dll) juga akan dihapus.")
                                
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("✅ Ya, Hapus", key=f"confirm_delete_{row['ID']}"):
                                        try:
                                            # Hapus data terkait
                                            db.query(Evidence).filter(Evidence.user_id == row["ID"]).delete()
                                            db.query(AuditLog).filter(AuditLog.user_id == row["ID"]).delete()
                                            db.query(UploadStatus).filter(UploadStatus.user_id == row["ID"]).delete()
                                            db.query(UploadLog).filter(UploadLog.user_id == row["ID"]).delete()
                                            db.query(DBSourcing).filter(DBSourcing.source_user_id == row["ID"]).delete()
                                            db.query(FPTK).filter(FPTK.source_user_id == row["ID"]).delete()
                                            db.delete(user_to_delete)
                                            db.commit()
                                            
                                            st.success(f"✅ User '{user_to_delete.username}' berhasil dihapus!")
                                            st.session_state.show_edit_form = False
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Error: {str(e)}")
                                            db.rollback()
                                with col_no:
                                    if st.button("❌ Batal", key=f"cancel_delete_{row['ID']}"):
                                        st.rerun()
                else:
                    st.write("-")
            
            st.divider()
        
        # ============================================================
        # FORM EDIT USER (Muncul saat tombol Edit diklik)
        # ============================================================
        if st.session_state.show_edit_form and st.session_state.edit_user_id:
            edit_user = db.query(User).filter(User.id == st.session_state.edit_user_id).first()
            if edit_user:
                st.markdown("---")
                st.subheader(f"✏️ Edit User: {edit_user.username}")
                
                with st.form("edit_user_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_display = st.text_input("Display Name", value=edit_user.display_name or "")
                        new_role = st.selectbox("Role", ["user", "admin"], index=0 if edit_user.role == "user" else 1)
                        new_pic = st.text_input("PIC Recruiter", value=edit_user.pic_recruiter or "")
                    with col2:
                        new_username = st.text_input("Username", value=edit_user.username)
                        # Reset password option
                        reset_pw = st.checkbox("Reset Password")
                        new_password = st.text_input("Password Baru (min 6 karakter)", type="password", disabled=not reset_pw)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.form_submit_button("💾 Simpan Perubahan", type="primary"):
                            try:
                                # Cek username duplikat (jika diubah)
                                if new_username != edit_user.username:
                                    existing = db.query(User).filter(User.username == new_username).first()
                                    if existing:
                                        st.error(f"Username '{new_username}' sudah digunakan!")
                                        st.stop()
                                
                                edit_user.username = new_username
                                edit_user.display_name = new_display
                                edit_user.role = new_role
                                edit_user.pic_recruiter = new_pic
                                
                                if reset_pw and new_password and len(new_password) >= 6:
                                    edit_user.password_hash = hash_password(new_password)
                                
                                db.commit()
                                st.success("✅ User berhasil diupdate!")
                                st.session_state.show_edit_form = False
                                st.session_state.edit_user_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()
                    
                    with col2:
                        if st.form_submit_button("❌ Batal"):
                            st.session_state.show_edit_form = False
                            st.session_state.edit_user_id = None
                            st.rerun()
    
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
    
    # ============================================================
    # SUMMARY STATISTICS
    # ============================================================
    st.markdown("---")
    st.subheader("📊 Statistik User")
    
    total_users = len(users)
    admin_count = len([u for u in users if u.role == "admin"])
    user_count = len([u for u in users if u.role == "user"])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total User", total_users)
    col2.metric("Admin", admin_count)
    col3.metric("User", user_count)
