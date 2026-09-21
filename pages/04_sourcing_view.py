# pages/04_sourcing_view.py
import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import (
    DBSourcing, User, FPTK, MasterDropdown,
    CVAttachment, SourcingDeleteRequest, BlacklistRequest,
    CandidateTransfer
)
from core.auth import get_current_user, is_admin, is_it
from core.utils import (
    get_filter_options_from_db, request_blacklist, request_unblacklist,
    get_last_pipeline_stage, transfer_candidate, transfer_candidates_bulk
)
from datetime import datetime
import base64 as b64
import time


@st.cache_data(ttl=3600)
def get_sourcing_options_view():
    return {
        'sumber_options': ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance", "Lainnya"],
        'model_options': ["Model 1", "Model 2", "Model 3", "Model 4"],
        'pipeline_status_options': ["V", "X"],
        'fmcg_options': ["Ya", "Tidak"],
        'jenjang_options': ["SMA/SMK", "D3", "D4", "S1", "S2"],
        'univ_tier_options': ["Tier 1", "Tier 2", "Tier 3", "Lainnya"],
        'ipk_tier_options': ["> 3.5", "3.0 - 3.5", "2.5 - 3.0", "< 2.5"]
    }


@st.cache_data(ttl=3600)
def get_pipeline_stages_view():
    return [
        {"field": "sourcing_freelance", "label": "Sourcing Freelance", "has_detail": False},
        {"field": "sourcing_hr", "label": "Sourcing HR", "has_detail": True},
        {"field": "shortlist_cv", "label": "Shortlist CV", "has_detail": True},
        {"field": "psikotes", "label": "Psikotes", "has_detail": True},
        {"field": "hr_interview", "label": "HR Interview", "has_detail": True},
        {"field": "technical_test_case_study", "label": "Technical Test", "has_detail": True},
        {"field": "market_visit", "label": "Market Visit", "has_detail": True},
        {"field": "user_interview", "label": "User Interview", "has_detail": True},
        {"field": "panel_interview", "label": "Panel Interview", "has_detail": True},
        {"field": "reference_check", "label": "Reference Check", "has_detail": True},
        {"field": "mcu", "label": "MCU", "has_detail": True},
        {"field": "offering", "label": "Offering", "has_detail": True},
        {"field": "day1", "label": "Day 1", "has_detail": True}
    ]


