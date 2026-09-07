import streamlit as st
import pandas as pd
import re
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence
from core.auth import get_current_user, is_admin, is_it, create_user, reset_password, hash_password
from datetime import datetime


# ============================================================
# BU MAPPING
# ============================================================
BU_OPTIONS = [
    {"value": "CMD", "label": "CMD - PT Cisarua Mountain Dairy, Tbk"},
    {"value": "JESS", "label": "JESS - PT Java Egg Specialities"},
    {"value": "MS", "label": "MS - PT Macrosentra Niagaboga"},
    {"value": "MP", "label": "MP - PT Macroprima Panganutama"},
    {"value": "CORP", "label": "CORP - Corporate"},
]

BU_LABELS = {b["value"]: b["label"] for b in BU_OPTIONS}
BU_VALUES = [b["value"] for b in BU_OPTIONS]


def generate_kode_pic(business_unit: str, pic_name: str) -> str:
    """
    Generate Kode PIC dari BU dan Nama PIC
    Format: {BU}{3 huruf pertama nama}
    Contoh: CMD + Elsi → CMDEls
    """
    if not business_unit or not pic_name:
        return ""
    # Ambil 3 huruf pertama dari nama (hapus spasi, karakter aneh)
    name_code = re.sub(r'[^A-Za-z]', '', pic_name)[:3].capitalize()
    return f"{business_unit}{name_code}"


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
# DIALOG EDIT USER (LENGKAP DENGAN BU & KODE PIC)
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

    # Current values
    current_bu = user.business_unit or "CORP"
    current_kode = user.kode_pic or ""
    current_pic = user.pic_recruiter or user.display_name or ""

    # Cari index BU
    bu_index = 0
    for i, b in enumerate(BU_OPTIONS):
        if b["value"] == current_bu:
            bu_index = i
            break

    with st.form("edit_user_form"):
        st.markdown("### Data User")
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username", value=user.username, disabled=not is_active)
            new_display = st.text_input("Display Name", value=user.display_name or "")
            new_pic = st.text_input("PIC Recruiter *", value=current_pic)
        with col2:
            # ============================================================
            # ROLE DROPDOWN - SUPPORT "it"
            # ============================================================
            role_options = ["user", "admin", "it"]
            current_role_index = role_options.index(user.role) if user.role in role_options else 0
            new_role = st.selectbox("Role", role_options, index=current_role_index)

            reset_pw = st.checkbox("Reset Password")
            new_password = st.text_input("Password Baru (min 6 karakter)", type="password", disabled=not reset_pw)

        st.markdown("### 🏢 Business Unit & Kode PIC")
        st.caption("Kode PIC otomatis dari BU + Nama PIC. Admin bisa override manual.")

        col1, col2 = st.columns(2)
        with col1:
            # BU dropdown
            selected_bu_label = st.selectbox(
                "Business Unit *",
                [b["label"] for b in BU_OPTIONS],
                index=bu_index
            )
            new_bu = [b["value"] for b in BU_OPTIONS if b["label"] == selected_bu_label][0]

        with col2:
            # Kode PIC - admin bisa override manual
            manual_kode = st.text_input(
                "Kode PIC (kosongkan untuk auto-generate)",
                value=current_kode,
                placeholder="Biarkan kosong untuk auto dari BU + Nama"
            )

        # Auto-generate preview
        if not manual_kode and new_pic and new_bu:
            auto_kode = generate_kode_pic(new_bu, new_pic)
            st.info(f"📋 Preview Kode PIC otomatis: **{auto_kode}**")
        elif manual_kode:
            st.info(f"📋 Kode PIC manual: **{manual_kode}**")

        # Info role
        if new_role == "it":
            st.info("🔍 Role **IT** = View-Only Admin (bisa lihat semua menu admin tapi TIDAK bisa upload/edit/aksi apa pun)")
        elif new_role == "admin":
            st.info("🛠️ Role **Admin** = Akses penuh (upload, edit, manage user, manage cycle)")
        else:
            st.info("👤 Role **User** = Bisa upload data sendiri")

        if not is_active:
            st.warning("⚠️ User ini sudah nonaktif. Ubah username (hapus 'inactive_') untuk mengaktifkan.")

        if st.form_submit_button("💾 Simpan", type="primary", use_container_width=True):
            errors = []
            if not new_pic:
                errors.append("PIC Recruiter wajib diisi")
            if reset_pw and new_password and len(new_password) < 6:
                errors.append("Password baru minimal 6 karakter")

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
                st.stop()

            try:
                # Cek duplikat username
                if new_username != user.username:
                    existing = db.query(User).filter(User.username == new_username).first()
                    if existing and existing.id != user_id:
                        st.error(f"Username '{new_username}' sudah digunakan!")
                        st.stop()

                # Tentukan Kode PIC final
                final_kode = manual_kode.strip() if manual_kode else None
                if not final_kode and new_pic and new_bu:
                    final_kode = generate_kode_pic(new_bu, new_pic)

                user.username = new_username
                user.display_name = new_display
                user.pic_recruiter = new_pic
                user.role = new_role
                user.business_unit = new_bu
                if final_kode:
                    user.kode_pic = final_kode

                if reset_pw and new_password and len(new_password) >= 6:
                    user.password_hash = hash_password(new_password)

                db.commit()
                st.success(f"✅ User '{new_username}' berhasil diupdate! Kode PIC: {final_kode}")
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
    st.markdown("Kelola akun user, Business Unit, dan Kode PIC.")

    db = next(get_db())

    # ============================================================
    # CHECK ACCESS - IT (VIEW-ONLY)
    # ============================================================
    if is_it(db):
        st.info("🔍 Mode View-Only (IT)")
        users = db.query(User).all()
        data = [{
            "ID": u.id,
            "Username": u.username,
            "Role": u.role,
            "BU": u.business_unit or "-",
            "Kode PIC": u.kode_pic or "-",
            "PIC Recruiter": u.pic_recruiter or "-",
            "Status": "✅ Aktif" if not u.username.startswith("inactive_") else "⛔ Nonaktif"
        } for u in users]
        st.dataframe(pd.DataFrame(data), use_container_width=True)
        db.close()
        return

    # ============================================================
    # CHECK ACCESS - ADMIN ONLY
    # ============================================================
    if not is_admin(db):
        st.error("Hanya Admin yang bisa mengelola User.")
        db.close()
        return

    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        db.close()
        return

    # ============================================================
    # DAFTAR USER
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
                "Display Name": u.display_name or u.username,
                "Role": u.role,
                "BU": u.business_unit or "-",
                "Kode PIC": u.kode_pic or "-",
                "PIC": u.pic_recruiter or "-",
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
                "Display Name": st.column_config.TextColumn("Display Name", width="medium"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "BU": st.column_config.TextColumn("BU", width="small"),
                "Kode PIC": st.column_config.TextColumn("Kode PIC", width="small"),
                "PIC": st.column_config.TextColumn("PIC Recruiter", width="medium"),
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

            # Tampilkan detail BU & Kode PIC user yang dipilih
            with st.expander("📋 Detail User Terpilih", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Username:** {selected_data.username}")
                    st.markdown(f"**Display Name:** {selected_data.display_name or '-'}")
                    st.markdown(f"**Role:** {selected_data.role}")
                with col2:
                    st.markdown(f"**Business Unit:** {selected_data.business_unit or '-'}")
                    st.markdown(f"**Kode PIC:** {selected_data.kode_pic or '-'}")
                    st.markdown(f"**PIC Recruiter:** {selected_data.pic_recruiter or '-'}")

        # ============================================================
        # TAMBAH USER BARU (DENGAN BU & KODE PIC)
        # ============================================================
        st.markdown("---")
        st.subheader("➕ Tambah User Baru")

        with st.form("add_user"):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_username = st.text_input("Username *", placeholder="contoh: pauline")
            with col2:
                new_password = st.text_input("Password *", type="password", value="password123")
            with col3:
                new_role = st.selectbox("Role", ["user", "admin", "it"], index=0)

            col1, col2 = st.columns(2)
            with col1:
                new_display = st.text_input("Display Name *", placeholder="Nama tampilan")
                new_pic_name = st.text_input("PIC Recruiter *", placeholder="Nama PIC (contoh: Pauline)")
            with col2:
                # Pilih BU
                selected_bu_label = st.selectbox(
                    "Business Unit *",
                    [b["label"] for b in BU_OPTIONS],
                    index=0
                )
                new_bu = [b["value"] for b in BU_OPTIONS if b["label"] == selected_bu_label][0]

                # Auto-generate preview kode PIC
                if new_pic_name and new_bu:
                    auto_kode = generate_kode_pic(new_bu, new_pic_name)
                    st.text_input("Preview Kode PIC (auto)", value=auto_kode, disabled=True)
                else:
                    st.text_input("Preview Kode PIC (auto)", value="", disabled=True, placeholder="Isi BU dan PIC")

            # Info role
            if new_role == "it":
                st.info("🔍 Role **IT** = View-Only Admin (bisa lihat semua menu admin tapi TIDAK bisa upload/edit/aksi apa pun)")
            elif new_role == "admin":
                st.info("🛠️ Role **Admin** = Akses penuh")
            else:
                st.info("👤 Role **User** = Bisa upload data sendiri")

            if st.form_submit_button("Tambah User", type="primary"):
                errors = []
                if not new_username:
                    errors.append("Username wajib diisi")
                if not new_password or len(new_password) < 6:
                    errors.append("Password minimal 6 karakter")
                if not new_display:
                    errors.append("Display Name wajib diisi")
                if not new_pic_name:
                    errors.append("PIC Recruiter wajib diisi")

                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    # Auto-generate kode PIC
                    auto_kode = generate_kode_pic(new_bu, new_pic_name)
                    result = create_user(
                        db,
                        new_username,
                        new_password,
                        new_role,
                        new_pic_name,
                        new_display,
                        new_bu,
                        auto_kode
                    )
                    if result:
                        st.success(f"✅ User '{new_username}' berhasil dibuat! Kode PIC: {auto_kode}")
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
        it_count = len([u for u in users if u.role == "it"])
        active_count = len([u for u in users if not u.username.startswith("inactive_")])
        # Statistik per BU
        bu_stats = {}
        for u in users:
            bu = u.business_unit or "Unknown"
            bu_stats[bu] = bu_stats.get(bu, 0) + 1
    else:
        total_users = admin_count = user_count = it_count = active_count = 0
        bu_stats = {}

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total User", total_users)
    col2.metric("Admin", admin_count)
    col3.metric("User", user_count)
    col4.metric("IT", it_count)
    col5.metric("Aktif", active_count)

    # Statistik per BU
    if bu_stats:
        st.markdown("**Distribusi User per Business Unit:**")
        bu_df = pd.DataFrame([{"BU": k, "Jumlah": v} for k, v in bu_stats.items()])
        st.dataframe(bu_df, use_container_width=True, hide_index=True)

    db.close()
