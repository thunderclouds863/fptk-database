# pages/07_user_management.py
import streamlit as st
import pandas as pd
import re
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import (
    User, FPTK, DBSourcing, UploadLog, UploadStatus, AuditLog, Evidence,
    UploadCycle
)
from core.auth import (
    get_current_user, is_admin, is_it, create_user, reset_password,
    hash_password, invalidate_filter_cache
)
from core.utils import get_filter_options_from_db
from core.upload_cycle import create_upload_cycle, get_cycle_progress, close_cycle
from datetime import datetime


BU_OPTIONS = [
    {"value": "CMD", "label": "CMD - PT Cisarua Mountain Dairy, Tbk"},
    {"value": "JESS", "label": "JESS - PT Java Egg Specialities"},
    {"value": "MS", "label": "MS - PT Macrosentra Niagaboga"},
    {"value": "MP", "label": "MP - PT Macroprima Panganutama"},
    {"value": "CORP", "label": "CORP - Corporate"},
]

BU_LABELS = {b["value"]: b["label"] for b in BU_OPTIONS}
BU_VALUES = [b["value"] for b in BU_OPTIONS]


def generate_kode_pic(business_unit, pic_name):
    if not business_unit or not pic_name:
        return ""
    name_code = re.sub(r'[^A-Za-z]', '', pic_name)[:3].capitalize()
    return f"{business_unit}{name_code}"


def refresh_filter_cache():
    try:
        get_filter_options_from_db.clear()
    except Exception:
        pass
    try:
        invalidate_filter_cache()
    except Exception:
        pass


