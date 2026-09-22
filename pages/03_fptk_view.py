# pages/03_fptk_view.py
import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import (
    FPTK, User, MasterDropdown, FPTKDeleteRequest,
    TransferHistory, DBSourcing
)
from core.auth import get_current_user, is_admin, is_it, is_editor
from core.utils import (
    get_filter_options_from_db, calculate_detail_sla, calculate_sla_days,
    get_last_pipeline_stage, transfer_kandidat_to_fptk
)
from datetime import datetime, timedelta
import re
import time


@st.cache_data(ttl=3600)
def get_level_options_fptk():
    LEVEL_OPTIONS = []
    for num in range(1, 6):
        for letter in ['A', 'B', 'C']:
            LEVEL_OPTIONS.append(f"{num}{letter}")
    return LEVEL_OPTIONS


@st.cache_data(ttl=3600)
def get_detail_sla_options():
    return ["OP Belum Lewat SLA", "OP Tidak Lulus SLA", "Closed Lulus SLA", "Closed Tidak Lulus SLA", "Cancel FPTK"]


FALLBACK_BU_OPTIONS = [
    "PT CISARUA MOUNTAIN DAIRY, TBK", "PT JAVA EGG SPECIALITIES", "PT MACROSENTRA NIAGABOGA",
    "PT MACROPRIMA PANGANUTAMA", "PT ARTHA RASA CIMORY", "PT MACROTAMA BINASANTIKA",
]

FALLBACK_DIREKTORAT_OPTIONS = [
    "CEO Office", "CEO, Corsec, & Investor Relation", "Commercial CMD", "Commercial JES",
    "Commercial MP", "Finance & Business Support", "Logistic & Distribution",
    "Manufacture CMD", "Manufacture JES", "Manufacture MP", "Procurement CMD & Corporate",
    "Procurement MP & JES", "Sales General Trade CMD", "Sales General Trade JES",
    "Sales General Trade MP", "Sales International Market", "Sales Modern Trade",
]

