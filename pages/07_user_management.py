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
    # SESSION STATE
    # ============================================================
    if "edit_user_id" not in st.session_state:
        st.session_state.edit_user_id = None
    if "show_edit_form" not in st.session_state:
        st.session_state.show_edit_form = False
    if "delete_user_id" not in st.session_state:
        st.session_state.delete_user_id = None
    if "show_delete_popover" not in st.session_state:
        st.session_state.show_delete_popover = False
    
    # ============================================================
    # DAFTAR USER DENGAN TABEL RAPI
    # ============================================================
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()
    
    if users:
        # Buat data untuk tabel
        data = []
        for u in users:
            can_delete = u.id != user.id
            data.append({
                "ID": u.id,
                "Username": u.username,
                "Role": "🛡️ Admin" if u.role == "admin" else "👤 User",
                "Display Name": u.display_name or u.username,
                "PIC": u.pic_recruiter or "-",
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-",
            })
        df = pd.DataFrame(data)
        
        # Tampilkan tabel dengan styling
        st.dataframe(
            df,
            use_container_width=True,
            height=400,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Username": st.column_config.TextColumn("Username", width="small"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "Display Name": st.column_config.TextColumn("Display Name", width="medium"),
                "PIC": st.column_config.TextColumn("PIC", width="small"),
                "Last Login": st.column_config.TextColumn("Last Login", width="medium"),
                "Created": st.column_config.TextColumn("Created", width="medium"),
            },
            hide_index=True,
        )
        
        # ============================================================
        # TOMBOL AKSI DI BAWAH TABEL (Edit / Hapus per User)
        # ============================================================
        st.markdown("---")
        st.markdown("**Pilih user untuk diedit atau dihapus:**")
        
        # Dropdown pilih user
        user_options = {}
        for u in users:
            label = f"{u.username} ({u.role}) - {u.display_name or u.username}"
            user_options[label] = u.id
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            selected_user_label = st.selectbox("Pilih User", list(user_options.keys()), key="user_action_select")
            selected_user_id = user_options[selected_user_label]
            selected_user_obj = db.query(User).filter(User.id == selected_user_id).first()
        
        with col2:
            # Tombol Edit
            if st.button("✏️ Edit", use_container_width=True, type="primary"):
                st.session_state.edit_user_id = selected_user_id
                st.session_state.show_edit_form = True
                st.rerun()
        
        with col3:
            # Tombol Hapus (disabled jika user sedang login)
            if selected_user_id == user.id:
                st.button("🗑️ Hapus", use_container_width=True, disabled=True, help="Tidak bisa menghapus diri sendiri")
            else:
                if st.button("🗑️ Hapus", use_container_width=True, type="secondary"):
                    st.session_state.delete_user_id = selected_user_id
                    st.session_state.show_delete_popover = True
                    st.rerun()
        
        # ============================================================
        # POPUP KONFIRMASI HAPUS
        # ============================================================
        if st.session_state.show_delete_popover and st.session_state.delete_user_id:
            delete_user = db.query(User).filter(User.id == st.session_state.delete_user_id).first()
            if delete_user:
                with st.popover("⚠️ Konfirmasi Hapus", use_container_width=True):
                    st.warning(f"Yakin ingin menghapus user **{delete_user.username}**?")
                    st.caption(f"Role: {delete_user.role}")
                    st.caption(f"Display: {delete_user.display_name or '-'}")
                    st.caption(f"PIC: {delete_user.pic_recruiter or '-'}")
                    st.caption("⚠️ Semua data terkait (FPTK, Sourcing, Evidence, dll) akan dihapus.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Ya, Hapus", type="primary", use_container_width=True):
                            try:
                                # Hapus data terkait
                                db.query(Evidence).filter(Evidence.user_id == st.session_state.delete_user_id).delete()
                                db.query(AuditLog).filter(AuditLog.user_id == st.session_state.delete_user_id).delete()
                                db.query(UploadStatus).filter(UploadStatus.user_id == st.session_state.delete_user_id).delete()
                                db.query(UploadLog).filter(UploadLog.user_id == st.session_state.delete_user_id).delete()
                                db.query(DBSourcing).filter(DBSourcing.source_user_id == st.session_state.delete_user_id).delete()
                                db.query(FPTK).filter(FPTK.source_user_id == st.session_state.delete_user_id).delete()
                                db.delete(delete_user)
                                db.commit()
                                
                                st.success(f"✅ User '{delete_user.username}' berhasil dihapus!")
                                st.session_state.show_delete_popover = False
                                st.session_state.delete_user_id = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()
                    with col2:
                        if st.button("❌ Batal", use_container_width=True):
                            st.session_state.show_delete_popover = False
                            st.session_state.delete_user_id = None
                            st.rerun()
        
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
                        new_username = st.text_input("Username", value=edit_user.username)
                        new_display = st.text_input("Display Name", value=edit_user.display_name or "")
                        new_pic = st.text_input("PIC Recruiter", value=edit_user.pic_recruiter or "")
                    with col2:
                        new_role = st.selectbox("Role", ["user", "admin"], index=0 if edit_user.role == "user" else 1)
                        reset_pw = st.checkbox("Reset Password")
                        new_password = st.text_input("Password Baru (min 6 karakter)", type="password", disabled=not reset_pw)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.form_submit_button("💾 Simpan", type="primary", use_container_width=True):
                            try:
                                # Cek username duplikat
                                if new_username != edit_user.username:
                                    existing = db.query(User).filter(User.username == new_username).first()
                                    if existing:
                                        st.error(f"Username '{new_username}' sudah digunakan!")
                                        st.stop()
                                
                                edit_user.username = new_username
                                edit_user.display_name = new_display
                                edit_user.role = new_role
                                edit_user.pic_recruiter = new_pic if new_pic else None
                                
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
                        if st.form_submit_button("❌ Batal", use_container_width=True):
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