@st.dialog("HAPUS USER PERMANEN")
def confirm_delete_user(user_id, username):
    st.error(f"PERINGATAN! Anda akan menghapus user **{username}** secara **PERMANEN**!")
    st.markdown("""
    ### Data yang akan ikut terhapus:
    - Semua FPTK milik user ini
    - Semua Sourcing milik user ini
    - Semua Evidence milik user ini
    - Semua Upload Logs milik user ini
    - Semua Audit Logs milik user ini
    """)
    st.warning("TINDAKAN INI TIDAK DAPAT DIBATALKAN!")
    confirm_username = st.text_input(f"Ketik username **{username}** untuk konfirmasi:", placeholder=f"Ketik {username} di sini")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ya, Hapus Permanen", type="primary", use_container_width=True, key="del_user_yes"):
            if confirm_username.strip() == username:
                db = next(get_db())
                try:
                    admin_count = db.query(User).filter(User.role == "admin").count()
                    user_check = db.query(User).filter(User.id == user_id).first()
                    if user_check.role == "admin" and admin_count <= 1:
                        st.error("Tidak bisa menghapus admin terakhir!")
                        db.close()
                        st.stop()

                    db.query(FPTK).filter(FPTK.source_user_id == user_id).delete(synchronize_session=False)
                    db.query(DBSourcing).filter(DBSourcing.source_user_id == user_id).delete(synchronize_session=False)
                    db.query(UploadLog).filter(UploadLog.user_id == user_id).delete(synchronize_session=False)
                    db.query(UploadStatus).filter(UploadStatus.user_id == user_id).delete(synchronize_session=False)
                    db.query(AuditLog).filter(AuditLog.user_id == user_id).delete(synchronize_session=False)
                    db.delete(user_check)
                    db.commit()

                    refresh_filter_cache()
                    st.cache_data.clear()
                    st.success(f"User **{username}** berhasil dihapus permanen!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    db.rollback()
                finally:
                    db.close()
            else:
                st.error(f"Username tidak cocok!")

    with col2:
        if st.button("Batal", use_container_width=True, key="del_user_no"):
            st.cache_data.clear()
            st.rerun()


@st.dialog("Konfirmasi Nonaktifkan User")
def confirm_deactivate_user(user_id, username):
    st.warning(f"Yakin ingin **nonaktifkan** user **{username}**?")
    st.caption("User akan kehilangan akses login. **Semua data TETAP TERSIMPAN**.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ya, Nonaktifkan", type="primary", use_container_width=True, key="deact_user_yes"):
            db = next(get_db())
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.username = f"inactive_{user.username}_{datetime.now().strftime('%Y%m%d')}"
                    user.password_hash = "DISABLED"
                    db.commit()
                    refresh_filter_cache()
                    st.cache_data.clear()
                    st.success(f"User '{username}' berhasil dinonaktifkan!")
                    st.rerun()
                else:
                    st.error("User tidak ditemukan!")
            except Exception as e:
                st.error(f"Error: {str(e)}")
                db.rollback()
            finally:
                db.close()

    with col2:
        if st.button("Batal", use_container_width=True, key="deact_user_no"):
            st.cache_data.clear()
            st.rerun()


@st.dialog("Aktifkan User Kembali")
def confirm_activate_user(user_id, username):
    st.info(f"Aktifkan user **{username}** kembali?")
    st.caption("Password akan direset ke **password123**.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ya, Aktifkan", type="primary", use_container_width=True, key="act_user_yes"):
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
                    refresh_filter_cache()
                    st.cache_data.clear()
                    st.success(f"User '{username}' berhasil diaktifkan! Password: **password123**")
                    st.rerun()
                else:
                    st.error("User tidak ditemukan!")
            except Exception as e:
                st.error(f"Error: {str(e)}")
                db.rollback()
            finally:
                db.close()

    with col2:
        if st.button("Batal", use_container_width=True, key="act_user_no"):
            st.cache_data.clear()
            st.rerun()


@st.dialog("Edit User")
def edit_user_dialog(user_id):
    db = next(get_db())
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        st.error("User tidak ditemukan!")
        db.close()
        return

    is_active = not user.username.startswith("inactive_")
    current_bu = user.business_unit or "CORP"
    current_kode = user.kode_pic or ""
    current_pic = user.pic_recruiter or user.display_name or ""

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
            role_options = ["user", "admin", "it"]
            current_role_index = role_options.index(user.role) if user.role in role_options else 0
            new_role = st.selectbox("Role", role_options, index=current_role_index)
            reset_pw = st.checkbox("Reset Password")
            new_password = st.text_input("Password Baru (min 6 karakter)", type="password", disabled=not reset_pw)

        st.markdown("### Business Unit & Kode PIC")
        st.caption("Kode PIC otomatis dari BU + Nama PIC. Admin bisa override manual.")

        col1, col2 = st.columns(2)
        with col1:
            selected_bu_label = st.selectbox("Business Unit *", [b["label"] for b in BU_OPTIONS], index=bu_index)
            new_bu = [b["value"] for b in BU_OPTIONS if b["label"] == selected_bu_label][0]

        with col2:
            manual_kode = st.text_input("Kode PIC (kosongkan untuk auto-generate)", value=current_kode,
                placeholder="Biarkan kosong untuk auto dari BU + Nama")

        if not manual_kode and new_pic and new_bu:
            auto_kode = generate_kode_pic(new_bu, new_pic)
            st.info(f"Preview Kode PIC otomatis: **{auto_kode}**")
        elif manual_kode:
            st.info(f"Kode PIC manual: **{manual_kode}**")

        if st.form_submit_button("Simpan", type="primary", use_container_width=True):
            errors = []
            if not new_pic:
                errors.append("PIC Recruiter wajib diisi")
            if reset_pw and new_password and len(new_password) < 6:
                errors.append("Password baru minimal 6 karakter")

            if errors:
                for err in errors:
                    st.error(f"{err}")
                st.stop()

            try:
                if new_username != user.username:
                    existing = db.query(User).filter(User.username == new_username).first()
                    if existing and existing.id != user_id:
                        st.error(f"Username '{new_username}' sudah digunakan!")
                        st.stop()

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
                refresh_filter_cache()
                st.cache_data.clear()
                st.success(f"User '{new_username}' berhasil diupdate!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")
                db.rollback()

    db.close()


def show_user_management():
    st.title("👥 User Management")
    st.markdown("Kelola akun user & upload cycle.")

    db = next(get_db())

    if is_it(db):
        st.info("Mode View-Only (IT)")
        tab1, tab2 = st.tabs(["📋 Daftar User", "🔄 Update Cycle"])
        with tab1:
            users = db.query(User).all()
            data = [{
                "ID": u.id, "Username": u.username, "Role": u.role,
                "BU": u.business_unit or "-", "Kode PIC": u.kode_pic or "-",
                "PIC Recruiter": u.pic_recruiter or "-",
                "Status": "Aktif" if not u.username.startswith("inactive_") else "Nonaktif"
            } for u in users]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        with tab2:
            render_upload_cycle_tab(db, None, it_mode=True)
        db.close()
        return

    if not is_admin(db):
        st.error("Hanya Admin yang bisa mengelola User.")
        db.close()
        return

    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        db.close()
        return

    tab1, tab2 = st.tabs(["👤 Daftar User", "🔄 Update Cycle"])

    with tab1:
        render_user_tab(db, user)

    with tab2:
        render_upload_cycle_tab(db, user, it_mode=False)


def render_user_tab(db, current_user):
    st.subheader("📋 Daftar User")
    users = db.query(User).order_by(User.username).all()

    if not users:
        st.info("Belum ada user.")
        return

    data = []
    for u in users:
        is_active = not u.username.startswith("inactive_")
        data.append({
            "ID": u.id, "Username": u.username,
            "Display Name": u.display_name or u.username,
            "Role": u.role, "BU": u.business_unit or "-",
            "Kode PIC": u.kode_pic or "-", "PIC": u.pic_recruiter or "-",
            "Status": "Aktif" if is_active else "Nonaktif",
            "Last Login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "-",
            "Created": u.created_at.strftime("%d/%m/%Y") if u.created_at else "-",
        })
    df = pd.DataFrame(data)

    st.dataframe(df, use_container_width=True, height=350, hide_index=True,
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
        })

    st.markdown("---")
    st.subheader("🔧 Aksi User")

    user_options = {f"{u.username} ({u.display_name or u.username})": u.id for u in users}
    selected_user = st.selectbox("Pilih User", list(user_options.keys()), key="um_user_select")
    selected_id = user_options[selected_user]
    selected_data = db.query(User).filter(User.id == selected_id).first()

    if selected_data:
        is_active = not selected_data.username.startswith("inactive_")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("✏️ Edit User", use_container_width=True):
                edit_user_dialog(selected_id)
        with col2:
            if st.button("🔑 Reset Password", use_container_width=True):
                if reset_password(db, selected_id, "password123"):
                    st.cache_data.clear()
                    st.success(f"Password direset ke: **password123**")
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
            if st.button("🗑️ Hapus", use_container_width=True, type="secondary"):
                confirm_delete_user(selected_id, selected_data.username)
        with col5:
            if is_active:
                st.success("Aktif")
            else:
                st.error("Nonaktif")

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
            selected_bu_label = st.selectbox("Business Unit *", [b["label"] for b in BU_OPTIONS], index=0)
            new_bu = [b["value"] for b in BU_OPTIONS if b["label"] == selected_bu_label][0]

            if new_pic_name and new_bu:
                auto_kode = generate_kode_pic(new_bu, new_pic_name)
                st.text_input("Preview Kode PIC (auto)", value=auto_kode, disabled=True)
            else:
                st.text_input("Preview Kode PIC (auto)", value="", disabled=True, placeholder="Isi BU dan PIC")

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
                    st.error(f"{err}")
            else:
                auto_kode = generate_kode_pic(new_bu, new_pic_name)
                result = create_user(db, new_username, new_password, new_role,
                    new_pic_name, new_display, new_bu, auto_kode)
                if result:
                    refresh_filter_cache()
                    st.cache_data.clear()
                    st.success(f"User '{new_username}' berhasil dibuat! Kode PIC: {auto_kode}")
                    st.rerun()
                else:
                    st.error("Username sudah digunakan atau password kurang dari 6 karakter!")

    st.markdown("---")
    st.subheader("📊 Statistik User")

    users = db.query(User).all()
    if users:
        total_users = len(users)
        admin_count = len([u for u in users if u.role == "admin"])
        user_count = len([u for u in users if u.role == "user"])
        it_count = len([u for u in users if u.role == "it"])
        active_count = len([u for u in users if not u.username.startswith("inactive_")])
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

    if bu_stats:
        st.markdown("**Distribusi User per Business Unit:**")
        bu_df = pd.DataFrame([{"BU": k, "Jumlah": v} for k, v in bu_stats.items()])
        st.dataframe(bu_df, use_container_width=True, hide_index=True)