FALLBACK_FILTER_KATEGORISASI = ["CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]


def update_all_sla_bulk(db):
    updated_count = 0
    try:
        fptk_list = db.query(FPTK).filter(FPTK.status.in_(["OP", "Closed", "Cancel"])).all()
        for fptk in fptk_list:
            new_detail_sla = calculate_detail_sla(
                status=fptk.status, deadline_sla=fptk.deadline_sla, offering_date=fptk.offering_date
            )
            if fptk.detail_sla != new_detail_sla:
                fptk.detail_sla = new_detail_sla
                fptk.last_updated_at = datetime.now()
                updated_count += 1
        if updated_count > 0:
            db.commit()
        else:
            db.rollback()
        return updated_count
    except Exception as e:
        db.rollback()
        print(f"Error updating SLA: {str(e)}")
        return -1


def get_kandidat_options_for_fptk(db, kode_unik):
    if not kode_unik:
        return []
    kandidat_list = db.query(DBSourcing).filter(DBSourcing.kode_unik == kode_unik).all()
    result = []
    for k in kandidat_list:
        last = get_last_pipeline_stage(k)
        result.append({
            "id": k.id, "nama": k.nama, "email": k.email, "hp": k.nomor_hp,
            "posisi": k.posisi, "kode_unik": k.kode_unik,
            "last_stage": last["stage_label"] if last else "Belum ada stage",
        })
    return result


def get_all_kandidat_from_other_kode(db, current_kode_unik):
    kandidat_list = db.query(DBSourcing).filter(
        DBSourcing.kode_unik != current_kode_unik
    ).order_by(DBSourcing.kode_unik, DBSourcing.nama).limit(500).all()

    result = []
    for k in kandidat_list:
        last = get_last_pipeline_stage(k)
        result.append({
            "id": k.id, "nama": k.nama, "email": k.email, "hp": k.nomor_hp,
            "posisi": k.posisi, "kode_unik": k.kode_unik, "rekruter": k.rekruter,
            "last_stage": last["stage_label"] if last else "Belum ada stage",
        })
    return result


def render_kandidat_picker_outside_form(db, kode_unik_input, key_prefix, default_value="", user=None):
    """
    Picker di LUAR form — interaktif.
    Return dict:
    {
        "nama": str,           # nama kandidat yang dipilih/diketik
        "mode": str,           # "dropdown" / "manual" / "transfer"
        "transfer_id": int,    # ID sourcing kalau mode transfer
        "transfer_reason": str # alasan transfer
    }
    """
    kandidat_list = get_kandidat_options_for_fptk(db, kode_unik_input)

    mode_key = f"{key_prefix}_mode"
    value_key = f"{key_prefix}_value"
    transfer_id_key = f"{key_prefix}_transfer_id"
    transfer_reason_key = f"{key_prefix}_transfer_reason"

    if mode_key not in st.session_state:
        if kandidat_list:
            st.session_state[mode_key] = "dropdown"
        elif default_value:
            st.session_state[mode_key] = "manual"
        else:
            st.session_state[mode_key] = "manual"

    mode_labels = {
        "dropdown": "📋 Pilih dari DB Sourcing (kandidat di kode unik ini)",
        "manual": "✏️ Ketik Manual",
        "transfer": "🔄 Transfer dari Kode Unik Lain"
    }

    if kandidat_list:
        mode_options = ["dropdown", "manual", "transfer"]
    else:
        st.caption(f"ℹ️ Belum ada kandidat di DB Sourcing untuk kode unik `{kode_unik_input}`.")
        mode_options = ["manual", "transfer"]

    current_mode = st.session_state.get(mode_key, "manual")
    if current_mode not in mode_options:
        current_mode = mode_options[0]
        st.session_state[mode_key] = current_mode

    mode = st.radio(
        "Mode Input Nama Kandidat",
        mode_options,
        format_func=lambda x: mode_labels[x],
        index=mode_options.index(current_mode),
        horizontal=False,
        key=f"{key_prefix}_radio"
    )
    st.session_state[mode_key] = mode

    result = {
        "nama": "",
        "mode": mode,
        "transfer_id": None,
        "transfer_reason": ""
    }

    # ============================================================
    # MODE 1: DROPDOWN
    # ============================================================
    if mode == "dropdown" and kandidat_list:
        options = {}
        for k in kandidat_list:
            display = f"{k['nama']} | {k['email'] or '-'} | {k['last_stage']}"
            options[display] = k['nama']

        default_idx = 0
        if default_value:
            for i, (disp, nama) in enumerate(options.items()):
                if nama == default_value:
                    default_idx = i
                    break

        selected = st.selectbox(
            "Nama Kandidat (dari DB Sourcing)",
            list(options.keys()),
            index=default_idx,
            key=f"{key_prefix}_select"
        )
        result["nama"] = options.get(selected, "")

    # ============================================================
    # MODE 2: MANUAL
    # ============================================================
    elif mode == "manual":
        manual_val = st.text_input(
            "Nama Kandidat (Manual)",
            value=default_value,
            placeholder="Ketik nama kandidat manual",
            key=f"{key_prefix}_manual"
        )
        result["nama"] = manual_val

    # ============================================================
    # MODE 3: TRANSFER
    # ============================================================
    elif mode == "transfer":
        st.markdown("**Transfer Kandidat dari Kode Unik Lain**")
        st.caption("Kandidat akan di-duplikat ke kode unik FPTK ini + dicatat di history transfer.")

        if default_value:
            st.warning(f"⚠️ FPTK ini sudah punya kandidat: **{default_value}**. Kosongin dulu field manual biar bisa transfer.")

        all_kandidat = get_all_kandidat_from_other_kode(db, kode_unik_input)

        if not all_kandidat:
            st.warning("Tidak ada kandidat di DB Sourcing dari kode unik lain.")
            return result

        search_transfer = st.text_input(
            "🔎 Cari Kandidat (Nama / Kode Unik)",
            placeholder="Ketik keyword...",
            key=f"{key_prefix}_search_transfer"
        )

        filtered_kandidat = all_kandidat
        if search_transfer:
            s = search_transfer.strip().lower()
            filtered_kandidat = [
                k for k in all_kandidat
                if s in (k['nama'] or "").lower() or s in (k['kode_unik'] or "").lower()
            ]

        if not filtered_kandidat:
            st.info("Tidak ada kandidat yang cocok.")
            return result

        options_transfer = {}
        for k in filtered_kandidat:
            display = f"{k['kode_unik']} | {k['nama']} | {(k['posisi'] or '')[:30]} | {k['last_stage']}"
            options_transfer[display] = k['id']

        selected_transfer = st.selectbox(
            "Pilih Kandidat dari Kode Unik Lain",
            list(options_transfer.keys()),
            key=f"{key_prefix}_transfer_select"
        )

        selected_id = options_transfer.get(selected_transfer)

        if selected_id:
            kandidat_detail = next((k for k in filtered_kandidat if k['id'] == selected_id), None)
            if kandidat_detail:
                with st.expander("📋 Preview Kandidat", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Nama:** {kandidat_detail['nama']}")
                        st.markdown(f"**Kode Unik Asal:** {kandidat_detail['kode_unik']}")
                        st.markdown(f"**Email:** {kandidat_detail['email'] or '-'}")
                    with col2:
                        st.markdown(f"**Posisi:** {kandidat_detail['posisi'] or '-'}")
                        st.markdown(f"**PIC:** {kandidat_detail.get('rekruter', '-')}")
                        st.markdown(f"**Tahap Terakhir:** {kandidat_detail['last_stage']}")

                result["nama"] = kandidat_detail['nama']
                result["transfer_id"] = selected_id

        reason_transfer = st.text_area(
            "Alasan Transfer *",
            placeholder="Contoh: Kandidat cocok untuk FPTK ini, recycle kandidat, dll. (min 10 karakter)",
            height=100,
            key=f"{key_prefix}_reason"
        )
        result["transfer_reason"] = reason_transfer.strip() if reason_transfer else ""

    # Simpan di session state biar bisa dibaca saat submit
    st.session_state[value_key] = result["nama"]
    st.session_state[transfer_id_key] = result["transfer_id"]
    st.session_state[transfer_reason_key] = result["transfer_reason"]

    return result


@st.dialog("Request Hapus FPTK ke Admin")
def request_delete_fptk(db, fptk_id, kode_unik, posisi, pic_name):
    st.info(f"**FPTK:** {kode_unik} | {posisi}")
    st.caption("Request Anda akan dikirim ke Admin untuk di-approve.")
    reason = st.text_area("Alasan Request Hapus *", height=150, key="reason_delete_fptk")
    st.caption("Alasan wajib diisi minimal 10 karakter.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Kirim Request", type="primary", use_container_width=True, key="btn_req_del_fptk"):
            if not reason or len(reason.strip()) < 10:
                st.error("Alasan wajib diisi minimal 10 karakter!")
            else:
                try:
                    existing = db.query(FPTKDeleteRequest).filter(
                        FPTKDeleteRequest.fptk_id == fptk_id,
                        FPTKDeleteRequest.status == "PENDING"
                    ).first()
                    if existing:
                        st.warning("Request sudah ada dan masih PENDING.")
                    else:
                        user = get_current_user(db)
                        new_request = FPTKDeleteRequest(
                            fptk_id=fptk_id, kode_unik=kode_unik, posisi=posisi,
                            pic_recruiter=pic_name, reason=reason.strip(), status="PENDING",
                            requested_by=user.id if user else None,
                            requested_by_name=user.display_name if user else "Unknown",
                            requested_at=datetime.now()
                        )
                        db.add(new_request)
                        db.commit()
                        st.success("Request berhasil dikirim!")
                        time.sleep(0.5)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    db.rollback()
    with col2:
        if st.button("Batal", use_container_width=True, key="btn_cancel_req_del_fptk"):
            st.rerun()


@st.dialog("HAPUS FPTK PERMANEN")
def confirm_delete_fptk(db, fptk_id, kode_unik, posisi):
    st.error(f"Anda akan menghapus FPTK **{kode_unik}** - **{posisi}** secara PERMANEN!")
    st.warning("TINDAKAN INI TIDAK DAPAT DIBATALKAN!")
    confirm_kode = st.text_input(f"Ketik kode unik **{kode_unik}** untuk konfirmasi:", key="confirm_del_fptk")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ya, Hapus Permanen", type="primary", use_container_width=True, key="btn_confirm_del_fptk"):
            if confirm_kode.strip() == kode_unik:
                try:
                    fptk = db.query(FPTK).filter(FPTK.id == fptk_id).first()
                    if fptk:
                        try:
                            db.query(TransferHistory).filter(TransferHistory.fptk_id == fptk_id).delete(synchronize_session=False)
                        except Exception:
                            pass
                        db.query(FPTKDeleteRequest).filter(FPTKDeleteRequest.fptk_id == fptk_id).delete(synchronize_session=False)
                        db.delete(fptk)
                        db.commit()
                        st.cache_data.clear()
                        st.success(f"FPTK **{kode_unik}** berhasil dihapus!")
                        time.sleep(0.5)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    db.rollback()
            else:
                st.error(f"Kode unik tidak cocok!")
    with col2:
        if st.button("Batal", use_container_width=True, key="btn_cancel_confirm_del_fptk"):
            st.rerun()


def show_fptk_view():
    st.title("📋 FPTK Database")
    st.markdown("Lihat semua data FPTK & transfer.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)

    with st.spinner("Memeriksa SLA..."):
        updated = update_all_sla_bulk(db)
        if updated > 0:
            st.success(f"✅ {updated} data FPTK diperbarui SLA-nya!")
        time.sleep(0.3)

    tab1, tab2 = st.tabs(["📋 Database FPTK", "🔄 Transfer FPTK"])

    with tab1:
        render_fptk_database(db, user, admin)

    with tab2:
        render_transfer_fptk(db, user, admin)


def render_fptk_database(db, user, admin):
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
    divisi_options = filter_opts.get("divisi_options", [])
    dept_options = filter_opts.get("dept_options", [])
    alasan_options = filter_opts.get("alasan_options", [])
    lokasi_onboarding_options = filter_opts.get("lokasi_onboarding_options", [])

    status_options = ["OP", "Closed", "Cancel"]
    LEVEL_OPTIONS = get_level_options_fptk()
    detail_sla_options = get_detail_sla_options()

    with st.sidebar:
        st.markdown("### 🔍 Filter FPTK")
        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...", key="fptk_search")
        status_filter = st.selectbox("Status", ["Semua"] + status_options, key="fptk_status")
        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + pic_options_all, key="fptk_pic")
        bu_filter = st.selectbox("Business Unit", ["Semua"] + bu_options, key="fptk_bu")
        dir_filter = st.selectbox("Direktorat", ["Semua"] + direktorat_options, key="fptk_dir")
        divisi_filter = st.selectbox("Divisi", ["Semua"] + (divisi_options if divisi_options else ["-"]), key="fptk_div")
        dept_filter = st.selectbox("Department", ["Semua"] + (dept_options if dept_options else ["-"]), key="fptk_dept")
        filter_kat = st.selectbox("Filter Kategorisasi", ["Semua"] + filter_kategorisasi_options, key="fptk_kat")
        st.markdown("---")
        if st.button("🔄 Refresh SLA Now", use_container_width=True, type="primary", key="fptk_refresh_sla"):
            with st.spinner("Memperbarui SLA..."):
                updated = update_all_sla_bulk(db)
                if updated > 0:
                    st.success(f"✅ {updated} data SLA diperbarui!")
                else:
                    st.info("✅ Semua SLA sudah sesuai.")
                time.sleep(0.5)
                st.rerun()
        if st.button("🔄 Reset Filter", use_container_width=True, key="fptk_reset"):
            st.rerun()

    query = db.query(FPTK)

    if search:
        query = query.filter((FPTK.kode_unik.ilike(f"%{search}%")) | (FPTK.posisi.ilike(f"%{search}%")))
    if status_filter != "Semua":
        query = query.filter(FPTK.status == status_filter)
    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)
    if bu_filter != "Semua":
        query = query.filter(FPTK.business_unit == bu_filter)
    if dir_filter != "Semua":
        query = query.filter(FPTK.direktorat == dir_filter)
    if divisi_filter != "Semua":
        query = query.filter(FPTK.divisi == divisi_filter)
    if dept_filter != "Semua":
        query = query.filter(FPTK.department == dept_filter)
    if filter_kat != "Semua":
        query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)

    total = query.count()
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

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        if st.button("📥 Export CSV (Filtered)", use_container_width=True, key="fptk_exp_csv"):
            df_export = pd.read_sql(query.statement, db.bind)
            csv = df_export.to_csv(index=False)
            st.download_button("⬇️ Download CSV", csv, f"fptk_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="dl_fptk_csv")
    with col_exp2:
        if st.button("📊 Export Excel (Filtered)", use_container_width=True, key="fptk_exp_xlsx"):
            from io import BytesIO
            df_export = pd.read_sql(query.statement, db.bind)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='FPTK', index=False)
            output.seek(0)
            st.download_button("⬇️ Download Excel", output.getvalue(), f"fptk_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_fptk_xlsx")

    st.markdown("---")
    st.markdown("### 📋 Daftar FPTK")

    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50, key="fptk_page_size")
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1, key="fptk_page")
    offset = (page - 1) * page_size

    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)

    if 'fptk_date_real' in df.columns:
        df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'])
        df['FPTK Date Real'] = df['fptk_date_real'].dt.strftime('%d/%m/%Y')

    display_cols = ['FPTK Date Real', 'kode_unik', 'posisi', 'pic_recruiter', 'business_unit',
                    'direktorat', 'divisi', 'department', 'status', 'filter_kategorisasi_fptk',
                    'vacancy', 'level_fptk', 'jumlah_sla', 'detail_sla']
    available_cols = [c for c in display_cols if c in df.columns]

    if not df.empty:
        st.dataframe(df[available_cols], use_container_width=True, height=400)

    # ============================================================
    # BULK EDIT FPTK
    # ============================================================
    st.markdown("---")
    st.markdown("### ✏️ Bulk Edit FPTK")
    st.caption("Pilih banyak FPTK sekaligus, lalu update field yang sama untuk semuanya.")

    bulk_query = db.query(FPTK)
    if status_filter != "Semua":
        bulk_query = bulk_query.filter(FPTK.status == status_filter)
    if pic_filter != "Semua":
        bulk_query = bulk_query.filter(FPTK.pic_recruiter == pic_filter)
    if bu_filter != "Semua":
        bulk_query = bulk_query.filter(FPTK.business_unit == bu_filter)
    if dir_filter != "Semua":
        bulk_query = bulk_query.filter(FPTK.direktorat == dir_filter)
    if divisi_filter != "Semua":
        bulk_query = bulk_query.filter(FPTK.divisi == divisi_filter)
    if dept_filter != "Semua":
        bulk_query = bulk_query.filter(FPTK.department == dept_filter)
    if filter_kat != "Semua":
        bulk_query = bulk_query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)
    if search:
        bulk_query = bulk_query.filter((FPTK.kode_unik.ilike(f"%{search}%")) | (FPTK.posisi.ilike(f"%{search}%")))
    if not admin:
        bulk_query = bulk_query.filter(FPTK.pic_recruiter == user.pic_recruiter)

    bulk_fptk = bulk_query.limit(500).all()

    if not bulk_fptk:
        st.info("Tidak ada FPTK yang bisa di-bulk edit dengan filter ini.")
    else:
        if "bulk_fptk_select_all" not in st.session_state:
            st.session_state.bulk_fptk_select_all = False

        col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 3])
        with col_sel1:
            if st.button("✅ Pilih Semua", use_container_width=True, key="bulk_fptk_select_all_btn"):
                st.session_state.bulk_fptk_select_all = True
                st.rerun()
        with col_sel2:
            if st.button("❌ Batal Pilih", use_container_width=True, key="bulk_fptk_deselect_all_btn"):
                st.session_state.bulk_fptk_select_all = False
                st.rerun()
        with col_sel3:
            st.caption(f"💡 Pilih **{len(bulk_fptk)}** FPTK sekaligus atau klik manual per row")

        default_pilih = st.session_state.bulk_fptk_select_all

        bulk_df = pd.DataFrame([{
            "pilih": default_pilih, "id": f.id, "kode_unik": f.kode_unik, "posisi": f.posisi,
            "pic_recruiter": f.pic_recruiter, "status": f.status, "level_fptk": f.level_fptk,
            "business_unit": f.business_unit, "divisi": f.divisi or "-", "department": f.department or "-",
        } for f in bulk_fptk])

        edited_df = st.data_editor(
            bulk_df, use_container_width=True, hide_index=True,
            column_config={
                "pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "kode_unik": st.column_config.TextColumn("Kode Unik", disabled=True, width="medium"),
                "posisi": st.column_config.TextColumn("Posisi", disabled=True, width="medium"),
                "pic_recruiter": st.column_config.TextColumn("PIC", disabled=True, width="small"),
                "status": st.column_config.TextColumn("Status", disabled=True, width="small"),
                "level_fptk": st.column_config.TextColumn("Level", disabled=True, width="small"),
                "business_unit": st.column_config.TextColumn("BU", disabled=True, width="medium"),
                "divisi": st.column_config.TextColumn("Divisi", disabled=True, width="medium"),
                "department": st.column_config.TextColumn("Department", disabled=True, width="medium"),
            }, key="bulk_edit_table"
        )

        selected_ids = edited_df[edited_df["pilih"] == True]["id"].tolist()
        st.markdown(f"**{len(selected_ids)} FPTK dipilih**")

        if selected_ids:
            st.markdown("#### Field yang Mau Diubah")
            all_bulk_fields = {
                "level_fptk": "Level FPTK (auto recalc SLA)", "level_number": "Level Number",
                "status": "Status (auto recalc SLA)", "business_unit": "Business Unit",
                "direktorat": "Direktorat", "divisi": "Divisi", "department": "Department",
                "alasan_permintaan_fptk": "Alasan Permintaan FPTK", "category_fptk": "Category FPTK",
                "pic_recruiter": "PIC Recruiter", "filter_kategorisasi_fptk": "Filter Kategorisasi FPTK",
                "vacancy": "Vacancy", "offering_date": "Offering Date", "fptk_cancel_date": "FPTK Cancel Date",
                "jumlah_sla": "Jumlah SLA", "deadline_sla": "Deadline SLA", "detail_sla": "Detail SLA",
                "estimasi_join": "Estimasi Join", "kebutuhan_laptop": "Kebutuhan Laptop",
                "lokasi_onboarding": "Lokasi Onboarding", "user_manager": "User (Manager)",
                "indirect_user": "Indirect User", "lokasi_kerja": "Lokasi Kerja", "lokasi_hr": "Lokasi HR",
                "status_karyawan": "Status Karyawan", "kode_bu": "Kode BU",
                "fptk_availability": "FPTK Availability", "remark": "Remark",
            }

            field_to_update = st.selectbox("Pilih Field", list(all_bulk_fields.keys()),
                format_func=lambda x: all_bulk_fields[x], key="bulk_field_select_v2")

            new_value = None

            if field_to_update == "level_fptk":
                new_value = st.selectbox("Level FPTK", LEVEL_OPTIONS, key="bulk_v2_level")
            elif field_to_update == "level_number":
                new_value = st.number_input("Level Number", min_value=1, max_value=5, value=1, key="bulk_v2_levelnum")
            elif field_to_update == "status":
                new_value = st.selectbox("Status", ["OP", "Closed", "Cancel"], key="bulk_v2_status")
            elif field_to_update == "business_unit":
                new_value = st.selectbox("Business Unit", [""] + bu_options, key="bulk_v2_bu")
            elif field_to_update == "direktorat":
                new_value = st.selectbox("Direktorat", [""] + direktorat_options, key="bulk_v2_dir")
            elif field_to_update == "divisi":
                new_value = st.selectbox("Divisi", [""] + divisi_options if divisi_options else [""], key="bulk_v2_div")
            elif field_to_update == "department":
                new_value = st.selectbox("Department", [""] + dept_options if dept_options else [""], key="bulk_v2_dept")
            elif field_to_update == "pic_recruiter":
                new_value = st.selectbox("PIC Recruiter", pic_options_all, key="bulk_v2_pic")
            elif field_to_update == "filter_kategorisasi_fptk":
                new_value = st.selectbox("Filter Kategorisasi", ["CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"], key="bulk_v2_kat")
            elif field_to_update == "category_fptk":
                new_value = st.selectbox("Category FPTK", ["NEW", "REPLACEMENT"], key="bulk_v2_cat")
            elif field_to_update == "vacancy":
                new_value = st.number_input("Vacancy", min_value=1, value=1, key="bulk_v2_vac")
            elif field_to_update in ["offering_date", "fptk_cancel_date", "deadline_sla", "estimasi_join"]:
                new_value = st.date_input("Tanggal", datetime.now().date(), key=f"bulk_v2_date_{field_to_update}")
            elif field_to_update == "jumlah_sla":
                new_value = st.number_input("Jumlah SLA (hari)", min_value=1, max_value=365, value=30, key="bulk_v2_sla")
            elif field_to_update == "detail_sla":
                new_value = st.selectbox("Detail SLA", detail_sla_options, key="bulk_v2_detailsla")
            elif field_to_update == "kebutuhan_laptop":
                new_value = st.selectbox("Kebutuhan Laptop", ["Ya", "Tidak"], key="bulk_v2_laptop")
            elif field_to_update == "fptk_availability":
                new_value = st.selectbox("FPTK Availability", ["V", "X", "Y", "N"], key="bulk_v2_avail")
            elif field_to_update == "alasan_permintaan_fptk":
                new_value = st.selectbox("Alasan", [""] + alasan_options, key="bulk_v2_alasan")
            elif field_to_update == "lokasi_onboarding":
                new_value = st.selectbox("Lokasi Onboarding", [""] + lokasi_onboarding_options, key="bulk_v2_onboard")
            else:
                new_value = st.text_area("Nilai Baru", key="bulk_v2_text")

            col_apply, col_cancel = st.columns(2)
            with col_apply:
                if st.button("✅ Terapkan", type="primary", use_container_width=True, key="bulk_v2_apply"):
                    try:
                        updated_count = 0
                        for fptk_id in selected_ids:
                            fptk_obj = db.query(FPTK).filter(FPTK.id == fptk_id).first()
                            if not fptk_obj:
                                continue
                            setattr(fptk_obj, field_to_update, new_value)

                            if field_to_update == "level_fptk":
                                match = re.search(r'(\d+)', str(new_value))
                                new_level_num = int(match.group(1)) if match else 1
                                fptk_obj.level_number = new_level_num
                                sla_days = calculate_sla_days(new_level_num)
                                fptk_obj.jumlah_sla = sla_days
                                if fptk_obj.fptk_date_real:
                                    fptk_obj.deadline_sla = fptk_obj.fptk_date_real + timedelta(days=sla_days)
                                fptk_obj.detail_sla = calculate_detail_sla(
                                    status=fptk_obj.status, deadline_sla=fptk_obj.deadline_sla,
                                    offering_date=fptk_obj.offering_date
                                )

                            if field_to_update == "status":
                                fptk_obj.detail_sla = calculate_detail_sla(
                                    status=new_value, deadline_sla=fptk_obj.deadline_sla,
                                    offering_date=fptk_obj.offering_date
                                )

                            fptk_obj.last_updated_at = datetime.now()
                            fptk_obj.last_compile_action = "BULK_EDIT"
                            updated_count += 1

                        db.commit()
                        st.session_state.bulk_fptk_select_all = False
                        st.cache_data.clear()
                        st.success(f"✅ Berhasil update {updated_count} FPTK!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        db.rollback()

            with col_cancel:
                if st.button("❌ Batal", use_container_width=True, key="bulk_v2_cancel"):
                    st.session_state.bulk_fptk_select_all = False
                    st.rerun()

    st.markdown("---")
    st.markdown("### ✏️ Pilih Data FPTK")

    df_all = pd.read_sql(query.statement, db.bind)
    if not df_all.empty:
        select_options = {}
        for _, row in df_all.iterrows():
            kode = row.get('kode_unik', '')
            posisi = row.get('posisi', '')
            display = f"{kode} | {posisi[:50]}..." if len(str(posisi)) > 50 else f"{kode} | {posisi}"
            select_options[display] = row.get('id')
        selected_display = st.selectbox("Pilih FPTK", list(select_options.keys()), key="fptk_select")
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

    st.markdown("---")
    st.markdown("### ⚙️ Aksi Data")

    existing_request = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.fptk_id == detail.id, FPTKDeleteRequest.status == "PENDING"
    ).first()
    all_requests = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.fptk_id == detail.id
    ).order_by(FPTKDeleteRequest.requested_at.desc()).all()

    col1, col2, col3 = st.columns(3)
    if admin:
        with col1:
            if st.button("🗑️ Hapus Langsung (Admin)", type="secondary", use_container_width=True, key=f"del_fptk_{detail.id}"):
                confirm_delete_fptk(db, detail.id, detail.kode_unik, detail.posisi)
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
                        st.caption(f"By: {req.requested_by_name}")
                        st.caption(f"Alasan: {req.reason}")
                        st.markdown("---")
    else:
        with col1:
            if existing_request:
                st.info(f"📩 Request PENDING")
            else:
                if detail.pic_recruiter == user.pic_recruiter:
                    if st.button("📩 Request Hapus", type="primary", use_container_width=True, key=f"req_del_fptk_{detail.id}"):
                        request_delete_fptk(db, detail.id, detail.kode_unik, detail.posisi, detail.pic_recruiter)
                else:
                    st.caption("ℹ️ Hanya PIC pemilik")
        with col2:
            if all_requests:
                st.caption(f"📋 {len(all_requests)} request")
            else:
                st.caption("Belum ada request")
        with col3:
            if all_requests:
                with st.expander("📋 History"):
                    for req in all_requests:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.status}**")
                        st.caption(f"Alasan: {req.reason}")
                        st.markdown("---")

    st.markdown("---")
    st.markdown("### 📋 Detail FPTK")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        st.markdown(f"**Posisi:** {detail.posisi}")
        st.markdown(f"**PIC Recruiter:** {detail.pic_recruiter}")
        st.markdown(f"**Business Unit:** {detail.business_unit}")
        st.markdown(f"**Direktorat:** {detail.direktorat}")
        st.markdown(f"**Divisi:** {detail.divisi or '-'}")
        st.markdown(f"**Department:** {detail.department or '-'}")
        st.markdown(f"**Level FPTK:** {detail.level_fptk} (Level {detail.level_number})")
        st.markdown(f"**Alasan:** {detail.alasan_permintaan_fptk or '-'}")
        st.markdown(f"**Category:** {detail.category_fptk or '-'}")
        st.markdown(f"**Nama Kandidat:** {detail.nama_kandidat or '-'}")
    with col2:
        st.markdown(f"**Status:** {detail.status}")
        st.markdown(f"**Filter Kategorisasi:** {detail.filter_kategorisasi_fptk}")
        st.markdown(f"**Tanggal FPTK:** {detail.fptk_date_real.strftime('%d/%m/%Y') if detail.fptk_date_real else '-'}")
        st.markdown(f"**Vacancy:** {detail.vacancy}")
        st.markdown(f"**Jumlah SLA:** {detail.jumlah_sla} hari")
        st.markdown(f"**Deadline SLA:** {detail.deadline_sla.strftime('%d/%m/%Y') if detail.deadline_sla else '-'}")
        st.markdown(f"**Detail SLA:** {detail.detail_sla or '-'}")

    if not can_edit:
        st.warning("⚠️ Anda hanya bisa mengedit data FPTK milik PIC Anda sendiri.")
        return

    st.markdown("---")
    st.markdown("### ✏️ Edit Data FPTK")

    # ============================================================
    # NAMA KANDIDAT PICKER — DI LUAR FORM (INTERAKTIF)
    # ============================================================
    st.markdown("#### 👤 Nama Kandidat")
    st.caption(f"Kode Unik FPTK: `{detail.kode_unik}` — pilih mode di bawah")

    picker_result = render_kandidat_picker_outside_form(
        db,
        detail.kode_unik,
        f"edit_fptk_kandidat_{detail.id}",
        default_value=detail.nama_kandidat or "",
        user=user
    )

    st.markdown("---")

    # ============================================================
    # FORM EDIT FPTK — DI DALAM FORM
    # ============================================================
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
            new_offering_date = st.date_input("Offering Date", value=detail.offering_date if detail.offering_date else None)
        with col3:
            new_fptk_cancel_date = st.date_input("FPTK Cancel Date",
                value=detail.fptk_cancel_date if detail.fptk_cancel_date else None)

        st.markdown("---")
        st.markdown("#### Data Tambahan")

        col1, col2 = st.columns(2)
        with col1:
            new_user_manager = st.text_input("User (Manager)", value=detail.user_manager or "")
        with col2:
            new_remark = st.text_area("Remark", value=detail.remark or "")

        submitted = st.form_submit_button("💾 Update FPTK", type="primary")

    if submitted:
        try:
            # ============================================================
            # BACA NILAI PICKER DARI SESSION STATE
            # ============================================================
            picker_value = st.session_state.get(f"edit_fptk_kandidat_{detail.id}_value", "")
            picker_mode = st.session_state.get(f"edit_fptk_kandidat_{detail.id}_mode", "manual")
            transfer_id = st.session_state.get(f"edit_fptk_kandidat_{detail.id}_transfer_id", None)
            transfer_reason = st.session_state.get(f"edit_fptk_kandidat_{detail.id}_transfer_reason", "")

            new_nama_kandidat = picker_value

            # ============================================================
            # MODE TRANSFER — PROSES TRANSFER
            # ============================================================
            if picker_mode == "transfer" and transfer_id:
                if not transfer_reason or len(transfer_reason) < 10:
                    st.error("❌ Alasan Transfer wajib diisi minimal 10 karakter!")
                    st.stop()

                if detail.nama_kandidat:
                    st.error(f"❌ FPTK ini sudah punya kandidat: **{detail.nama_kandidat}**. Kosongin field manual dulu baru transfer.")
                    st.stop()

                result = transfer_kandidat_to_fptk(
                    db,
                    transfer_id,
                    detail.kode_unik,
                    transfer_reason,
                    user.id,
                    user.display_name or user.username
                )

                if not result["success"]:
                    st.error(f"❌ Gagal transfer: {result.get('error', 'Unknown error')}")
                    st.stop()

                new_nama_kandidat = result["nama"]
                st.success(f"✅ Kandidat **{result['nama']}** berhasil ditransfer!")
                st.info(f"📋 Dari: {result['old_kode_unik']} → Ke: {result['new_kode_unik']}")

                # Clear transfer state
                st.session_state[f"edit_fptk_kandidat_{detail.id}_transfer_id"] = None
                st.session_state[f"edit_fptk_kandidat_{detail.id}_transfer_reason"] = ""

            # ============================================================
            # LOGIC UPDATE FPTK
            # ============================================================
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

            new_detail_sla_auto = calculate_detail_sla(
                status=new_status, deadline_sla=new_deadline_sla_calc, offering_date=new_offering_date
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
            detail.nama_kandidat = new_nama_kandidat or None
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
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            db.rollback()


# ============================================================
# TAB 2: TRANSFER FPTK
# ============================================================

def render_transfer_fptk(db, user, admin):
    st.markdown("### 🔄 Transfer FPTK")
    st.caption("Transfer FPTK dari satu PIC ke PIC lain.")

    if is_it(db):
        st.info("🔍 Mode View-Only (IT) - Anda hanya bisa melihat history transfer.")
        render_transfer_fptk_history(db)
        return

    if not is_editor(db):
        st.error("❌ Anda tidak memiliki akses untuk transfer FPTK. Hubungi Admin.")
        return

    sub_tab1, sub_tab2 = st.tabs(["🔄 Transfer FPTK", "📜 History Transfer"])

    with sub_tab1:
        render_transfer_fptk_form(db, user)

    with sub_tab2:
        render_transfer_fptk_history(db)


def render_transfer_fptk_form(db, user):
    st.subheader("Pilih FPTK yang akan ditransfer")

    col1, col2 = st.columns([2, 2])
    with col1:
        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik kode unik atau posisi...", key="transfer_fptk_search")
    with col2:
        status_filter = st.selectbox("Filter Status", ["Semua", "OP", "Closed", "Cancel"], key="transfer_fptk_status")

    query = db.query(FPTK)

    if search:
        s = search.strip()
        query = query.filter((FPTK.kode_unik.ilike(f"%{s}%")) | (FPTK.posisi.ilike(f"%{s}%")))

    if status_filter != "Semua":
        query = query.filter(FPTK.status == status_filter)

    query = query.order_by(FPTK.fptk_date_real.desc()).limit(500)
    fptk_list = query.all()

    if not fptk_list:
        st.warning("Tidak ada data FPTK yang cocok.")
        return

    st.markdown(f"**Ditemukan {len(fptk_list)} FPTK**")

    if "bulk_transfer_fptk_select_all" not in st.session_state:
        st.session_state.bulk_transfer_fptk_select_all = False

    col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 3])
    with col_sel1:
        if st.button("✅ Pilih Semua", use_container_width=True, key="bulk_transfer_fptk_select_all_btn"):
            st.session_state.bulk_transfer_fptk_select_all = True
            st.rerun()
    with col_sel2:
        if st.button("❌ Batal Pilih", use_container_width=True, key="bulk_transfer_fptk_deselect_all_btn"):
            st.session_state.bulk_transfer_fptk_select_all = False
            st.rerun()
    with col_sel3:
        st.caption(f"💡 Pilih **{len(fptk_list)}** FPTK sekaligus atau klik manual per row")

    default_pilih = st.session_state.bulk_transfer_fptk_select_all

    display_data = []
    for f in fptk_list:
        display_data.append({
            "pilih": default_pilih, "id": f.id, "kode_unik": f.kode_unik, "posisi": f.posisi,
            "pic_recruiter": f.pic_recruiter, "status": f.status,
            "level_fptk": f.level_fptk, "business_unit": f.business_unit or "-",
        })

    df = pd.DataFrame(display_data)

    edited_df = st.data_editor(
        df, use_container_width=True, hide_index=True,
        column_config={
            "pilih": st.column_config.CheckboxColumn("Pilih", default=False),
            "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "kode_unik": st.column_config.TextColumn("Kode Unik", disabled=True, width="medium"),
            "posisi": st.column_config.TextColumn("Posisi", disabled=True, width="large"),
            "pic_recruiter": st.column_config.TextColumn("PIC Saat Ini", disabled=True, width="medium"),
            "status": st.column_config.TextColumn("Status", disabled=True, width="small"),
            "level_fptk": st.column_config.TextColumn("Level", disabled=True, width="small"),
            "business_unit": st.column_config.TextColumn("BU", disabled=True, width="medium"),
        }, key="transfer_fptk_table"
    )

    selected_ids = edited_df[edited_df["pilih"] == True]["id"].tolist()
    st.markdown(f"**{len(selected_ids)} FPTK dipilih**")

    if not selected_ids:
        st.info("Pilih minimal 1 FPTK untuk ditransfer.")
        return

    st.markdown("---")
    st.markdown("### Transfer Ke PIC Tujuan")

    target_users = db.query(User).filter(
        User.role.in_(['user', 'admin']), User.pic_recruiter.isnot(None)
    ).all()

    target_options = {}
    for u in target_users:
        display = f"{u.pic_recruiter} ({u.username})"
        target_options[display] = u.pic_recruiter

    if not target_options:
        st.warning("Tidak ada PIC tujuan yang tersedia.")
        return

    target_pic_display = st.selectbox("PIC Tujuan", list(target_options.keys()), key="transfer_target_pic")
    target_pic_value = target_options[target_pic_display]

    reason = st.text_area("Alasan Transfer *", placeholder="Isi alasan transfer (min 10 karakter)...", height=100, key="transfer_reason")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Transfer Sekarang", type="primary", use_container_width=True):
            if not reason or len(reason.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                success_count = 0
                error_count = 0
                errors = []

                for fptk_id in selected_ids:
                    try:
                        fptk = db.query(FPTK).filter(FPTK.id == fptk_id).first()
                        if not fptk:
                            error_count += 1
                            errors.append(f"ID {fptk_id}: FPTK tidak ditemukan")
                            continue

                        if fptk.pic_recruiter == target_pic_value:
                            error_count += 1
                            errors.append(f"{fptk.kode_unik}: PIC sudah sama ({target_pic_value})")
                            continue

                        old_pic = fptk.pic_recruiter
                        fptk.pic_recruiter = target_pic_value
                        fptk.last_updated_at = datetime.now()
                        fptk.last_compile_action = "TRANSFER"

                        history = TransferHistory(
                            fptk_id=fptk.id, kode_unik=fptk.kode_unik, posisi=fptk.posisi,
                            from_pic=old_pic, to_pic=target_pic_value, reason=reason.strip(),
                            transferred_by=user.id, transferred_by_name=user.display_name or user.username
                        )
                        db.add(history)
                        db.commit()
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(f"ID {fptk_id}: {str(e)}")
                        db.rollback()

                st.session_state.bulk_transfer_fptk_select_all = False
                st.success(f"✅ Berhasil transfer: {success_count} FPTK")
                if error_count > 0:
                    st.warning(f"⚠️ Gagal: {error_count} FPTK")
                    with st.expander("Detail Error"):
                        for err in errors:
                            st.text(err)

                st.balloons()
                time.sleep(1)
                st.rerun()


def render_transfer_fptk_history(db):
    col1, col2 = st.columns(2)
    with col1:
        pic_options = ["Semua"] + sorted(set([
            p[0] for p in db.query(FPTK.pic_recruiter).distinct().all() if p[0]
        ]))
        pic_filter = st.selectbox("Filter PIC", pic_options, key="transfer_hist_pic")
    with col2:
        search = st.text_input("Cari (Kode Unik / Posisi / Alasan)", placeholder="Ketik keyword...", key="transfer_hist_search")

    filter_type = st.selectbox("Filter Waktu", ["Semua", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir"], key="transfer_hist_time")

    query = db.query(TransferHistory).order_by(TransferHistory.created_at.desc())

    if pic_filter != "Semua":
        query = query.filter((TransferHistory.from_pic == pic_filter) | (TransferHistory.to_pic == pic_filter))

    if search:
        s = search.strip()
        query = query.filter(
            (TransferHistory.kode_unik.ilike(f"%{s}%")) |
            (TransferHistory.posisi.ilike(f"%{s}%")) |
            (TransferHistory.reason.ilike(f"%{s}%"))
        )

    if filter_type == "Hari Ini":
        today = datetime.now().date()
        query = query.filter(TransferHistory.created_at >= datetime.combine(today, datetime.min.time()))
    elif filter_type == "7 Hari Terakhir":
        query = query.filter(TransferHistory.created_at >= (datetime.now() - pd.Timedelta(days=7)))
    elif filter_type == "30 Hari Terakhir":
        query = query.filter(TransferHistory.created_at >= (datetime.now() - pd.Timedelta(days=30)))

    histories = query.limit(500).all()

    if not histories:
        st.info("Belum ada history transfer.")
        return

    data = []
    for h in histories:
        data.append({
            "Tanggal": h.created_at.strftime("%d/%m/%Y %H:%M") if h.created_at else "-",
            "Kode Unik": h.kode_unik, "Posisi": h.posisi or "-",
            "From": h.from_pic, "To": h.to_pic,
            "Alasan": h.reason or "-", "Oleh": h.transferred_by_name or "-"
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📊 Statistik Transfer")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transfer", len(histories))

    to_counts = {}
    for h in histories:
        to_counts[h.to_pic] = to_counts.get(h.to_pic, 0) + 1
    if to_counts:
        most_receive = max(to_counts, key=to_counts.get)
        col2.metric("Paling Sering Menerima", most_receive, f"{to_counts[most_receive]}x")

    from_counts = {}
    for h in histories:
        from_counts[h.from_pic] = from_counts.get(h.from_pic, 0) + 1
    if from_counts:
        most_send = max(from_counts, key=from_counts.get)
        col3.metric("Paling Sering Mengirim", most_send, f"{from_counts[most_send]}x")

    month_counts = {}
    for h in histories:
        if h.created_at:
            month_key = h.created_at.strftime("%B %Y")
            month_counts[month_key] = month_counts.get(month_key, 0) + 1
    if month_counts:
        most_month = max(month_counts, key=month_counts.get)
        col4.metric("Bulan Terbanyak", most_month, f"{month_counts[most_month]}x")

    if st.button("📥 Export CSV", use_container_width=True, key="trf_fptk_exp_csv"):
        csv = df.to_csv(index=False)
        st.download_button("⬇️ Download CSV", csv, f"transfer_history_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