@st.dialog("🚫 Request Blacklist ke Admin")
def dialog_request_blacklist(db, sourcing_id, kode_unik, nama, posisi, pic_name):
    st.info(f"**Kandidat:** {nama}")
    st.caption(f"Kode Unik: {kode_unik} | Posisi: {posisi}")
    st.caption("Request Anda akan dikirim ke Admin untuk di-approve.")

    reason = st.text_area("Alasan Blacklist *",
        placeholder="Contoh: Kandidat no-show, kandidat melanggar aturan, dll.",
        height=150, key="reason_blacklist")
    st.caption("Alasan wajib diisi minimal 10 karakter.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Kirim Request", type="primary", use_container_width=True, key="btn_submit_blacklist"):
            if not reason or len(reason.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                user = get_current_user(db)
                result = request_blacklist(db, sourcing_id, kode_unik, nama, posisi,
                    pic_name, reason.strip(), user.id, user.display_name)
                if result["success"]:
                    st.success("✅ Request blacklist berhasil dikirim!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('error', 'Unknown error')}")

    with col2:
        if st.button("❌ Batal", use_container_width=True, key="btn_cancel_blacklist"):
            st.rerun()


@st.dialog("✅ Request Un-Blacklist ke Admin")
def dialog_request_unblacklist(db, sourcing_id, kode_unik, nama, posisi, pic_name):
    st.info(f"**Kandidat:** {nama}")
    st.caption(f"Kode Unik: {kode_unik} | Posisi: {posisi}")
    st.caption("Request Anda akan dikirim ke Admin untuk di-approve.")

    reason = st.text_area("Alasan Un-Blacklist *",
        placeholder="Contoh: Kandidat sudah diperbaiki, kesalahan input, dll.",
        height=150, key="reason_unblacklist")
    st.caption("Alasan wajib diisi minimal 10 karakter.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Kirim Request", type="primary", use_container_width=True, key="btn_submit_unblacklist"):
            if not reason or len(reason.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                user = get_current_user(db)
                result = request_unblacklist(db, sourcing_id, kode_unik, nama, posisi,
                    pic_name, reason.strip(), user.id, user.display_name)
                if result["success"]:
                    st.success("✅ Request un-blacklist berhasil dikirim!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('error', 'Unknown error')}")

    with col2:
        if st.button("❌ Batal", use_container_width=True, key="btn_cancel_unblacklist"):
            st.rerun()


@st.dialog("📩 Request Hapus Kandidat ke Admin")
def dialog_request_delete(db, sourcing_id, kode_unik, nama, posisi, pic_name):
    st.info(f"**Kandidat:** {nama}")
    st.caption(f"Kode Unik: {kode_unik} | Posisi: {posisi}")
    st.caption("Request Anda akan dikirim ke Admin untuk di-approve.")

    reason = st.text_area("Alasan Request Hapus *",
        placeholder="Contoh: Kandidat duplikat, salah input, dibatalkan kandidat, dll.",
        height=150, key="reason_delete_sourcing")
    st.caption("Alasan wajib diisi minimal 10 karakter.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Kirim Request", type="primary", use_container_width=True, key="btn_submit_del_req"):
            if not reason or len(reason.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                try:
                    existing = db.query(SourcingDeleteRequest).filter(
                        SourcingDeleteRequest.sourcing_id == sourcing_id,
                        SourcingDeleteRequest.status == "PENDING"
                    ).first()
                    if existing:
                        st.warning("⚠️ Request hapus untuk kandidat ini sudah ada dan masih PENDING.")
                    else:
                        user = get_current_user(db)
                        new_request = SourcingDeleteRequest(
                            sourcing_id=sourcing_id, kode_unik=kode_unik, nama=nama,
                            posisi=posisi, pic_recruiter=pic_name, reason=reason.strip(),
                            status="PENDING", requested_by=user.id if user else None,
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

    with col2:
        if st.button("❌ Batal", use_container_width=True, key="btn_cancel_del_req"):
            st.rerun()


@st.dialog("⚠️ HAPUS KANDIDAT PERMANEN")
def dialog_confirm_delete(db, sourcing_id, kode_unik, nama):
    st.error(f"⚠️ Anda akan menghapus kandidat **{nama}** (Kode Unik: {kode_unik}) secara PERMANEN!")
    st.warning("⚠️ TINDAKAN INI TIDAK DAPAT DIBATALKAN!")
    st.caption("Data terkait (CV attachments, transfer history, request un-blacklist) juga akan terhapus otomatis.")

    confirm_kode = st.text_input(f"Ketik kode unik **{kode_unik}** untuk konfirmasi:",
        placeholder=f"Ketik {kode_unik} di sini", key="confirm_del_src_input")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Ya, Hapus Permanen", type="primary", use_container_width=True, key="btn_confirm_del_src"):
            if confirm_kode.strip() == kode_unik:
                try:
                    src = db.query(DBSourcing).filter(DBSourcing.id == sourcing_id).first()
                    if src:
                        db.query(SourcingDeleteRequest).filter(
                            SourcingDeleteRequest.sourcing_id == sourcing_id
                        ).delete(synchronize_session=False)
                        db.delete(src)
                        db.commit()
                        st.cache_data.clear()
                        st.success(f"✅ Kandidat **{nama}** berhasil dihapus!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Kandidat tidak ditemukan!")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
            else:
                st.error(f"❌ Kode unik tidak cocok!")

    with col2:
        if st.button("❌ Batal", use_container_width=True, key="btn_cancel_del_src"):
            st.rerun()


def show_sourcing_view():
    st.title("👤 Sourcing Database")
    st.markdown("Lihat, filter, dan kelola data kandidat sourcing & blacklist.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)

    with st.spinner("📋 Memuat data..."):
        filter_opts = get_filter_options_from_db()
        sourcing_options = get_sourcing_options_view()
        pipeline_stages = get_pipeline_stages_view()

    tab1, tab2, tab3 = st.tabs(["📊 Database Sourcing", "🚫 Blacklist Kandidat", "🔄 Transfer Kandidat"])

    with tab1:
        render_database_sourcing(db, user, admin, filter_opts, sourcing_options, pipeline_stages)

    with tab2:
        render_blacklist_tab(db, user, admin)

    with tab3:
        render_transfer_tab(db, user, admin)


def render_database_sourcing(db, user, admin, filter_opts, sourcing_options, pipeline_stages):
    pic_from_users = filter_opts.get("pic_options", [])

    if not pic_from_users:
        try:
            master_pics = db.query(MasterDropdown.pic_recruiter).filter(
                MasterDropdown.pic_recruiter.isnot(None),
                MasterDropdown.pic_recruiter != "",
                MasterDropdown.is_active == True
            ).distinct().all()
            pic_from_users = sorted(set([r[0] for r in master_pics if r[0]]))
        except Exception:
            pic_from_users = []

    if not pic_from_users:
        try:
            rekruter_from_db = db.query(DBSourcing.rekruter).filter(
                DBSourcing.rekruter.isnot(None), DBSourcing.rekruter != ""
            ).distinct().all()
            pic_from_users = sorted(set([r[0] for r in rekruter_from_db if r[0]]))
        except Exception:
            pic_from_users = []

    with st.sidebar:
        st.markdown("### 🔍 Filter Sourcing")
        search = st.text_input("🔎 Cari (Nama / Posisi / Kode Unik)", placeholder="Ketik keyword...", key="src_search")
        pic_options = ["Semua"] + pic_from_users
        pic_filter = st.selectbox("PIC Recruiter / Rekruter", pic_options, key="src_pic")

        sumber_options = ["Semua"] + filter_opts.get("sumber_options", [])
        if len(sumber_options) == 1:
            sumber_options = ["Semua"] + sourcing_options['sumber_options']
        sumber_filter = st.selectbox("Sumber Sourcing", sumber_options, key="src_sumber")

        model_options = ["Semua"] + sourcing_options['model_options']
        model_filter = st.selectbox("Model Rekrutmen", model_options, key="src_model")

        stage_labels = ["Semua"] + [s["label"] for s in pipeline_stages]
        stage_filter = st.selectbox("Tahap Pipeline", stage_labels, key="src_stage")

        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari Sourcing", datetime.now().replace(year=2020), key="src_from")
        with col2:
            date_to = st.date_input("Sampai Sourcing", datetime.now(), key="src_to")

        show_mine = st.checkbox("Hanya data saya", value=False, key="src_mine")

        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True, key="src_reset"):
            st.rerun()
        if st.button("🔄 Refresh Filter Options", use_container_width=True, key="src_refresh"):
            get_filter_options_from_db.clear()
            st.success("✅ Filter refreshed!")
            time.sleep(0.3)
            st.rerun()

    query = db.query(DBSourcing).filter(DBSourcing.is_blacklisted != True)

    if search:
        search_term = search.strip()
        query = query.filter(
            (DBSourcing.nama.ilike(f"%{search_term}%")) |
            (DBSourcing.posisi.ilike(f"%{search_term}%")) |
            (DBSourcing.kode_unik.ilike(f"%{search_term}%"))
        )

    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)
    if sumber_filter != "Semua":
        query = query.filter(DBSourcing.sumber_sourcing == sumber_filter)
    if model_filter != "Semua":
        query = query.filter(DBSourcing.model_rekrutmen == model_filter)
    if show_mine and not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)
    if date_from:
        query = query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        query = query.filter(DBSourcing.sourcing_date <= date_to)

    if stage_filter != "Semua":
        for stage in pipeline_stages:
            if stage["label"] == stage_filter:
                field = getattr(DBSourcing, stage["field"])
                query = query.filter(field.isnot(None))
                break

    total = query.count()
    st.markdown(f"**Total Kandidat (non-blacklist): {total}**")

    if total == 0:
        st.info("Tidak ada data sourcing dengan filter yang dipilih.")
        return

    col_export1, col_export2 = st.columns(2)
    with col_export1:
        if st.button("📥 Export CSV (Filtered)", use_container_width=True, key="src_exp_csv"):
            df_export = pd.read_sql(query.statement, db.bind)
            csv = df_export.to_csv(index=False)
            st.download_button("⬇️ Download CSV", csv,
                f"sourcing_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv", key="dl_src_csv")
    with col_export2:
        if st.button("📊 Export Excel (Filtered)", use_container_width=True, key="src_exp_xlsx"):
            from io import BytesIO
            df_export = pd.read_sql(query.statement, db.bind)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='Sourcing', index=False)
            output.seek(0)
            st.download_button("⬇️ Download Excel", output.getvalue(),
                f"sourcing_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_src_xlsx")

    st.markdown("---")

    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50, key="src_page_size")
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1, key="src_page")
    offset = (page - 1) * page_size

    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)

    exclude_cols = ['created_at', 'last_updated_at', 'last_compile_action',
                   'source_file', 'source_file_hash', 'source_user_id', 'source_cycle_id',
                   'blacklisted_by']
    display_cols = [c for c in df.columns if c not in exclude_cols]

    column_config = {
        "id": "ID", "no": "No", "sourcing_date": "Tgl Sourcing",
        "kode_unik": "Kode Unik", "posisi": "Posisi",
        "model_rekrutmen": "Model Rekrutmen", "rekruter": "PIC Recruiter",
        "sumber_sourcing": "Sumber Sourcing", "nama": "Nama Kandidat",
        "nama_universitas_top10": "Universitas Top 10",
        "nama_universitas_lainnya": "Universitas Lainnya",
        "jenjang_pendidikan": "Jenjang Pendidikan", "jurusan": "Jurusan",
        "jurusan_lainnya": "Jurusan Lainnya", "tahun_lulus": "Tahun Lulus",
        "ipk": "IPK", "skor_bahasa_inggris": "Skor Bahasa Inggris",
        "university_tier": "University Tier", "ipk_tier": "IPK Tier",
        "nomor_hp": "No HP", "email": "Email", "domisili": "Domisili",
        "last_position": "Posisi Terakhir", "last_tenure": "Masa Kerja Terakhir",
        "last_company": "Perusahaan Terakhir", "total_tenure": "Total Masa Kerja",
        "pernah_di_fmcg": "Pernah di FMCG",
        "sourcing_freelance": "Sourcing Freelance",
        "tanggal_sourcing_freelance": "Tgl Sourcing Freelance",
        "sourcing_hr": "Sourcing HR",
        "detail_keterangan_sourcing_hr": "Keterangan Sourcing HR",
        "tanggal_sourcing": "Tgl Sourcing", "shortlist_cv": "Shortlist CV",
        "detail_keterangan_shortlist_cv": "Keterangan Shortlist",
        "tanggal_shortlist_cv": "Tgl Shortlist", "psikotes": "Psikotes",
        "kode_psikotes": "Kode Psikotes",
        "detail_keterangan_psikotes": "Keterangan Psikotes",
        "tanggal_psikotes": "Tgl Psikotes", "nilai_logika": "Nilai Logika",
        "nilai_iq": "Nilai IQ", "nilai_daya_tangkap": "Nilai Daya Tangkap",
        "nilai_ra": "Nilai RA", "disc": "DISC", "hr_interview": "HR Interview",
        "detail_keterangan_hr_interview": "Keterangan HR Interview",
        "tanggal_hr_interview": "Tgl HR Interview",
        "technical_test_case_study": "Technical Test",
        "detail_keterangan_technical_test": "Keterangan Technical Test",
        "tanggal_technical_test": "Tgl Technical Test",
        "market_visit": "Market Visit",
        "detail_market_visit": "Keterangan Market Visit",
        "tanggal_market_visit": "Tgl Market Visit",
        "user_interview": "User Interview",
        "detail_keterangan_user_interview": "Keterangan User Interview",
        "tanggal_user_interview": "Tgl User Interview",
        "panel_interview": "Panel Interview",
        "detail_keterangan_panel_interview": "Keterangan Panel Interview",
        "tanggal_panel_interview": "Tgl Panel Interview",
        "reference_check": "Reference Check",
        "detail_keterangan_reference_check": "Keterangan Reference Check",
        "tanggal_reference_check": "Tgl Reference Check",
        "mcu": "MCU", "detail_keterangan_mcu": "Keterangan MCU",
        "tanggal_mcu": "Tgl MCU", "offering": "Offering",
        "detail_keterangan_offering": "Keterangan Offering",
        "tanggal_offering": "Tgl Offering", "notes": "Catatan",
        "day1": "Day 1", "detail_keterangan_day1": "Keterangan Day 1",
        "tanggal_day1": "Tgl Day 1"
    }

    display_df = df[display_cols].copy()
    new_columns = []
    used_names = set()
    for col in display_df.columns:
        new_name = column_config.get(col, col)
        if new_name in used_names:
            new_columns.append(col)
        else:
            new_columns.append(new_name)
            used_names.add(new_name)
    display_df.columns = new_columns

    st.dataframe(display_df, use_container_width=True, height=500)

    # ============================================================
    # BULK EDIT SOURCING
    # ============================================================
    st.markdown("---")
    st.markdown("### ✏️ Bulk Edit Sourcing")
    st.caption("Pilih banyak kandidat sekaligus, lalu update field yang sama untuk semuanya.")

    bulk_query = db.query(DBSourcing).filter(DBSourcing.is_blacklisted != True)
    if search:
        search_term = search.strip()
        bulk_query = bulk_query.filter(
            (DBSourcing.nama.ilike(f"%{search_term}%")) |
            (DBSourcing.posisi.ilike(f"%{search_term}%")) |
            (DBSourcing.kode_unik.ilike(f"%{search_term}%"))
        )
    if pic_filter != "Semua":
        bulk_query = bulk_query.filter(DBSourcing.rekruter == pic_filter)
    if sumber_filter != "Semua":
        bulk_query = bulk_query.filter(DBSourcing.sumber_sourcing == sumber_filter)
    if model_filter != "Semua":
        bulk_query = bulk_query.filter(DBSourcing.model_rekrutmen == model_filter)
    if date_from:
        bulk_query = bulk_query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        bulk_query = bulk_query.filter(DBSourcing.sourcing_date <= date_to)
    if not admin:
        bulk_query = bulk_query.filter(DBSourcing.rekruter == user.pic_recruiter)

    bulk_sourcing = bulk_query.limit(500).all()

    if not bulk_sourcing:
        st.info("Tidak ada kandidat yang bisa di-bulk edit dengan filter ini.")
    else:
        if "bulk_src_select_all" not in st.session_state:
            st.session_state.bulk_src_select_all = False

        col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 3])
        with col_sel1:
            if st.button("✅ Pilih Semua", use_container_width=True, key="bulk_src_select_all_btn"):
                st.session_state.bulk_src_select_all = True
                st.rerun()
        with col_sel2:
            if st.button("❌ Batal Pilih", use_container_width=True, key="bulk_src_deselect_all_btn"):
                st.session_state.bulk_src_select_all = False
                st.rerun()
        with col_sel3:
            st.caption(f"💡 Pilih **{len(bulk_sourcing)}** kandidat sekaligus atau klik manual per row")

        default_pilih = st.session_state.bulk_src_select_all

        bulk_src_df = pd.DataFrame([{
            "pilih": default_pilih, "id": s.id, "kode_unik": s.kode_unik,
            "nama": s.nama, "posisi": s.posisi, "rekruter": s.rekruter,
            "sumber_sourcing": s.sumber_sourcing, "model_rekrutmen": s.model_rekrutmen,
        } for s in bulk_sourcing])

        edited_src_df = st.data_editor(
            bulk_src_df, use_container_width=True, hide_index=True,
            column_config={
                "pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "kode_unik": st.column_config.TextColumn("Kode Unik", disabled=True, width="medium"),
                "nama": st.column_config.TextColumn("Nama", disabled=True, width="medium"),
                "posisi": st.column_config.TextColumn("Posisi", disabled=True, width="medium"),
                "rekruter": st.column_config.TextColumn("PIC", disabled=True, width="small"),
                "sumber_sourcing": st.column_config.TextColumn("Sumber", disabled=True, width="small"),
                "model_rekrutmen": st.column_config.TextColumn("Model", disabled=True, width="small"),
            }, key="bulk_sourcing_table"
        )

        selected_src_ids = edited_src_df[edited_src_df["pilih"] == True]["id"].tolist()
        st.markdown(f"**{len(selected_src_ids)} kandidat dipilih**")

        if selected_src_ids:
            st.markdown("#### Field yang Mau Diubah")

            pipeline_fields = [
                "sourcing_freelance", "sourcing_hr", "shortlist_cv", "psikotes",
                "hr_interview", "technical_test_case_study", "market_visit",
                "user_interview", "panel_interview", "reference_check",
                "mcu", "offering", "day1"
            ]

            all_src_fields = {
                "posisi": "Posisi", "model_rekrutmen": "Model Rekrutmen",
                "rekruter": "Rekruter", "sumber_sourcing": "Sumber Sourcing",
                "jenjang_pendidikan": "Jenjang Pendidikan", "jurusan": "Jurusan",
                "tahun_lulus": "Tahun Lulus", "ipk": "IPK",
                "nama_universitas_top10": "Universitas Top 10",
                "university_tier": "University Tier", "ipk_tier": "IPK Tier",
                "domisili": "Domisili", "last_position": "Last Position",
                "last_company": "Last Company", "last_tenure": "Last Tenure",
                "total_tenure": "Total Tenure", "pernah_di_fmcg": "Pernah di FMCG",
                "notes": "Notes",
            }
            for pf in pipeline_fields:
                all_src_fields[pf] = f"Pipeline: {pf.replace('_', ' ').title()}"

            field_src = st.selectbox("Pilih Field", list(all_src_fields.keys()),
                format_func=lambda x: all_src_fields[x], key="bulk_src_field")

            new_src_value = None
            custom_date = None

            if field_src in pipeline_fields:
                new_src_value = st.selectbox("Status Pipeline", ["", "V", "X"], key=f"bulk_src_v_{field_src}")
                auto_date = st.checkbox("Auto-isi tanggal hari ini", value=True, key=f"bulk_src_autodate_{field_src}")
                if not auto_date:
                    custom_date = st.date_input("Tanggal", datetime.now().date(), key=f"bulk_src_date_{field_src}")
                else:
                    custom_date = datetime.now().date()
            elif field_src == "model_rekrutmen":
                new_src_value = st.selectbox("Model Rekrutmen", ["Model 1", "Model 2", "Model 3", "Model 4"], key="bulk_src_model")
            elif field_src == "pernah_di_fmcg":
                new_src_value = st.selectbox("Pernah di FMCG", ["Ya", "Tidak"], key="bulk_src_fmcg")
            elif field_src == "jenjang_pendidikan":
                new_src_value = st.selectbox("Jenjang", ["SMA/SMK", "D3", "D4", "S1", "S2"], key="bulk_src_jenjang")
            elif field_src == "university_tier":
                new_src_value = st.selectbox("University Tier", ["Top 3 PTN", "Top 10 PTN", "Top 20 PTN", "Top 10 PTS", "Lainnya"], key="bulk_src_unitier")
            elif field_src == "ipk_tier":
                new_src_value = st.selectbox("IPK Tier", ["> 3.5", "3.0 - 3.5", "2.5 - 3.0", "< 2.5"], key="bulk_src_ipktier")
            elif field_src == "tahun_lulus":
                new_src_value = st.number_input("Tahun Lulus", min_value=1900, max_value=2100, value=2020, key="bulk_src_tahun")
            elif field_src == "ipk":
                new_src_value = st.number_input("IPK", min_value=0.0, max_value=4.0, value=3.0, step=0.01, key="bulk_src_ipk")
            else:
                new_src_value = st.text_input("Nilai Baru", key="bulk_src_text")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Terapkan ke Kandidat", type="primary", use_container_width=True, key="bulk_src_apply"):
                    try:
                        updated_count = 0
                        for sid in selected_src_ids:
                            src_obj = db.query(DBSourcing).filter(DBSourcing.id == sid).first()
                            if not src_obj:
                                continue
                            setattr(src_obj, field_src, new_src_value)
                            if field_src in pipeline_fields and new_src_value and custom_date:
                                date_field = f"tanggal_{field_src}"
                                if hasattr(src_obj, date_field):
                                    setattr(src_obj, date_field, custom_date)
                            src_obj.last_updated_at = datetime.now()
                            src_obj.last_compile_action = "BULK_EDIT"
                            updated_count += 1
                        db.commit()
                        st.session_state.bulk_src_select_all = False
                        st.cache_data.clear()
                        st.success(f"✅ Berhasil update {updated_count} kandidat!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        db.rollback()

            with col_b:
                if st.button("❌ Batal", use_container_width=True, key="bulk_src_cancel"):
                    st.session_state.bulk_src_select_all = False
                    st.rerun()

    # ============================================================
    # DETAIL & EDIT
    # ============================================================
    st.markdown("---")
    st.subheader("✏️ Detail & Edit Kandidat")
    st.caption("🔍 Cari berdasarkan Kode Unik, Nama, atau Posisi")

    df_all = pd.read_sql(query.statement, db.bind)

    if not df_all.empty:
        search_options = {}
        for _, row in df_all.iterrows():
            kode = row.get('kode_unik', '')
            nama = row.get('nama', '')
            posisi = row.get('posisi', '')
            display = f"{kode} | {nama[:30]}..." if len(str(nama)) > 30 else f"{kode} | {nama}"
            if posisi:
                display += f" | {posisi[:20]}..." if len(str(posisi)) > 20 else f" | {posisi}"
            search_options[display] = row.get('id')

        selected_display = st.selectbox("Pilih Kandidat (Kode Unik | Nama | Posisi)",
            list(search_options.keys()), key="src_detail_select")
        selected_id = search_options[selected_display] if selected_display else None
    else:
        selected_id = None
        st.info("Tidak ada data untuk diedit.")
        return

    if not selected_id:
        st.info("Pilih data dari daftar di atas untuk diedit.")
        return

    detail = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
    if not detail:
        st.error("Data tidak ditemukan")
        return

    with st.expander("📋 Data Pribadi & Pendidikan", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**ID:** {detail.id}")
            st.markdown(f"**No:** {detail.no or '-'}")
            st.markdown(f"**Nama:** {detail.nama}")
            st.markdown(f"**Posisi:** {detail.posisi or '-'}")
            st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        with col2:
            st.markdown(f"**Email:** {detail.email or '-'}")
            st.markdown(f"**No HP:** {detail.nomor_hp or '-'}")
            st.markdown(f"**Domisili:** {detail.domisili or '-'}")
            st.markdown(f"**Sumber Sourcing:** {detail.sumber_sourcing or '-'}")
        with col3:
            st.markdown(f"**Universitas Top 10:** {detail.nama_universitas_top10 or '-'}")
            st.markdown(f"**Universitas Lainnya:** {detail.nama_universitas_lainnya or '-'}")
            st.markdown(f"**Jurusan:** {detail.jurusan or '-'}")
            st.markdown(f"**Jurusan Lainnya:** {getattr(detail, 'jurusan_lainnya', None) or '-'}")
            st.markdown(f"**IPK:** {detail.ipk or '-'}")

    with st.expander("💼 Pengalaman Kerja"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Posisi Terakhir:** {detail.last_position or '-'}")
            st.markdown(f"**Perusahaan Terakhir:** {detail.last_company or '-'}")
        with col2:
            st.markdown(f"**Masa Kerja Terakhir:** {detail.last_tenure or '-'}")
            st.markdown(f"**Total Masa Kerja:** {detail.total_tenure or '-'}")
            st.markdown(f"**Pernah di FMCG:** {detail.pernah_di_fmcg or '-'}")

    with st.expander("📊 Pipeline Status"):
        pipeline_data = []
        for stage in pipeline_stages:
            field = getattr(detail, stage["field"])
            date_field_name = f"tanggal_{stage['field']}"
            detail_field_name = f"detail_keterangan_{stage['field']}"
            date_value = getattr(detail, date_field_name) if hasattr(detail, date_field_name) else None
            detail_value = getattr(detail, detail_field_name) if hasattr(detail, detail_field_name) else None
            pipeline_data.append({
                "Tahap": stage["label"], "Status": field or "-",
                "Tanggal": date_value.strftime('%d/%m/%Y') if date_value else "-",
                "Keterangan": detail_value or "-"
            })
        st.dataframe(pd.DataFrame(pipeline_data), use_container_width=True)

    with st.expander("📎 Lampiran CV"):
        cv_list = db.query(CVAttachment).filter(
            CVAttachment.sourcing_id == detail.id
        ).order_by(CVAttachment.created_at.desc()).all()

        if not cv_list:
            st.info("Belum ada CV terlampir.")
            st.caption("Upload CV di halaman **Sourcing Input** → tab **Manage CV**.")
        else:
            st.markdown(f"**{len(cv_list)} CV terlampir:**")
            for cv in cv_list:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    size_kb = (cv.file_size or 0) / 1024
                    st.markdown(f"📄 **{cv.file_name}** ({size_kb:.1f} KB)")
                    st.caption(f"Upload: {cv.created_at.strftime('%d/%m/%Y %H:%M')} oleh {cv.uploaded_by_name or '-'}")
                with col2:
                    try:
                        file_bytes = b64.b64decode(cv.file_data)
                        st.download_button("⬇️ Download", file_bytes, cv.file_name,
                            mime=cv.file_type or "application/octet-stream",
                            key=f"dl_cv_src_{cv.id}", use_container_width=True)
                    except Exception:
                        st.caption("Error")
                with col3:
                    file_lower = cv.file_name.lower()
                    if file_lower.endswith(('.jpg', '.jpeg', '.png')):
                        if st.button("👁️ Lihat", key=f"view_cv_src_{cv.id}", use_container_width=True):
                            st.session_state[f"show_cv_{cv.id}"] = not st.session_state.get(f"show_cv_{cv.id}", False)
                            st.rerun()

                if st.session_state.get(f"show_cv_{cv.id}", False):
                    try:
                        file_bytes = b64.b64decode(cv.file_data)
                        st.image(file_bytes, caption=cv.file_name, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    with st.expander("📝 Catatan"):
        st.markdown(f"**Catatan:** {detail.notes or '-'}")

    st.markdown("---")
    st.markdown("### ⚙️ Aksi Kandidat")

    existing_del_request = db.query(SourcingDeleteRequest).filter(
        SourcingDeleteRequest.sourcing_id == detail.id,
        SourcingDeleteRequest.status == "PENDING"
    ).first()

    existing_bl_request = db.query(BlacklistRequest).filter(
        BlacklistRequest.sourcing_id == detail.id,
        BlacklistRequest.action == "BLACKLIST",
        BlacklistRequest.status == "PENDING"
    ).first()

    all_del_requests = db.query(SourcingDeleteRequest).filter(
        SourcingDeleteRequest.sourcing_id == detail.id
    ).order_by(SourcingDeleteRequest.requested_at.desc()).all()

    col1, col2, col3, col4 = st.columns(4)
    is_owner = detail.rekruter == user.pic_recruiter

    if admin:
        with col1:
            if st.button("🗑️ Hapus Langsung (Admin)", type="secondary", use_container_width=True, key=f"del_direct_{detail.id}"):
                dialog_confirm_delete(db, detail.id, detail.kode_unik, detail.nama)
        with col2:
            if st.button("🚫 Blacklist Langsung (Admin)", type="secondary", use_container_width=True, key=f"bl_direct_{detail.id}"):
                try:
                    detail.is_blacklisted = True
                    detail.blacklisted_at = datetime.now()
                    detail.blacklisted_by = user.id
                    detail.blacklist_reason = "Blacklist langsung oleh admin"
                    detail.last_updated_at = datetime.now()
                    detail.last_compile_action = "BLACKLIST_ADMIN"
                    db.commit()
                    st.cache_data.clear()
                    st.success(f"✅ Kandidat {detail.nama} di-blacklist!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
        with col3:
            if existing_del_request:
                st.warning(f"📩 Del Pending")
            elif existing_bl_request:
                st.warning(f"🚫 Bl Pending")
            else:
                st.caption("Tidak ada request pending")
        with col4:
            if all_del_requests:
                with st.expander(f"📋 History ({len(all_del_requests)})"):
                    for req in all_del_requests:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.status}**")
                        st.caption(f"By: {req.requested_by_name}")
                        st.caption(f"Alasan: {req.reason}")
                        st.markdown("---")
    else:
        with col1:
            if existing_del_request:
                st.info(f"📩 Del PENDING")
            else:
                if is_owner:
                    if st.button("📩 Request Hapus", type="primary", use_container_width=True, key=f"req_del_{detail.id}"):
                        dialog_request_delete(db, detail.id, detail.kode_unik, detail.nama, detail.posisi, detail.rekruter)
                else:
                    st.caption("ℹ️ Request Hapus")
        with col2:
            if existing_bl_request:
                st.info(f"🚫 Bl PENDING")
            else:
                if is_owner:
                    if st.button("🚫 Request Blacklist", type="primary", use_container_width=True, key=f"req_bl_{detail.id}"):
                        dialog_request_blacklist(db, detail.id, detail.kode_unik, detail.nama, detail.posisi, detail.rekruter)
                else:
                    st.caption("ℹ️ Request Blacklist")
        with col3:
            st.caption("ℹ️ Hanya PIC pemilik")
        with col4:
            if all_del_requests:
                with st.expander("📋 History Del"):
                    for req in all_del_requests:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.status}**")
                        st.caption(f"Alasan: {req.reason}")
                        st.markdown("---")

    st.markdown("---")
    st.subheader("✏️ Edit Data Kandidat")
    can_edit = admin or is_owner

    if not can_edit:
        st.warning("⚠️ Anda hanya bisa mengedit data yang Anda input sendiri.")
        return

    with st.form("edit_sourcing_full", clear_on_submit=False):
        st.markdown("### 📋 Data Pribadi & Pendidikan")
        col1, col2, col3 = st.columns(3)

        with col1:
            nama = st.text_input("Nama Kandidat *", value=detail.nama or "")
            posisi = st.text_input("Posisi *", value=detail.posisi or "")
            kode_unik = st.text_input("Kode Unik *", value=detail.kode_unik or "")
            sourcing_date = st.date_input("Tanggal Sourcing",
                value=detail.sourcing_date if detail.sourcing_date else datetime.now().date())
        with col2:
            email = st.text_input("Email", value=detail.email or "")
            nomor_hp = st.text_input("No HP", value=detail.nomor_hp or "")
            domisili = st.text_input("Domisili", value=detail.domisili or "")
            rekruter = st.text_input("PIC Recruiter", value=detail.rekruter or "")
        with col3:
            sumber_sourcing = st.selectbox("Sumber Sourcing", [""] + sourcing_options['sumber_options'],
                index=([""] + sourcing_options['sumber_options']).index(detail.sumber_sourcing) if detail.sumber_sourcing in sourcing_options['sumber_options'] else 0)
            model_rekrutmen = st.selectbox("Model Rekrutmen", [""] + sourcing_options['model_options'],
                index=([""] + sourcing_options['model_options']).index(detail.model_rekrutmen) if detail.model_rekrutmen in sourcing_options['model_options'] else 0)
            no = st.number_input("No", value=detail.no or 0, step=1)
            pernah_di_fmcg = st.selectbox("Pernah di FMCG", [""] + sourcing_options['fmcg_options'],
                index=([""] + sourcing_options['fmcg_options']).index(detail.pernah_di_fmcg) if detail.pernah_di_fmcg in sourcing_options['fmcg_options'] else 0)

        st.markdown("---")
        st.markdown("### 🎓 Pendidikan")
        col1, col2, col3 = st.columns(3)
        with col1:
            jenjang_pendidikan = st.selectbox("Jenjang Pendidikan", [""] + sourcing_options['jenjang_options'],
                index=([""] + sourcing_options['jenjang_options']).index(detail.jenjang_pendidikan) if detail.jenjang_pendidikan in sourcing_options['jenjang_options'] else 0)
            nama_universitas_top10 = st.text_input("Nama Universitas Top 10", value=detail.nama_universitas_top10 or "")
            nama_universitas_lainnya = st.text_input("Nama Universitas Lainnya", value=detail.nama_universitas_lainnya or "")
        with col2:
            jurusan = st.text_input("Jurusan", value=detail.jurusan or "")
            jurusan_lainnya = st.text_input("Jurusan Lainnya",
                value=getattr(detail, 'jurusan_lainnya', None) or "")
            tahun_lulus = st.number_input("Tahun Lulus", value=detail.tahun_lulus or 0, step=1)
            ipk = st.text_input("IPK", value=str(detail.ipk) if detail.ipk else "")
        with col3:
            skor_bahasa_inggris = st.text_input("Skor Bahasa Inggris", value=detail.skor_bahasa_inggris or "")
            university_tier = st.selectbox("University Tier", [""] + sourcing_options['univ_tier_options'],
                index=([""] + sourcing_options['univ_tier_options']).index(detail.university_tier) if detail.university_tier in sourcing_options['univ_tier_options'] else 0)
            ipk_tier = st.selectbox("IPK Tier", [""] + sourcing_options['ipk_tier_options'],
                index=([""] + sourcing_options['ipk_tier_options']).index(detail.ipk_tier) if detail.ipk_tier in sourcing_options['ipk_tier_options'] else 0)

        st.markdown("---")
        st.markdown("### 💼 Pengalaman Kerja")
        col1, col2 = st.columns(2)
        with col1:
            last_position = st.text_input("Posisi Terakhir", value=detail.last_position or "")
            last_company = st.text_input("Perusahaan Terakhir", value=detail.last_company or "")
        with col2:
            last_tenure = st.text_input("Masa Kerja Terakhir", value=detail.last_tenure or "")
            total_tenure = st.text_input("Total Masa Kerja", value=detail.total_tenure or "")

        st.markdown("---")
        st.markdown("### 📊 Pipeline Stages (V = Lolos, X = Tidak Lolos)")

        pipeline_inputs = {}
        for i, stage in enumerate(pipeline_stages):
            if i % 3 == 0:
                cols = st.columns(3)
            status_field = stage["field"]
            label = stage["label"]
            date_field = f"tanggal_{status_field}"
            detail_field = f"detail_keterangan_{status_field}"
            status_value = getattr(detail, status_field)
            date_value = getattr(detail, date_field) if hasattr(detail, date_field) else None
            detail_value = getattr(detail, detail_field) if hasattr(detail, detail_field) else None

            with cols[i % 3]:
                st.markdown(f"**{label}**")
                new_status = st.selectbox(f"Status {label}",
                    [""] + sourcing_options['pipeline_status_options'],
                    index=([""] + sourcing_options['pipeline_status_options']).index(status_value) if status_value in sourcing_options['pipeline_status_options'] else 0,
                    key=f"status_{status_field}")
                new_date = st.date_input(f"Tgl {label}",
                    value=date_value if date_value else None, key=f"date_{date_field}")
                if hasattr(detail, detail_field):
                    new_detail = st.text_area(f"Keterangan {label}",
                        value=detail_value or "", key=f"detail_{detail_field}", height=50)
                    pipeline_inputs[detail_field] = new_detail if new_detail else None
                pipeline_inputs[status_field] = new_status if new_status else None
                pipeline_inputs[date_field] = new_date

        st.markdown("---")
        st.markdown("### 📝 Catatan")
        notes = st.text_area("Catatan", value=detail.notes or "", height=100)
        st.markdown("---")
        submitted = st.form_submit_button("💾 Simpan Perubahan")

        if submitted:
            try:
                detail.nama = nama
                detail.posisi = posisi
                detail.kode_unik = kode_unik
                detail.sourcing_date = sourcing_date
                detail.email = email if email else None
                detail.nomor_hp = nomor_hp if nomor_hp else None
                detail.domisili = domisili if domisili else None
                detail.rekruter = rekruter if rekruter else None
                detail.sumber_sourcing = sumber_sourcing if sumber_sourcing else None
                detail.model_rekrutmen = model_rekrutmen if model_rekrutmen else None
                detail.no = no if no else None
                detail.pernah_di_fmcg = pernah_di_fmcg if pernah_di_fmcg != "" else None

                detail.jenjang_pendidikan = jenjang_pendidikan if jenjang_pendidikan else None
                detail.nama_universitas_top10 = nama_universitas_top10 if nama_universitas_top10 else None
                detail.nama_universitas_lainnya = nama_universitas_lainnya if nama_universitas_lainnya else None
                detail.jurusan = jurusan if jurusan else None
                detail.jurusan_lainnya = jurusan_lainnya if jurusan_lainnya else None
                detail.tahun_lulus = tahun_lulus if tahun_lulus else None

                try:
                    if ipk:
                        detail.ipk = float(ipk)
                    else:
                        detail.ipk = None
                except ValueError:
                    st.error("IPK harus berupa angka (contoh: 3.5)")
                    return

                detail.skor_bahasa_inggris = skor_bahasa_inggris if skor_bahasa_inggris else None
                detail.university_tier = university_tier if university_tier else None
                detail.ipk_tier = ipk_tier if ipk_tier else None
                detail.last_position = last_position if last_position else None
                detail.last_company = last_company if last_company else None
                detail.last_tenure = last_tenure if last_tenure else None
                detail.total_tenure = total_tenure if total_tenure else None
                detail.notes = notes if notes else None

                for field_name, value in pipeline_inputs.items():
                    setattr(detail, field_name, value)

                detail.last_updated_at = datetime.now()
                detail.last_compile_action = "Manual Edit"

                db.commit()
                st.success("✅ Data berhasil diupdate!")
                st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"❌ Gagal mengupdate data: {str(e)}")


# ============================================================
# TAB 2: BLACKLIST
# ============================================================

def render_blacklist_tab(db, user, admin):
    st.markdown("### 🚫 Kandidat Blacklist")
    st.caption("Kandidat yang di-blacklist tidak bisa diproses di FPTK baru.")

    with st.sidebar:
        st.markdown("### 🔍 Filter Blacklist")
        bl_search = st.text_input("🔎 Cari (Nama / Kode Unik / Posisi)", placeholder="Ketik keyword...", key="bl_search")
        bl_pic_options = ["Semua"] + sorted(set([
            r[0] for r in db.query(DBSourcing.rekruter)
            .filter(DBSourcing.rekruter.isnot(None), DBSourcing.rekruter != "")
            .distinct().all() if r[0]
        ]))
        bl_pic_filter = st.selectbox("PIC Recruiter", bl_pic_options, key="bl_pic")
        bl_reason = st.text_input("Filter Alasan", placeholder="Ketik keyword alasan...", key="bl_reason")
        if st.button("🔄 Reset Filter", use_container_width=True, key="bl_reset"):
            st.rerun()

    query = db.query(DBSourcing).filter(DBSourcing.is_blacklisted == True)

    if bl_search:
        s = bl_search.strip()
        query = query.filter(
            (DBSourcing.nama.ilike(f"%{s}%")) |
            (DBSourcing.kode_unik.ilike(f"%{s}%")) |
            (DBSourcing.posisi.ilike(f"%{s}%"))
        )
    if bl_pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == bl_pic_filter)
    if bl_reason:
        query = query.filter(DBSourcing.blacklist_reason.ilike(f"%{bl_reason}%"))

    query = query.order_by(DBSourcing.blacklisted_at.desc())
    total = query.count()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Blacklist", total)
    pending_bl = db.query(BlacklistRequest).filter(
        BlacklistRequest.action == "BLACKLIST", BlacklistRequest.status == "PENDING"
    ).count()
    pending_unbl = db.query(BlacklistRequest).filter(
        BlacklistRequest.action == "UNBLACKLIST", BlacklistRequest.status == "PENDING"
    ).count()
    col2.metric("Request Blacklist Pending", pending_bl)
    col3.metric("Request Un-Blacklist Pending", pending_unbl)

    st.markdown("---")

    if total == 0:
        st.info("Tidak ada kandidat blacklist dengan filter ini.")
        return

    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50, key="bl_page_size")
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1, key="bl_page")
    offset = (page - 1) * page_size

    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)

    display_cols = ['id', 'kode_unik', 'nama', 'posisi', 'rekruter', 'email', 'nomor_hp',
                    'blacklisted_at', 'blacklist_reason']
    available_cols = [c for c in display_cols if c in df.columns]

    if 'blacklisted_at' in df.columns:
        df['blacklisted_at'] = pd.to_datetime(df['blacklisted_at'])
        df['Tgl Blacklist'] = df['blacklisted_at'].dt.strftime('%d/%m/%Y %H:%M')

    display_df = df[available_cols + (['Tgl Blacklist'] if 'Tgl Blacklist' in df.columns else [])].copy()

    rename_map = {
        'id': 'ID', 'kode_unik': 'Kode Unik', 'nama': 'Nama Kandidat',
        'posisi': 'Posisi', 'rekruter': 'PIC', 'email': 'Email',
        'nomor_hp': 'No HP', 'blacklist_reason': 'Alasan Blacklist'
    }
    display_df = display_df.rename(columns=rename_map)

    st.dataframe(display_df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📋 Detail & Aksi")

    select_options = {}
    for _, row in df.iterrows():
        kode = row.get('kode_unik', '')
        nama = row.get('nama', '')
        display = f"{kode} | {nama[:40]}" if len(str(nama)) > 40 else f"{kode} | {nama}"
        select_options[display] = row.get('id')

    selected_display = st.selectbox("Pilih Kandidat", list(select_options.keys()), key="bl_detail_select")
    selected_id = select_options.get(selected_display)

    if not selected_id:
        return

    detail = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
    if not detail:
        st.error("Data tidak ditemukan.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nama:** {detail.nama}")
        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        st.markdown(f"**Posisi:** {detail.posisi or '-'}")
        st.markdown(f"**PIC:** {detail.rekruter or '-'}")
        st.markdown(f"**Email:** {detail.email or '-'}")
        st.markdown(f"**No HP:** {detail.nomor_hp or '-'}")
    with col2:
        st.markdown(f"**Tgl Blacklist:** {detail.blacklisted_at.strftime('%d/%m/%Y %H:%M') if detail.blacklisted_at else '-'}")
        st.markdown(f"**Alasan:** {detail.blacklist_reason or '-'}")
        st.markdown(f"**Sumber Sourcing:** {detail.sumber_sourcing or '-'}")
        st.markdown(f"**Domisili:** {detail.domisili or '-'}")

    existing_unbl_request = db.query(BlacklistRequest).filter(
        BlacklistRequest.sourcing_id == selected_id,
        BlacklistRequest.action == "UNBLACKLIST",
        BlacklistRequest.status == "PENDING"
    ).first()

    st.markdown("---")
    st.markdown("### ⚙️ Aksi")
    is_owner = detail.rekruter == user.pic_recruiter
    col1, col2 = st.columns(2)

    if admin:
        with col1:
            if st.button("✅ Un-Blacklist Langsung (Admin)", type="primary", use_container_width=True, key=f"unbl_direct_{detail.id}"):
                try:
                    detail.is_blacklisted = False
                    detail.blacklisted_at = None
                    detail.blacklisted_by = None
                    detail.blacklist_reason = None
                    detail.last_updated_at = datetime.now()
                    detail.last_compile_action = "UNBLACKLIST_ADMIN"
                    db.commit()
                    st.cache_data.clear()
                    st.success(f"✅ Kandidat {detail.nama} di-un-blacklist!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
        with col2:
            if existing_unbl_request:
                st.warning(f"📩 Pending dari {existing_unbl_request.requested_by_name}")
            else:
                st.caption("Tidak ada request pending")
    else:
        with col1:
            if existing_unbl_request:
                st.info(f"📩 Request Anda PENDING")
            else:
                if is_owner:
                    if st.button("✅ Request Un-Blacklist ke Admin", type="primary", use_container_width=True, key=f"req_unbl_{detail.id}"):
                        dialog_request_unblacklist(db, detail.id, detail.kode_unik, detail.nama, detail.posisi, detail.rekruter)
                else:
                    st.caption("ℹ️ Hanya PIC pemilik yang bisa request")
        with col2:
            st.caption("Request akan dikirim ke Admin")


# ============================================================
# TAB 3: TRANSFER KANDIDAT
# ============================================================

def render_transfer_tab(db, user, admin):
    st.markdown("### 🔄 Transfer Kandidat")
    st.caption("Pindahkan kandidat dari satu FPTK ke FPTK lain (recycle).")

    if is_it(db):
        st.info("🔍 Mode View-Only (IT)")
        render_transfer_history(db, admin=False)
        return

    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["🔄 Transfer Single", "📦 Transfer Bulk", "📜 History Transfer"])

    with sub_tab1:
        render_transfer_single(db, user, admin)
    with sub_tab2:
        render_transfer_bulk(db, user, admin)
    with sub_tab3:
        render_transfer_history(db, admin)


def render_transfer_single(db, user, admin):
    fptk_list = db.query(FPTK).filter(FPTK.status == "OP").order_by(FPTK.kode_unik).all()
    fptk_options = {}
    for f in fptk_list:
        display = f"{f.kode_unik} | {f.posisi[:50]}" if len(str(f.posisi)) > 50 else f"{f.kode_unik} | {f.posisi}"
        fptk_options[display] = f.kode_unik

    if not fptk_options:
        st.warning("Tidak ada FPTK OP yang tersedia.")
        return

    filter_fptk = st.selectbox("Filter dari FPTK Asal", ["Semua"] + list(fptk_options.keys()), key="trf_single_filter")

    query = db.query(DBSourcing)
    if filter_fptk != "Semua":
        query = query.filter(DBSourcing.kode_unik == fptk_options[filter_fptk])
    if not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)

    candidates = query.limit(500).all()
    if not candidates:
        st.info("Tidak ada kandidat yang bisa ditransfer.")
        return

    search = st.text_input("🔎 Cari Kandidat (Nama / Kode Unik)", placeholder="Ketik keyword...", key="trf_single_search")
    if search:
        s = search.strip().lower()
        candidates = [c for c in candidates if s in (c.nama or "").lower() or s in (c.kode_unik or "").lower()]

    if not candidates:
        st.info("Tidak ada kandidat yang cocok.")
        return

    cand_options = {}
    for c in candidates:
        last_stage = get_last_pipeline_stage(c)
        stage_label = last_stage["stage_label"] if last_stage else "Belum ada stage"
        display = f"{c.kode_unik} | {c.nama} | {stage_label}"
        cand_options[display] = c.id

    selected_display = st.selectbox("Pilih Kandidat", list(cand_options.keys()), key="trf_single_cand")
    selected_id = cand_options.get(selected_display)
    if not selected_id:
        return

    candidate = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
    if not candidate:
        st.error("Kandidat tidak ditemukan.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nama:** {candidate.nama}")
        st.markdown(f"**Kode Unik:** {candidate.kode_unik}")
        st.markdown(f"**Posisi:** {candidate.posisi or '-'}")
        st.markdown(f"**PIC:** {candidate.rekruter or '-'}")
    with col2:
        last_stage = get_last_pipeline_stage(candidate)
        if last_stage:
            st.markdown(f"**Tahap Terakhir:** {last_stage['stage_label']}")
            st.markdown(f"**Status:** {last_stage['status']}")
        else:
            st.info("Belum masuk tahap pipeline apapun.")

    st.markdown("---")
    st.markdown("### Transfer Ke FPTK Tujuan")
    target_fptk = st.selectbox("Pilih FPTK Tujuan", list(fptk_options.keys()), key="trf_single_target")
    new_kode_unik = fptk_options[target_fptk]

    reason = st.text_area("Alasan Transfer *", height=100, key="trf_single_reason")

    if st.button("🔄 Transfer Kandidat", type="primary", use_container_width=True, key="btn_trf_single"):
        if not reason or len(reason.strip()) < 10:
            st.error("❌ Alasan wajib diisi minimal 10 karakter!")
        else:
            result = transfer_candidate(db, selected_id, new_kode_unik, reason.strip(),
                user.id, user.display_name or user.username)
            if result["success"]:
                st.success(f"✅ Kandidat **{candidate.nama}** berhasil ditransfer!")
                st.info(f"📋 Dari: {result['old_kode_unik']} → Ke: {result['new_kode_unik']}")
                st.balloons()
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ Gagal transfer: {result.get('error', 'Unknown error')}")


