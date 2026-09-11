import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import FPTK, User, MasterDropdown, FPTKDeleteRequest
from core.auth import get_current_user, is_admin
from core.utils import get_filter_options_from_db
from datetime import datetime, timedelta
import plotly.express as px
import re
import time


# ============================================================
#  CACHE FUNCTIONS
# ============================================================

@st.cache_data(ttl=3600)
def get_level_options_fptk():
    LEVEL_OPTIONS = []
    for num in range(1, 6):
        for letter in ['A', 'B']:
            LEVEL_OPTIONS.append(f"{num}{letter}")
    return LEVEL_OPTIONS


@st.cache_data(ttl=3600)
def get_detail_sla_options():
    return [
        "OP Belum Lewat SLA",
        "OP Tidak Lulus SLA",
        "Closed Lulus SLA",
        "Closed Tidak Lulus SLA",
        "Cancel FPTK"
    ]


# ============================================================
#  FALLBACK OPSI
# ============================================================

FALLBACK_BU_OPTIONS = [
    "PT CISARUA MOUNTAIN DAIRY, TBK",
    "PT JAVA EGG SPECIALITIES",
    "PT MACROSENTRA NIAGABOGA",
    "PT MACROPRIMA PANGANUTAMA",
    "PT ARTHA RASA CIMORY",
    "PT MACROTAMA BINASANTIKA",
]

FALLBACK_DIREKTORAT_OPTIONS = [
    "CEO Office",
    "CEO, Corsec, & Investor Relation",
    "Commercial CMD",
    "Commercial JES",
    "Commercial MP",
    "Finance & Business Support",
    "Logistic & Distribution",
    "Manufacture CMD",
    "Manufacture JES",
    "Manufacture MP",
    "Procurement CMD & Corporate",
    "Procurement MP & JES",
    "Sales General Trade CMD",
    "Sales General Trade JES",
    "Sales General Trade MP",
    "Sales International Market",
    "Sales Modern Trade",
]

FALLBACK_FILTER_KATEGORISASI = [
    "CLAP FGDP",
    "STO",
    "Level 1-2",
    "Level 3",
    "Level 4",
]


# ============================================================
#  FUNGSI UPDATE SLA OTOMATIS
# ============================================================

def calculate_detail_sla_auto(status, fptk_date_real, deadline_sla, offering_date, fptk_cancel_date, today=None):
    if today is None:
        today = datetime.now().date()

    if status == "Cancel":
        return "Cancel FPTK"

    if status == "Closed":
        if offering_date and deadline_sla:
            if offering_date <= deadline_sla:
                return "Closed Lulus SLA"
            else:
                return "Closed Tidak Lulus SLA"
        else:
            if fptk_date_real and deadline_sla:
                if today <= deadline_sla:
                    return "OP Belum Lewat SLA"
                else:
                    return "OP Tidak Lulus SLA"
            return "OP Belum Lewat SLA"

    if status == "OP":
        if deadline_sla:
            if today <= deadline_sla:
                return "OP Belum Lewat SLA"
            else:
                return "OP Tidak Lulus SLA"
        else:
            return "OP Belum Lewat SLA"

    return "OP Belum Lewat SLA"


def update_all_sla_bulk(db):
    today = datetime.now().date()
    updated_count = 0

    try:
        fptk_list = db.query(FPTK).filter(
            FPTK.status.in_(["OP", "Closed", "Cancel"])
        ).all()

        for fptk in fptk_list:
            new_detail_sla = calculate_detail_sla_auto(
                status=fptk.status,
                fptk_date_real=fptk.fptk_date_real,
                deadline_sla=fptk.deadline_sla,
                offering_date=fptk.offering_date,
                fptk_cancel_date=fptk.fptk_cancel_date,
                today=today
            )

            if fptk.detail_sla != new_detail_sla:
                fptk.detail_sla = new_detail_sla
                fptk.last_updated_at = datetime.now()
                updated_count += 1

        if updated_count > 0:
            db.commit()
            return updated_count
        return 0
    except Exception as e:
        db.rollback()
        print(f"Error updating SLA: {str(e)}")
        return -1


# ============================================================
#  DIALOG: PIC REQUEST HAPUS
# ============================================================

