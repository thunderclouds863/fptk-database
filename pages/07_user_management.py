import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, MasterDropdown
from core.auth import get_current_user, is_admin, create_user, reset_password, hash_password
import pandas as pd

def show_user_management():
    st.title("👥 User Management")
    st.markdown("Kelola akun user, PIC Recruiter, dan BU.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    if not is_admin(db):
        st.error("Halaman ini hanya untuk Admin.")
        return
    
    # ============================================================
    # DAFTAR USER (DENGAN BU)
    # ============================================================
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()
    
    # Ambil data master dropdown untuk mapping PIC -> BU
    master_data = db.query(MasterDropdown).all()
    pic_to_bu = {}
    for m in master_data:
        if m.pic_recruiter and m.bu:
            pic_to_bu[m.pic_recruiter] = m.bu
    
    if users:
        data = []
        for u in users:
            # Ambil BU dari mapping
            bu = pic_to_bu.get(u.pic_recruiter, "-") if u.pic_recruiter else "-"
            
            # Cek apakah user punya FPTK data
            from core.models import FPTK
            fptk_count = db.query(FPTK).filter(FPTK.pic_recruiter == u.pic_recruiter).count() if u.pic_recruiter else 0
            
            data.append({
                "ID": u.id,
                "Username": u.username,
                "Role": u.role,
                "PIC Recruiter": u.pic_recruiter or "-",
                "BU": bu,
                "Display Name": u.display_name or u.username,
                "Jumlah FPTK": fptk_count,
                "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
                "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-"
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=400)
        
        # ============================================================
        # HAPUS USER
        # ============================================================
        st.markdown("---")
        st.subheader("🗑️ Hapus User")
        
        # Filter user yang bisa dihapus (jangan hapus admin yang sedang login)
        delete_options = {}
        for u in users:
            if u.id != user.id:  # Jangan hapus diri sendiri
                display = f"{u.username} ({u.pic_recruiter or 'No PIC'}) - {u.role}"
                delete_options[display] = u.id
        
        if delete_options:
            selected_delete = st.selectbox("Pilih User yang akan dihapus", list(delete_options.keys()))
            
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("🗑️ Hapus User", type="secondary"):
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
                                    from core.models import FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence
                                    
                                    # Hapus evidence
                                    db.query(Evidence).filter(Evidence.user_id == user_id).delete()
                                    # Hapus audit log
                                    db.query(AuditLog).filter(AuditLog.user_id == user_id).delete()
                                    # Hapus upload status
                                    db.query(UploadStatus).filter(UploadStatus.user_id == user_id).delete()
                                    # Hapus upload log
                                    db.query(UploadLog).filter(UploadLog.user_id == user_id).delete()
                                    # Hapus sourcing (jika ada)
                                    db.query(DBSourcing).filter(DBSourcing.source_user_id == user_id).delete()
                                    # Hapus FPTK (jika ada)
                                    db.query(FPTK).filter(FPTK.source_user_id == user_id).delete()
                                    # Hapus user
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
    # TAMBAH USER BARU (DENGAN BU)
    # ============================================================
    st.markdown("---")
    st.subheader("➕ Tambah User Baru")
    
    # Ambil daftar PIC + BU dari master dropdown
    pic_bu_options = {}
    for m in master_data:
        if m.pic_recruiter and m.bu:
            pic_bu_options[f"{m.pic_recruiter} ({m.bu})"] = m.pic_recruiter
    
    # Tambahkan opsi custom
    pic_bu_options["Custom (isi manual)"] = "CUSTOM"
    
    with st.form("add_user"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_username = st.text_input("Username *")
        with col2:
            new_password = st.text_input("Password *", type="password")
        with col3:
            new_role = st.selectbox("Role", ["user", "admin"])
        
        # PIC Recruiter dengan BU
        selected_pic_bu = st.selectbox(
            "PIC Recruiter (pilih dari daftar atau custom)", 
            list(pic_bu_options.keys())
        )
        
        if selected_pic_bu == "Custom (isi manual)":
            new_pic = st.text_input("PIC Recruiter (custom)", placeholder="Contoh: Pauline, Karin, dll")
            new_bu = st.text_input("Business Unit (custom)", placeholder="Contoh: PT CISARUA MOUNTAIN DAIRY, TBK")
        else:
            new_pic = pic_bu_options[selected_pic_bu]
            # Cari BU dari master
            new_bu = ""
            for m in master_data:
                if m.pic_recruiter == new_pic and m.bu:
                    new_bu = m.bu
                    break
            st.info(f"📋 BU: **{new_bu or 'Belum diset'}**")
        
        new_display = st.text_input("Display Name", placeholder="Nama tampilan (opsional)")
        
        if st.form_submit_button("Tambah User"):
            errors = []
            if not new_username:
                errors.append("Username wajib diisi")
            if not new_password or len(new_password) < 6:
                errors.append("Password minimal 6 karakter")
            if selected_pic_bu == "Custom (isi manual)" and not new_pic:
                errors.append("PIC Recruiter wajib diisi untuk user role")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                # Jika custom dan ada BU, tambahkan ke master dropdown
                if selected_pic_bu == "Custom (isi manual)" and new_pic:
                    # Cek apakah PIC sudah ada di master
                    existing_master = db.query(MasterDropdown).filter(
                        MasterDropdown.pic_recruiter == new_pic
                    ).first()
                    if not existing_master and new_bu:
                        # Tambahkan ke master dropdown
                        new_master = MasterDropdown(
                            pic_recruiter=new_pic,
                            bu=new_bu,
                            is_active=True
                        )
                        db.add(new_master)
                        db.commit()
                        st.info(f"✅ PIC '{new_pic}' dengan BU '{new_bu}' ditambahkan ke master dropdown.")
                    elif not existing_master and not new_bu:
                        st.warning(f"⚠️ PIC '{new_pic}' tidak ada di master dropdown. Silakan isi BU.")
                
                result = create_user(db, new_username, new_password, new_role, new_pic, new_display)
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
        if u.role == "user" and u.pic_recruiter:
            bu = pic_to_bu.get(u.pic_recruiter, "-")
            user_options[f"{u.username} ({u.pic_recruiter}) - BU: {bu}"] = u.id
    
    if user_options:
        selected_user = st.selectbox("Pilih User", list(user_options.keys()))
        
        if selected_user:
            user_id = user_options[selected_user]
            new_pw = st.text_input("Password Baru", type="password")
            if st.button("🔄 Reset Password", type="primary"):
                if new_pw and len(new_pw) >= 6:
                    if reset_password(db, user_id, new_pw):
                        st.success("✅ Password berhasil direset!")
                    else:
                        st.error("❌ Gagal reset password")
                else:
                    st.error("Password baru minimal 6 karakter")
    else:
        st.info("Tidak ada user (non-admin) yang bisa direset password.")
    
    # ============================================================
    # SUMMARY STATISTICS
    # ============================================================
    st.markdown("---")
    st.subheader("📊 Statistik User")
    
    total_users = len(users)
    admin_count = len([u for u in users if u.role == "admin"])
    user_count = len([u for u in users if u.role == "user"])
    
    # Hitung user dengan data
    from core.models import FPTK
    active_users = 0
    for u in users:
        if u.pic_recruiter:
            count = db.query(FPTK).filter(FPTK.pic_recruiter == u.pic_recruiter).count()
            if count > 0:
                active_users += 1
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total User", total_users)
    col2.metric("Admin", admin_count)
    col3.metric("User (PIC)", user_count)
    col4.metric("Aktif (punya FPTK)", active_users)