def render_transfer_bulk(db, user, admin):
    fptk_list = db.query(FPTK).filter(FPTK.status == "OP").order_by(FPTK.kode_unik).all()
    fptk_options = {}
    for f in fptk_list:
        display = f"{f.kode_unik} | {f.posisi[:50]}" if len(str(f.posisi)) > 50 else f"{f.kode_unik} | {f.posisi}"
        fptk_options[display] = f.kode_unik

    if not fptk_options:
        st.warning("Tidak ada FPTK OP yang tersedia.")
        return

    filter_fptk = st.selectbox("Filter dari FPTK Asal", ["Semua"] + list(fptk_options.keys()), key="trf_bulk_filter")

    query = db.query(DBSourcing)
    if filter_fptk != "Semua":
        query = query.filter(DBSourcing.kode_unik == fptk_options[filter_fptk])
    if not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)

    candidates = query.limit(500).all()
    if not candidates:
        st.info("Tidak ada kandidat yang bisa ditransfer.")
        return

    search = st.text_input("🔎 Cari Kandidat (Nama / Kode Unik)", placeholder="Ketik keyword...", key="trf_bulk_search")
    if search:
        s = search.strip().lower()
        candidates = [c for c in candidates if s in (c.nama or "").lower() or s in (c.kode_unik or "").lower()]

    if not candidates:
        st.info("Tidak ada kandidat yang cocok.")
        return

    if "bulk_transfer_select_all" not in st.session_state:
        st.session_state.bulk_transfer_select_all = False

    col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 3])
    with col_sel1:
        if st.button("✅ Pilih Semua", use_container_width=True, key="bulk_transfer_select_all_btn"):
            st.session_state.bulk_transfer_select_all = True
            st.rerun()
    with col_sel2:
        if st.button("❌ Batal Pilih", use_container_width=True, key="bulk_transfer_deselect_all_btn"):
            st.session_state.bulk_transfer_select_all = False
            st.rerun()
    with col_sel3:
        st.caption(f"💡 Pilih **{len(candidates)}** kandidat sekaligus atau klik manual per row")

    default_pilih = st.session_state.bulk_transfer_select_all

    bulk_data = []
    for c in candidates:
        last_stage = get_last_pipeline_stage(c)
        bulk_data.append({
            "pilih": default_pilih, "id": c.id, "kode_unik": c.kode_unik,
            "nama": c.nama, "posisi": (c.posisi or "")[:50],
            "rekruter": c.rekruter or "-",
            "tahap_terakhir": last_stage["stage_label"] if last_stage else "-",
        })

    bulk_df = pd.DataFrame(bulk_data)

    edited_df = st.data_editor(
        bulk_df, use_container_width=True, hide_index=True,
        column_config={
            "pilih": st.column_config.CheckboxColumn("Pilih", default=False),
            "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "kode_unik": st.column_config.TextColumn("Kode Unik", disabled=True, width="medium"),
            "nama": st.column_config.TextColumn("Nama", disabled=True, width="medium"),
            "posisi": st.column_config.TextColumn("Posisi", disabled=True, width="medium"),
            "rekruter": st.column_config.TextColumn("PIC", disabled=True, width="small"),
            "tahap_terakhir": st.column_config.TextColumn("Tahap Terakhir", disabled=True, width="medium"),
        }, key="bulk_transfer_table"
    )

    selected_ids = edited_df[edited_df["pilih"] == True]["id"].tolist()
    st.markdown(f"**{len(selected_ids)} kandidat dipilih**")

    if selected_ids:
        st.markdown("---")
        st.markdown("### Transfer Ke FPTK Tujuan")
        target_fptk_bulk = st.selectbox("Pilih FPTK Tujuan", list(fptk_options.keys()), key="trf_bulk_target")
        new_kode_unik_bulk = fptk_options[target_fptk_bulk]

        reason_bulk = st.text_area("Alasan Transfer *", height=100, key="trf_bulk_reason")

        if st.button("🔄 Transfer Semua Kandidat Terpilih", type="primary", use_container_width=True, key="btn_trf_bulk"):
            if not reason_bulk or len(reason_bulk.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                result = transfer_candidates_bulk(db, selected_ids, new_kode_unik_bulk,
                    reason_bulk.strip(), user.id, user.display_name or user.username)
                st.session_state.bulk_transfer_select_all = False
                st.success(f"✅ Transfer selesai!")
                st.info(f"📋 Berhasil: {result['success_count']}")
                st.warning(f"⚠️ Gagal: {result['error_count']}")
                if result["errors"]:
                    with st.expander("❌ Detail Error"):
                        for err in result["errors"]:
                            st.text(err)
                st.balloons()
                time.sleep(1)
                st.rerun()


def render_transfer_history(db, admin):
    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("Cari (Nama / Kode Unik)", placeholder="Ketik keyword...", key="trf_hist_search")
    with col2:
        filter_type = st.selectbox("Filter", ["Semua", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir"], key="trf_hist_time")

    query = db.query(CandidateTransfer).order_by(CandidateTransfer.transferred_at.desc())

    if search:
        s = search.strip()
        query = query.filter(
            (CandidateTransfer.nama.ilike(f"%{s}%")) |
            (CandidateTransfer.old_kode_unik.ilike(f"%{s}%")) |
            (CandidateTransfer.new_kode_unik.ilike(f"%{s}%"))
        )

    if filter_type == "Hari Ini":
        today = datetime.now().date()
        query = query.filter(CandidateTransfer.transferred_at >= datetime.combine(today, datetime.min.time()))
    elif filter_type == "7 Hari Terakhir":
        query = query.filter(CandidateTransfer.transferred_at >= (datetime.now() - pd.Timedelta(days=7)))
    elif filter_type == "30 Hari Terakhir":
        query = query.filter(CandidateTransfer.transferred_at >= (datetime.now() - pd.Timedelta(days=30)))

    histories = query.limit(500).all()

    if not histories:
        st.info("Belum ada history transfer.")
        return

    data = []
    for h in histories:
        data.append({
            "Tanggal": h.transferred_at.strftime("%d/%m/%Y %H:%M") if h.transferred_at else "-",
            "Nama": h.nama, "Dari Kode Unik": h.old_kode_unik,
            "Ke Kode Unik": h.new_kode_unik,
            "Tahap Terakhir": h.old_pipeline_stage or "-",
            "Alasan": h.reason or "-", "Oleh": h.transferred_by_name or "-",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📊 Statistik")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Transfer", len(histories))

    if histories:
        to_counts = {}
        for h in histories:
            to_counts[h.new_kode_unik] = to_counts.get(h.new_kode_unik, 0) + 1
        if to_counts:
            most_receive = max(to_counts, key=to_counts.get)
            col2.metric("FPTK Paling Sering Menerima", most_receive, f"{to_counts[most_receive]}x")

        from_counts = {}
        for h in histories:
            from_counts[h.old_kode_unik] = from_counts.get(h.old_kode_unik, 0) + 1
        if from_counts:
            most_send = max(from_counts, key=from_counts.get)
            col3.metric("FPTK Paling Sering Mengirim", most_send, f"{from_counts[most_send]}x")

    if st.button("📥 Export CSV", use_container_width=True, key="trf_cand_exp_csv"):
        csv = df.to_csv(index=False)
        st.download_button("⬇️ Download CSV", csv,
            f"candidate_transfer_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")


if __name__ == "__main__":
    show_sourcing_view()
