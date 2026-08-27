import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, MasterDropdown, FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence
from core.auth import get_current_user, is_admin, create_user, reset_password, hash_password
import pandas as pd

def show_user_management():
    st.title("👥 User Management")
    st.markdown("Kelola akun user.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    if not is_admin(db):
        st.error("Halaman ini hanya untuk Admin.")
        return
    
    # ============================================================
    # DAFTAR USER (DENGAN TOMBOL HAPUS DI KOLOM PERTAMA)
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
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-"
            })
        df = pd.DataFrame(data)
        
        # Tampilkan tabel dengan kolom aksi
        st.dataframe(
            df,
            use_container_width=True,
            height=400,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Username": st.column_config.TextColumn("Username", width="medium"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "Display Name": st.column_config.TextColumn("Display Name", width="medium"),
                "Last Login": st.column_config.TextColumn("Last Login", width="medium"),
                "Created": st.column_config.TextColumn("Created", width="medium"),
            }
        )
        
        # ============================================================
        # FORM HAPUS USER (DI BAWAH TABEL)
        # ============================================================
        st.markdown("---")
        st.subheader("🗑️ Hapus User")
        
        # Filter user yang bisa dihapus (jangan hapus admin yang sedang login)
        delete_options = {}
        for u in users:
            if u.id != user.id:  # Jangan hapus diri sendiri
                display = f"{u.username} ({u.role})"
                delete_options[display] = u.id
        
        if delete_options:
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_delete = st.selectbox("Pilih User yang akan dihapus", list(delete_options.keys()))
            with col2:
                if st.button("🗑️ Hapus User", type="secondary", use_container_width=True):
                    user_id = delete_options[selected_delete]
                    user_to_delete = db.query(User).filter(User.id == user_id).first()
                    
                    if user_to_delete:
                        # Konfirmasi
                        st.warning(f"⚠️ Yakin ingin menghapus user **{user_to_delete.username}**?")
                        st.caption(f"Ini akan menghapus akun dan semua data terkait (FPTK, Sourcing, dll).")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Ya, Hapus", key="confirm_delete_user"):
                                try:
                                    # Hapus data terkait
                                    db.query(Evidence).filter(Evidence.user_id == user_id).delete()
                                    db.query(AuditLog).filter(AuditLog.user_id == user_id).delete()
                                    db.query(UploadStatus).filter(UploadStatus.user_id == user_id).delete()
                                    db.query(UploadLog).filter(UploadLog.user_id == user_id).delete()
                                    db.query(DBSourcing).filter(DBSourcing.source_user_id == user_id).delete()
                                    db.query(FPTK).filter(FPTK.source_user_id == user_id).delete()
                                    db.delete(user_to_delete)
                                    db.commit()
                                    
                                    st.success(f"✅ User '{user_to_delete.username}' berhasil dihapus!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                                    db.rollback()
                        with col2:
                            if st.button("❌ Batal", key="cancel_delete_user"):
                                st.rerun()
        else:
            st.info("Tidak ada user yang bisa dihapus (selain admin yang sedang login).")
    else:
        st.info("Belum ada user.")
    
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
        
        new_display = st.text_input("Display Name", placeholder="Nama tampilan (opsional)")
        
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
                result = create_user(db, new_username, new_password, new_role, None, new_display)
                if result:
                    st.success(f"✅ User '{new_username}' berhasil dibuat!")
                    st.rerun()
                else:
                    st.error("Username sudah digunakan!")
    
    # ============================================================
    # RESET PASSWORD
    # ============================================================
    st.markdown("---")
    st.subheader("🔑 Reset Password User")
    
    user_options = {}
    for u in users:
        if u.id != user.id:  # Jangan reset password sendiri (bisa lewat sidebar)
            user_options[f"{u.username} ({u.role})"] = u.id
    
    if user_options:
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_user = st.selectbox("Pilih User", list(user_options.keys()))
        with col2:
            if selected_user:
                user_id = user_options[selected_user]
                new_pw = st.text_input("Password Baru", type="password", key="reset_pw_input")
                if st.button("🔄 Reset Password", type="primary", use_container_width=True):
                    if new_pw and len(new_pw) >= 6:
                        if reset_password(db, user_id, new_pw):
                            st.success("✅ Password berhasil direset!")
                            st.rerun()
                        else:
                            st.error("❌ Gagal reset password")
                    else:
                        st.error("Password baru minimal 6 karakter")
    else:
        st.info("Tidak ada user lain yang bisa direset passwordnya.")
    
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