@st.dialog("📩 Request Hapus FPTK ke Admin")
def request_delete_fptk(fptk_id: int, kode_unik: str, posisi: str, pic_name: str):
    st.info(f"**FPTK:** {kode_unik} | {posisi}")
    st.caption("Request Anda akan dikirim ke Admin untuk di-approve.")

    reason = st.text_area(
        "Alasan Request Hapus *",
        placeholder="Contoh: FPTK duplikat, salah input, dibatalkan user, dll.",
        height=150,
        key="reason_delete_fptk"
    )

    st.caption("⚠️ **Alasan wajib diisi** minimal 10 karakter.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Kirim Request", type="primary", use_container_width=True):
            if not reason or len(reason.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                db = next(get_db())
                try:
                    existing = db.query(FPTKDeleteRequest).filter(
                        FPTKDeleteRequest.fptk_id == fptk_id,
                        FPTKDeleteRequest.status == "PENDING"
                    ).first()

                    if existing:
                        st.warning("⚠️ Request hapus untuk FPTK ini sudah ada dan masih PENDING.")
                    else:
                        user = get_current_user(db)
                        new_request = FPTKDeleteRequest(
                            fptk_id=fptk_id,
                            kode_unik=kode_unik,
                            posisi=posisi,
                            pic_recruiter=pic_name,
                            reason=reason.strip(),
                            status="PENDING",
                            requested_by=user.id if user else None,
                            requested_by_name=user.display_name if user else "Unknown",
                            requested_at=datetime.now()
                        )
                        db.add(new_request)
                        db.commit()

                        st.success("✅ Request hapus berhasil dikirim ke Admin!")
                        time.sleep(0.5)
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
                finally:
                    db.close()

    with col2:
        if st.button("❌ Batal", use_container_width=True):
            st.rerun()


# ============================================================
#  DIALOG: ADMIN HAPUS LANGSUNG
# ============================================================

@st.dialog("⚠️ HAPUS FPTK PERMANEN")
def confirm_delete_fptk(fptk_id: int, kode_unik: str, posisi: str):
    st.error(f"⚠️ Anda akan menghapus FPTK **{kode_unik}** - **{posisi}** secara PERMANEN!")
    st.warning("⚠️ **TINDAKAN INI TIDAK DAPAT DIBATALKAN!**")

    confirm_kode = st.text_input(
        f"Ketik kode unik **{kode_unik}** untuk konfirmasi:",
        placeholder=f"Ketik {kode_unik} di sini"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Ya, Hapus Permanen", type="primary", use_container_width=True):
            if confirm_kode.strip() == kode_unik:
                db = next(get_db())
                try:
                    fptk = db.query(FPTK).filter(FPTK.id == fptk_id).first()
                    if fptk:
                        try:
                            from core.models import TransferHistory
                            db.query(TransferHistory).filter(
                                TransferHistory.fptk_id == fptk_id
                            ).delete(synchronize_session=False)
                        except Exception:
                            pass

                        db.query(FPTKDeleteRequest).filter(
                            FPTKDeleteRequest.fptk_id == fptk_id
                        ).delete(synchronize_session=False)

                        db.delete(fptk)
                        db.commit()

                        st.cache_data.clear()
                        st.success(f"✅ FPTK **{kode_unik}** berhasil dihapus!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("FPTK tidak ditemukan!")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
                finally:
                    db.close()
            else:
                st.error(f"❌ Kode unik tidak cocok!")

    with col2:
        if st.button("❌ Batal", use_container_width=True):
            st.rerun()


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show_fptk_view():
    st.title("📋 FPTK Database")
    st.markdown("Lihat semua data FPTK. Edit hanya untuk data milik PIC Anda (Admin bisa semua).")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)

    # ============================================================
    #  AUTO UPDATE SLA
    # ============================================================
    with st.spinner("🔄 Memeriksa dan memperbarui SLA..."):
        updated = update_all_sla_bulk(db)
        if updated > 0:
            st.success(f"✅ {updated} data FPTK diperbarui SLA-nya secara otomatis!")
        time.sleep(0.3)

    # ============================================================
    # LOAD FILTER OPTIONS
    # ============================================================
    filter_opts = get_filter_options_from_db()

    pic_options_all = filter_opts.get("pic_options", [])
    if not pic_options_all:
        try:
            master_records = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
            pic_options_all = sorted(set([m.pic_recruiter for m in master_records if m.pic_recruiter]))
        except Exception:
            pic_options_all = []

    bu_options = filter_opts.get("bu_options", []) or FALLBACK_BU_OPTIONS
    direktorat_options = filter_opts.get("direktorat_options", []) or FALLBACK_DIREKTORAT_OPTIONS
    filter_kategorisasi_options = filter_opts.get("filter_kategorisasi_options", []) or FALLBACK_FILTER_KATEGORISASI

    status_options = ["OP", "Closed", "Cancel"]
    LEVEL_OPTIONS = get_level_options_fptk()
    detail_sla_options = get_detail_sla_options()

    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter FPTK")

        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
        status_filter = st.selectbox("Status", ["Semua"] + status_options)
        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + pic_options_all)
        bu_filter = st.selectbox("Business Unit", ["Semua"] + bu_options)
        dir_filter = st.selectbox("Direktorat", ["Semua"] + direktorat_options)
        filter_kat_options = ["Semua"] + filter_kategorisasi_options
        filter_kat = st.selectbox("Filter Kategorisasi", filter_kat_options)

        st.markdown("---")

        if st.button("🔄 Refresh SLA Now", use_container_width=True, type="primary"):
            with st.spinner("Memperbarui SLA..."):
                updated = update_all_sla_bulk(db)
                if updated > 0:
                    st.success(f"✅ {updated} data SLA diperbarui!")
                else:
                    st.info("✅ Semua SLA sudah sesuai.")
                time.sleep(0.5)
                st.rerun()

        if st.button("🔄 Refresh Filter Options", use_container_width=True):
            get_filter_options_from_db.clear()
            st.success("✅ Filter refreshed!")
            time.sleep(0.3)
            st.rerun()

        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()

    # ============================================================
    # BUILD QUERY
    # ============================================================
    query = db.query(FPTK)

    if search:
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{search}%")) |
            (FPTK.posisi.ilike(f"%{search}%"))
        )
    if status_filter != "Semua":
        query = query.filter(FPTK.status == status_filter)
    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)
    if bu_filter != "Semua":
        query = query.filter(FPTK.business_unit == bu_filter)
    if dir_filter != "Semua":
        query = query.filter(FPTK.direktorat == dir_filter)
    if filter_kat != "Semua":
        query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)

    total = query.count()

    # ============================================================
    # METRIK CARD
    # ============================================================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total FPTK", total)

    if total > 0:
        df_all = pd.read_sql(query.statement, db.bind)
        op_count = len(df_all[df_all['status'] == 'OP']) if 'status' in df_all else 0
        closed_count = len(df_all[df_all['status'] == 'Closed']) if 'status' in df_all else 0
        cancel_count = len(df_all[df_all['status'] == 'Cancel']) if 'status' in df_all else 0

        col2.metric("OP", op_count)
        col3.metric("Closed", closed_count)
        col4.metric("Cancel", cancel_count)
    else:
        col2.metric("OP", 0)
        col3.metric("Closed", 0)
        col4.metric("Cancel", 0)
        st.info("Tidak ada data FPTK dengan filter yang dipilih.")
        return

    st.markdown("---")

    # ============================================================
    # TABEL LIST FPTK
    # ============================================================
    st.markdown("### 📋 Daftar FPTK")

    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
    offset = (page - 1) * page_size

    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)

    if 'fptk_date_real' in df.columns:
        df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'])
        df['FPTK Date Real'] = df['fptk_date_real'].dt.strftime('%d/%m/%Y')

    display_cols = ['FPTK Date Real', 'kode_unik', 'posisi', 'pic_recruiter', 'business_unit',
                    'direktorat', 'status', 'filter_kategorisasi_fptk',
                    'vacancy', 'level_fptk', 'jumlah_sla', 'detail_sla']
    available_cols = [c for c in display_cols if c in df.columns]

    if not df.empty:
        st.dataframe(df[available_cols], use_container_width=True, height=400)

    # ============================================================
    # PILIH DATA
    # ============================================================
    st.markdown("---")
    st.markdown("### ✏️ Pilih Data FPTK")

    df_all = pd.read_sql(query.statement, db.bind)

    if not df_all.empty:
        select_options = {}
        for _, row in df_all.iterrows():
            kode = row.get('kode_unik', '')
            posisi = row.get('posisi', '')
            display = f"{kode} | {posisi[:50]}..." if len(posisi) > 50 else f"{kode} | {posisi}"
            select_options[display] = row.get('id')

        selected_display = st.selectbox("Pilih FPTK", list(select_options.keys()))
        selected_id = select_options.get(selected_display)
    else:
        selected_id = None

    if not selected_id:
        return

    detail = db.query(FPTK).filter(FPTK.id == selected_id).first()
    if not detail:
        st.error("Data tidak ditemukan")
        return

    can_edit = admin or (detail.pic_recruiter == user.pic_recruiter)

    # ============================================================
    # ⚙️ AKSI DATA
    # ============================================================
    st.markdown("---")
    st.markdown("### ⚙️ Aksi Data")

    existing_request = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.fptk_id == detail.id,
        FPTKDeleteRequest.status == "PENDING"
    ).first()

    all_requests = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.fptk_id == detail.id
    ).order_by(FPTKDeleteRequest.requested_at.desc()).all()

    col1, col2, col3 = st.columns(3)

    # ADMIN: Hapus langsung
    if admin:
        with col1:
            if st.button("🗑️ Hapus Langsung (Admin)", type="secondary", use_container_width=True):
                confirm_delete_fptk(detail.id, detail.kode_unik, detail.posisi)

        with col2:
            if existing_request:
                st.warning(f"📩 Pending dari {existing_request.requested_by_name}")
            else:
                st.caption("Tidak ada request pending")

        with col3:
            if all_requests:
                with st.expander(f"📋 History ({len(all_requests)})"):
                    for req in all_requests:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.status}**")
                        st.caption(f"By: {req.requested_by_name} — {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")
                        st.caption(f"Alasan: {req.reason}")
                        if req.admin_notes:
                            st.caption(f"Admin: {req.admin_notes}")
                        st.markdown("---")

    # PIC: Request hapus
    else:
        with col1:
            if existing_request:
                st.info(f"📩 Request Anda PENDING — {existing_request.requested_at.strftime('%d/%m/%Y %H:%M')}")
            else:
                if detail.pic_recruiter == user.pic_recruiter:
                    if st.button("📩 Request Hapus ke Admin", type="primary", use_container_width=True):
                        request_delete_fptk(detail.id, detail.kode_unik, detail.posisi, detail.pic_recruiter)
                else:
                    st.caption("ℹ️ Hanya PIC pemilik FPTK yang bisa request hapus")

        with col2:
            if all_requests:
                st.caption(f"📋 Total {len(all_requests)} request")
            else:
                st.caption("Belum ada request")

        with col3:
            if all_requests:
                with st.expander("📋 Lihat History Request"):
                    for req in all_requests:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.status}** — {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")
                        st.caption(f"Alasan: {req.reason}")
                        if req.status == "REJECTED" and req.admin_notes:
                            st.caption(f"Admin Notes: {req.admin_notes}")
                        st.markdown("---")

    # ============================================================
    # DETAIL VIEW
    # ============================================================
    st.markdown("---")
    st.markdown("### 📋 Detail FPTK")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        st.markdown(f"**Posisi:** {detail.posisi}")
        st.markdown(f"**PIC Recruiter:** {detail.pic_recruiter}")
        st.markdown(f"**Kode PIC:** {detail.kode_pic or '-'}")
        st.markdown(f"**Business Unit:** {detail.business_unit}")
        st.markdown(f"**Direktorat:** {detail.direktorat}")
        st.markdown(f"**Divisi:** {detail.divisi or '-'}")
        st.markdown(f"**Department:** {detail.department or '-'}")
        st.markdown(f"**Level FPTK:** {detail.level_fptk} (Level {detail.level_number})")
        st.markdown(f"**Alasan:** {detail.alasan_permintaan_fptk or '-'}")
        st.markdown(f"**Category:** {detail.category_fptk or '-'}")

    with col2:
        st.markdown(f"**Status:** {detail.status}")
        st.markdown(f"**Filter Kategorisasi:** {detail.filter_kategorisasi_fptk}")
        st.markdown(f"**Tanggal FPTK (Real):** {detail.fptk_date_real.strftime('%d/%m/%Y') if detail.fptk_date_real else '-'}")
        st.markdown(f"**Vacancy:** {detail.vacancy}")
        st.markdown(f"**Jumlah SLA:** {detail.jumlah_sla} hari")
        st.markdown(f"**Deadline SLA:** {detail.deadline_sla.strftime('%d/%m/%Y') if detail.deadline_sla else '-'}")
        st.markdown(f"**Detail SLA:** {detail.detail_sla or '-'}")
        st.markdown(f"**Offering Date:** {detail.offering_date.strftime('%d/%m/%Y') if detail.offering_date else '-'}")

    # ============================================================
    # EDIT FORM
    # ============================================================
    if not can_edit:
        st.warning("⚠️ Anda hanya bisa mengedit data FPTK milik PIC Anda sendiri.")
    else:
        st.markdown("---")
        st.markdown("### ✏️ Edit Data FPTK")

        with st.form("edit_fptk_form"):
            st.markdown("#### Data Utama")
            col1, col2, col3 = st.columns(3)

            with col1:
                if admin:
                    new_kode_unik = st.text_input("Kode Unik", value=detail.kode_unik or "")
                else:
                    new_kode_unik = st.text_input("Kode Unik", value=detail.kode_unik or "", disabled=True)

                new_posisi = st.text_input("Posisi", value=detail.posisi or "")
                new_pic_recruiter = st.selectbox("PIC Recruiter", pic_options_all,
                                                 index=pic_options_all.index(detail.pic_recruiter) if detail.pic_recruiter in pic_options_all else 0)
                new_kode_pic = st.text_input("Kode PIC", value=detail.kode_pic or "")

            with col2:
                new_business_unit = st.selectbox("Business Unit", [""] + bu_options,
                                                 index=(bu_options.index(detail.business_unit) + 1) if detail.business_unit in bu_options else 0)
                new_direktorat = st.selectbox("Direktorat", [""] + direktorat_options,
                                              index=(direktorat_options.index(detail.direktorat) + 1) if detail.direktorat in direktorat_options else 0)
                new_divisi = st.text_input("Divisi", value=detail.divisi or "")
                new_department = st.text_input("Department", value=detail.department or "")

            with col3:
                new_status = st.selectbox("Status", status_options,
                                          index=status_options.index(detail.status) if detail.status in status_options else 0)

                default_level = detail.level_fptk or "1A"
                new_level_fptk = st.selectbox("Level FPTK", LEVEL_OPTIONS,
                                              index=LEVEL_OPTIONS.index(default_level) if default_level in LEVEL_OPTIONS else 0)

                if new_level_fptk:
                    match = re.search(r'(\d+)', new_level_fptk)
                    new_level_number = int(match.group(1)) if match else 1
                else:
                    new_level_number = detail.level_number or 1

                st.text_input("Level Number (auto)", value=str(new_level_number), disabled=True)
                new_vacancy = st.number_input("Vacancy", min_value=1, value=detail.vacancy or 1)

            st.markdown("---")
            st.markdown("#### Tanggal")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_fptk_date_real = st.date_input("FPTK Date Real",
                                                   value=detail.fptk_date_real if detail.fptk_date_real else datetime.now().date())
            with col2:
                new_offering_date = st.date_input("Offering Date",
                                                  value=detail.offering_date if detail.offering_date else None)
            with col3:
                new_fptk_cancel_date = st.date_input("FPTK Cancel Date",
                                                     value=detail.fptk_cancel_date if detail.fptk_cancel_date else None)

            st.markdown("---")
            st.markdown("#### Data Tambahan")
            col1, col2 = st.columns(2)
            with col1:
                new_nama_kandidat = st.text_input("Nama Kandidat", value=detail.nama_kandidat or "")
                new_user_manager = st.text_input("User (Manager)", value=detail.user_manager or "")
            with col2:
                new_remark = st.text_area("Remark", value=detail.remark or "")

            submitted = st.form_submit_button("💾 Update FPTK", type="primary")

        if submitted:
            try:
                if new_level_number <= 3:
                    sla_days = 30
                elif new_level_number == 4:
                    sla_days = 45
                else:
                    sla_days = 60

                if new_fptk_date_real and sla_days:
                    new_deadline_sla_calc = new_fptk_date_real + timedelta(days=sla_days)
                else:
                    new_deadline_sla_calc = detail.deadline_sla

                new_detail_sla_auto = calculate_detail_sla_auto(
                    status=new_status,
                    fptk_date_real=new_fptk_date_real,
                    deadline_sla=new_deadline_sla_calc,
                    offering_date=new_offering_date,
                    fptk_cancel_date=new_fptk_cancel_date
                )

                if admin and new_kode_unik:
                    detail.kode_unik = new_kode_unik

                detail.posisi = new_posisi
                detail.pic_recruiter = new_pic_recruiter
                detail.kode_pic = new_kode_pic
                detail.business_unit = new_business_unit
                detail.direktorat = new_direktorat
                detail.divisi = new_divisi
                detail.department = new_department
                detail.status = new_status
                detail.level_fptk = new_level_fptk
                detail.level_number = new_level_number
                detail.vacancy = new_vacancy
                detail.fptk_date_real = new_fptk_date_real
                detail.offering_date = new_offering_date
                detail.fptk_cancel_date = new_fptk_cancel_date
                detail.nama_kandidat = new_nama_kandidat
                detail.user_manager = new_user_manager
                detail.remark = new_remark

                detail.jumlah_sla = sla_days
                detail.deadline_sla = new_deadline_sla_calc
                detail.detail_sla = new_detail_sla_auto

                detail.last_updated_at = datetime.now()
                detail.last_compile_action = "MANUAL_EDIT"

                db.commit()
                st.cache_data.clear()

                st.success(f"✅ FPTK berhasil diupdate!")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