def render_upload_cycle_tab(db, current_user, it_mode=False):
    if it_mode:
        cycles = db.query(UploadCycle).order_by(UploadCycle.created_at.desc()).all()
        if cycles:
            data = [{
                "ID": c.id, "Nama Cycle": c.cycle_name,
                "Dibuat": c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else "-",
                "Status": "Aktif" if not c.ended_at else "Selesai"
            } for c in cycles]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("Belum ada upload cycle.")
        return

    st.subheader("📋 Riwayat Upload Cycle")
    cycles = db.query(UploadCycle).order_by(UploadCycle.created_at.desc()).all()

    if cycles:
        data = []
        for cycle in cycles:
            progress = get_cycle_progress(db, cycle.id)
            data.append({
                "ID": cycle.id, "Nama Cycle": cycle.cycle_name,
                "Dibuat": cycle.created_at.strftime("%d/%m/%Y %H:%M"),
                "Status": "Aktif" if not cycle.ended_at else "Selesai",
                "Progress": f"{progress['done']}/{progress['total']} ({progress['progress_pct']:.0f}%)"
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada upload cycle.")

    st.markdown("---")
    st.subheader("➕ Buat Upload Cycle Baru")

    with st.form("create_cycle"):
        cycle_name = st.text_input("Nama Cycle", placeholder="Contoh: Periode Januari 2026")
        submitted = st.form_submit_button("Buat Cycle")

        if submitted and cycle_name:
            new_cycle = create_upload_cycle(db, cycle_name, current_user.id)
            refresh_filter_cache()
            st.cache_data.clear()
            st.success(f"Cycle '{cycle_name}' berhasil dibuat!")
            st.rerun()
        elif submitted and not cycle_name:
            st.error("Nama Cycle wajib diisi")

    st.markdown("---")
    st.subheader("📊 Progress Cycle Aktif")

    active_cycle = db.query(UploadCycle).filter(
        UploadCycle.ended_at.is_(None)
    ).order_by(UploadCycle.created_at.desc()).first()

    if active_cycle:
        statuses = db.query(UploadStatus).filter(UploadStatus.cycle_id == active_cycle.id).all()

        if statuses:
            progress_data = []
            for s in statuses:
                user_obj = db.query(User).filter(User.id == s.user_id).first()
                progress_data.append({
                    "User": user_obj.display_name if user_obj else s.user_id,
                    "PIC": user_obj.pic_recruiter if user_obj else "-",
                    "Status": s.status,
                    "First Compile": s.first_compile_at.strftime("%d/%m/%Y") if s.first_compile_at else "-",
                    "Done At": s.done_at.strftime("%d/%m/%Y %H:%M") if s.done_at else "-"
                })
            df_progress = pd.DataFrame(progress_data)

            total = len(df_progress)
            done = len(df_progress[df_progress['Status'] == 'Done'])
            uploading = len(df_progress[df_progress['Status'] == 'Sedang Upload'])
            belum = len(df_progress[df_progress['Status'] == 'Belum Mulai'])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total User", total)
            col2.metric("Done", done, delta=f"{done/total*100:.0f}%" if total else "0%")
            col3.metric("Sedang Upload", uploading)
            col4.metric("Belum Mulai", belum)

            st.dataframe(df_progress, use_container_width=True)

            if done == total:
                if st.button("🔒 Tutup Cycle", type="primary"):
                    close_cycle(db, active_cycle.id)
                    refresh_filter_cache()
                    st.cache_data.clear()
                    st.success("Cycle berhasil ditutup!")
                    st.rerun()
        else:
            st.info("Belum ada user yang terdaftar di cycle ini.")
    else:
        st.info("Tidak ada cycle aktif.")
