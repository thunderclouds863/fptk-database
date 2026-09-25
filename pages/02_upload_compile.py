# pages/02_upload_compile.py
import streamlit as st
import pandas as pd
import re
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import func

from core.database import get_db
from core.models import FPTK, MasterDropdown, User, UploadStatus, UploadLog, UploadTemplate, DBKodePosisi, DBSourcing
from core.auth import get_current_user, is_admin, is_editor, hash_file, sanitize_filename
from core.compiler import compile_fptk, translate_error_to_friendly
from core.upload_cycle import get_current_cycle, mark_user_uploading, mark_user_done
from core.validator import validate_fptk_file, validate_db_sourcing_file, validate_db_kode_posisi_file
from core.compiler import compile_fptk, compile_db_sourcing, compile_db_kode_posisi
from core.utils import (
    normalize_key, safe_int, safe_float, safe_string, safe_boolean_char, safe_date,
    parse_date_dmy, calculate_sla_days, calculate_deadline_sla, calculate_detail_sla,
    get_sla_option_list, calculate_filter_kategorisasi, get_position_details,
    add_to_db_kode_posisi, get_single_value, extract_label_value_pairs
)
from core.utils import determine_category_fptk
from core.template_manager import save_template, get_active_template, get_template_bytes
import time


BU_CODE_MAPPING = {
    "CORP": {"nama": "Corporate", "kode": "CORP"},
    "MP": {"nama": "Macroprima Panganutama", "kode": "MP"},
    "CMD": {"nama": "Cisarua Mountain Dairy", "kode": "CMD"},
    "JESS": {"nama": "Java Egg Specialties", "kode": "JESS"},
    "MS": {"nama": "Macrosentra Niagaboga", "kode": "MS"},
}

PIC_MAPPING = {
    "adista": {"name": "Adista", "bu": "CORP", "code": "CORPAdi"},
    "brittney": {"name": "Brittney", "bu": "CORP", "code": "CORPBrit"},
    "eli": {"name": "Eli", "bu": "CORP", "code": "CORPEli"},
    "fiqra": {"name": "Fiqra", "bu": "CORP", "code": "CORPFiq"},
    "karin": {"name": "Karin", "bu": "CORP", "code": "CORPKar"},
    "kenthansen": {"name": "Kenthansen", "bu": "CORP", "code": "CORPKen"},
    "kevin": {"name": "Kevin", "bu": "CORP", "code": "CORPKev"},
    "marta": {"name": "Marta", "bu": "CORP", "code": "CORPMar"},
    "omega": {"name": "Omega", "bu": "CORP", "code": "CORPOme"},
    "salsa": {"name": "Salsa", "bu": "CORP", "code": "CORPSal"},
    "valen": {"name": "Valendra", "bu": "CORP", "code": "CORPVal"},
    "victor": {"name": "Victor", "bu": "CORP", "code": "CORPVic"},
    "yeremia": {"name": "Yeremia", "bu": "CORP", "code": "CORPYer"},
    "zwei": {"name": "Zwei", "bu": "CORP", "code": "CORPZwei"},
    "desi": {"name": "Desi", "bu": "CORP", "code": "CORPDesi"},
    "pauline": {"name": "Pauline", "bu": "MP", "code": "MPPau"},
    "ratih": {"name": "Ratih", "bu": "MP", "code": "MPRat"},
    "achmad": {"name": "Achmad", "bu": "MP", "code": "MPAch"},
    "kasanah": {"name": "Kasanah", "bu": "MP", "code": "MPKas"},
    "alma": {"name": "Alma", "bu": "MP", "code": "MPAlm"},
    "salwa": {"name": "Salwa", "bu": "CMD", "code": "CMDSal"},
    "elsi": {"name": "Elsi", "bu": "CMD", "code": "CMDEls"},
    "wahyu": {"name": "Wahyu", "bu": "CMD", "code": "CMDWah"},
    "riska": {"name": "Riska", "bu": "JESS", "code": "JESSRis"},
    "fiscall": {"name": "Fiscall", "bu": "JESS", "code": "JESSFis"},
    "leo": {"name": "Leo", "bu": "MS", "code": "MSLeo"},
    "adm": {"name": "Admin", "bu": "CORP", "code": "ADM"},
}

PIC_NAMES_BY_BU = {
    "CORP": ["Adista", "Brittney", "Eli", "Fiqra", "Karin", "Kenthansen", "Kevin", "Marta", "Omega", "Salsa", "Valendra", "Victor", "Yeremia", "Zwei", "Desi"],
    "MP": ["Pauline", "Ratih", "Achmad", "Kasanah", "Alma"],
    "CMD": ["Salwa", "Elsi", "Wahyu"],
    "JESS": ["Riska", "Fiscall"],
    "MS": ["Leo"],
}

ALL_PIC_NAMES = sorted([name for names in PIC_NAMES_BY_BU.values() for name in names])
ALL_BU_CODES = sorted(BU_CODE_MAPPING.keys())

LEVEL_OPTIONS = []
for num in range(1, 6):
    for letter in ['A', 'B', 'C']:
        LEVEL_OPTIONS.append(f"{num}{letter}")


def generate_kode_unik(kode_pic, kode_angka, fptk_date):
    if not kode_pic or not fptk_date:
        return ""
    date_code = fptk_date.strftime("%d%m%y")
    angka_part = re.sub(r'[^0-9]', '', str(kode_angka)) if kode_angka else "0"
    if not angka_part:
        angka_part = "0"
    angka_part = angka_part.zfill(3) if len(angka_part) < 3 else angka_part
    return f"{kode_pic}{angka_part}{date_code}"


def generate_kode_angka(db, posisi=None, kode_pic=None):
    all_kode = db.query(FPTK.kode_angka).all()
    max_angka = 0
    for k in all_kode:
        if k[0]:
            num = re.sub(r'[^0-9]', '', str(k[0]))
            if num and num.isdigit():
                max_angka = max(max_angka, int(num))
    return max_angka + 1


def get_last_fptk_date_kode(db, posisi, kode_pic):
    last_entry = db.query(FPTK).filter(
        FPTK.posisi == posisi,
        FPTK.kode_pic == kode_pic
    ).order_by(FPTK.fptk_date_kode.desc()).first()
    if last_entry and last_entry.fptk_date_kode:
        return last_entry.fptk_date_kode
    return None


def check_duplicate(db, kode_unik, posisi):
    if not kode_unik:
        return None
    return db.query(FPTK).filter(
        FPTK.kode_unik == kode_unik,
        FPTK.posisi == posisi
    ).first()


def get_position_details_cached(db, posisi, direktorat=None):
    if not posisi:
        return None
    cache_key = f"pos_{posisi.strip().lower()}_{direktorat.strip().lower() if direktorat else ''}"
    if "position_cache" not in st.session_state:
        st.session_state.position_cache = {}
    if cache_key in st.session_state.position_cache:
        return st.session_state.position_cache[cache_key]
    result = get_position_details(db, posisi, direktorat)
    st.session_state.position_cache[cache_key] = result
    return result


def add_position_to_master(db, posisi, direktorat=None, business_unit=None, location=None,
                           division=None, department=None, user_manager=None, indirect_user=None, kode=None):
    if not posisi:
        return None
    result = add_to_db_kode_posisi(
        db, posisi, direktorat, business_unit, location,
        division, department, user_manager, indirect_user, kode
    )
    if "position_cache" in st.session_state:
        st.session_state.position_cache = {}
    return result


def get_kandidat_options_for_fptk(db, kode_unik):
    if not kode_unik:
        return []
    from core.utils import get_last_pipeline_stage
    kandidat_list = db.query(DBSourcing).filter(DBSourcing.kode_unik == kode_unik).all()
    result = []
    for k in kandidat_list:
        last = get_last_pipeline_stage(k)
        result.append({
            "id": k.id, "nama": k.nama, "email": k.email, "hp": k.nomor_hp,
            "posisi": k.posisi, "last_stage": last["stage_label"] if last else "Belum ada stage",
        })
    return result


def render_kandidat_picker(db, kode_unik_input, key_prefix, default_value=""):
    kandidat_list = get_kandidat_options_for_fptk(db, kode_unik_input)
    mode_key = f"{key_prefix}_mode"
    select_key = f"{key_prefix}_select"
    manual_key = f"{key_prefix}_manual"

    if mode_key not in st.session_state:
        st.session_state[mode_key] = "dropdown" if kandidat_list else "manual"

    if kandidat_list:
        mode = st.radio(
            "Pilih Mode Input Nama Kandidat", ["dropdown", "manual"],
            format_func=lambda x: "Pilih dari DB Sourcing" if x == "dropdown" else "Ketik Manual",
            index=0 if st.session_state[mode_key] == "dropdown" else 1,
            horizontal=True, key=f"{key_prefix}_radio"
        )
        st.session_state[mode_key] = mode
    else:
        st.caption(f"ℹ️ Belum ada kandidat di DB Sourcing untuk kode unik `{kode_unik_input}`. Silakan ketik manual.")
        st.session_state[mode_key] = "manual"
        mode = "manual"

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
        selected = st.selectbox("Nama Kandidat (dari DB Sourcing)", list(options.keys()),
            index=default_idx, key=select_key)
        return options.get(selected, "")
    else:
        return st.text_input("Nama Kandidat (Manual)", value=default_value,
            placeholder="Ketik nama kandidat manual", key=manual_key)


def sanitize_value(value):
    if value == "" or value == " ":
        return None
    return value


def clean_dataframe(df):
    if df is None or df.empty:
        return df
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df = df.dropna(how='all')
    return df


@st.cache_data(ttl=600)
def get_master_options(_db):
    try:
        master_records = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        return {
            'bu_options': sorted(set([m.bu for m in master_records if m.bu])),
            'alasan_options': sorted(set([m.alasan for m in master_records if m.alasan])),
            'category_options': sorted(set([m.category_fptk for m in master_records if m.category_fptk])),
            'filter_options': sorted(set([m.filter_fptk for m in master_records if m.filter_fptk])),
            'status_options': ["OP", "Closed", "Cancel"],
            'lokasi_onboarding_options': sorted(set([m.lokasi_onboarding for m in master_records if m.lokasi_onboarding])),
            'detail_sla_options': sorted(set([m.detail_sla for m in master_records if m.detail_sla])),
            'keterangan_0_options': sorted(set([m.keterangan_0 for m in master_records if m.keterangan_0])),
            'keterangan_1_options': sorted(set([m.keterangan_1 for m in master_records if m.keterangan_1])),
            'keterangan_cancel_options': sorted(set([m.keterangan_cancel for m in master_records if m.keterangan_cancel])),
            'direktorat_options': sorted(set([m.nama_direktorat for m in master_records if m.nama_direktorat])),
            'model_options': sorted(set([m.model for m in master_records if m.model])),
            'sumber_options': sorted(set([m.sumber_sourcing for m in master_records if m.sumber_sourcing])),
            'jenjang_options': sorted(set([m.jenjang_pendidikan for m in master_records if m.jenjang_pendidikan])),
            'univ_options': sorted(set([m.nama_universitas_top10 for m in master_records if m.nama_universitas_top10])),
            'jurusan_options': sorted(set([m.jurusan for m in master_records if m.jurusan])),
            'univ_tier_options': sorted(set([m.university_tier for m in master_records if m.university_tier])),
            'ipk_tier_options': sorted(set([m.ipk_tier for m in master_records if m.ipk_tier])),
            'kode_pic_options': sorted(set([m.kode_pic for m in master_records if m.kode_pic])),
            'divisi_options': sorted(set([m.divisi for m in master_records if m.divisi])),
            'dept_options': sorted(set([m.department for m in master_records if m.department])),
        }
    except Exception:
        return {
            'bu_options': [], 'alasan_options': [], 'category_options': [],
            'filter_options': [], 'status_options': ["OP", "Closed", "Cancel"],
            'lokasi_onboarding_options': [], 'detail_sla_options': [],
            'keterangan_0_options': [], 'keterangan_1_options': [],
            'keterangan_cancel_options': [], 'direktorat_options': [],
            'model_options': [], 'sumber_options': [], 'jenjang_options': [],
            'univ_options': [], 'jurusan_options': [], 'univ_tier_options': [],
            'ipk_tier_options': [], 'kode_pic_options': [],
            'divisi_options': [], 'dept_options': []
        }


@st.cache_data(ttl=3600)
def get_pic_mapping():
    return PIC_MAPPING.copy()


@st.cache_data(ttl=3600)
def get_bu_mapping():
    return BU_CODE_MAPPING.copy()


@st.cache_data(ttl=3600)
def get_level_options():
    return LEVEL_OPTIONS.copy()


@st.dialog("⚠️ Konfirmasi Selesai Upload")
def dialog_confirm_done(db, user_id, cycle_id, cycle_name):
    st.warning("⚠️ Anda yakin sudah **SELESAI** upload untuk cycle ini?")
    st.markdown(f"**Cycle:** {cycle_name}")
    st.markdown("---")

    st.markdown("""
    ### ⚠️ Perhatian:
    - Setelah klik **"Ya, Selesai Upload"**, status Anda menjadi **Done**
    - Anda **masih bisa upload** kalau ada data baru, tapi status akan berubah kembali jadi **"Sedang Upload"**
    - Admin akan menutup cycle setelah semua user **Done**
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Ya, Selesai Upload", type="primary", use_container_width=True, key="btn_confirm_done"):
            try:
                mark_user_done(db, user_id, cycle_id)
                st.success("✅ Status Anda diupdate ke **Done**!")
                st.info("📌 Kalau ada data baru, upload lagi dan status akan kembali ke 'Sedang Upload'.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

    with col2:
        if st.button("❌ Batal", use_container_width=True, key="btn_cancel_done"):
            st.rerun()


def show_upload_compile():
    st.title("📤 Upload & Compile FPTK")
    st.markdown("Upload file Excel recruiter ATAU input FPTK secara manual ATAU paste informasi FPTK dari HR Portal.")

    db = next(get_db())
    if not is_editor(db):
        st.error("❌ Anda tidak memiliki akses untuk upload/compile data. Hubungi Admin.")
        return
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    with st.spinner("📋 Memuat data master..."):
        master_options = get_master_options(db)

    bu_options = master_options['bu_options']
    alasan_options = master_options['alasan_options']
    category_options = master_options['category_options']
    filter_options = master_options['filter_options']
    status_options = master_options['status_options']
    lokasi_onboarding_options = master_options['lokasi_onboarding_options']
    detail_sla_options = master_options['detail_sla_options']
    keterangan_0_options = master_options['keterangan_0_options']
    keterangan_1_options = master_options['keterangan_1_options']
    keterangan_cancel_options = master_options['keterangan_cancel_options']
    direktorat_options = master_options['direktorat_options']
    model_options = master_options['model_options']
    sumber_options = master_options['sumber_options']
    jenjang_options = master_options['jenjang_options']
    univ_options = master_options['univ_options']
    jurusan_options = master_options['jurusan_options']
    univ_tier_options = master_options['univ_tier_options']
    ipk_tier_options = master_options['ipk_tier_options']
    kode_pic_options = master_options['kode_pic_options']
    divisi_options = master_options.get('divisi_options', [])
    dept_options = master_options.get('dept_options', [])
    level_options = get_level_options()

    if is_admin(db):
        st.markdown("---")
        st.subheader("⚙️ Admin - Template Excel")
        template_file = st.file_uploader("Upload Template Excel", type=["xlsx"], key="admin_template_upload")
        if template_file:
            if st.button("💾 Simpan Template", key="save_template_btn"):
                save_template(db, template_file, user.id, template_type="FPTK")
                st.cache_data.clear()
                st.success("✅ Template berhasil diperbarui")
                st.rerun()

    tab1, tab2, tab3 = st.tabs(["📤 Upload Excel (TIDAK TERSEDIA LAGI MAMPUSSS", "📝 Input Manual FPTK", "📧 Paste informasi FPTK dari HR Portal"])

    with tab2:
        st.subheader("📝 Input FPTK Manual")
        st.caption("Input satu per satu. PIC otomatis dari user yang login.")

        if "manual_posisi" not in st.session_state:
            st.session_state.manual_posisi = ""
        if "manual_direktorat" not in st.session_state:
            st.session_state.manual_direktorat = ""
        if "manual_position_data" not in st.session_state:
            st.session_state.manual_position_data = {}

        pic_mapping = get_pic_mapping()

        user_pic_name = user.pic_recruiter or user.display_name or user.username
        user_pic_code = user.kode_pic or ""
        user_pic_bu = user.business_unit or ""

        for key, val in pic_mapping.items():
            if val["name"].lower() == user_pic_name.lower():
                user_pic_code = val["code"]
                user_pic_bu = val["bu"]
                break

        if not user_pic_code:
            for key, val in pic_mapping.items():
                if key == user.username.lower():
                    user_pic_name = val["name"]
                    user_pic_code = val["code"]
                    user_pic_bu = val["bu"]
                    break

        if is_admin(db) and not user_pic_code:
            user_pic_code = "ADM"
            user_pic_bu = "CORP"
            user_pic_name = "Admin"

        st.info(f"👤 PIC Login: **{user_pic_name}** | Kode: **{user_pic_code}** | BU: **{user_pic_bu}**")

        with st.form("fptk_manual_form", clear_on_submit=True):
            st.markdown("### Data FPTK")

            col1, col2 = st.columns(2)

            with col1:
                kode_pic = st.text_input("Kode PIC", value=user_pic_code, disabled=True)

                if is_admin(db):
                    kode_unik_manual = st.text_input("Kode Unik", value="", placeholder="Admin: isi manual atau biarkan auto-generate")
                else:
                    kode_unik_manual = st.text_input("Kode Unik", value="", placeholder="Akan di-generate otomatis", disabled=True)

                posisi = st.text_input("Posisi *", value=st.session_state.manual_posisi, key="manual_posisi_input")

                default_direktorat = st.session_state.manual_direktorat
                direktorat = st.selectbox(
                    "Direktorat *",
                    [""] + direktorat_options,
                    index=(direktorat_options.index(default_direktorat) + 1) if default_direktorat in direktorat_options else 0,
                    key="manual_direktorat_input"
                )

                current_posisi = st.session_state.manual_posisi
                current_direktorat = st.session_state.manual_direktorat

                if current_posisi != posisi or current_direktorat != direktorat:
                    st.session_state.manual_posisi = posisi
                    st.session_state.manual_direktorat = direktorat
                    if posisi:
                        position_data = get_position_details_cached(db, posisi, direktorat)
                        if position_data:
                            st.session_state.manual_position_data = position_data
                            st.rerun()
                        else:
                            st.session_state.manual_position_data = {}

                position_data = st.session_state.manual_position_data
                if position_data:
                    st.success(f"✅ Data posisi ditemukan di master: **{position_data.get('position')}**")
                    if position_data.get("business_unit"):
                        st.caption(f"🏢 BU: {position_data.get('business_unit')} | 📍 Lokasi: {position_data.get('location') or '-'}")
                elif posisi:
                    st.warning(f"⚠️ Posisi '{posisi}' belum ada di DB Kode Posisi")
                    st.caption("📌 Data akan otomatis ditambahkan ke master saat FPTK disimpan.")

                default_bu = position_data.get("business_unit", "") if position_data else ""
                default_divisi = position_data.get("division_chris", "") if position_data else ""
                default_department = position_data.get("department_chris", "") if position_data else ""
                default_lokasi_kerja = position_data.get("location", "") if position_data else ""
                default_user_manager = position_data.get("user_manager", "") if position_data else ""
                default_indirect_user = position_data.get("indirect_user", "") if position_data else ""

                business_unit = st.selectbox(
                    "Business Unit *",
                    [""] + bu_options,
                    index=(bu_options.index(default_bu) + 1) if default_bu in bu_options else 0
                )

                divisi = st.text_input("Divisi *", value=default_divisi)
                department = st.text_input("Department *", value=default_department)

            with col2:
                fptk_date = st.date_input("FPTK Date (Real) *", datetime.now())
                level_fptk = st.selectbox("Level FPTK *", level_options, index=0)

                if level_fptk:
                    match = re.search(r'^(\d+)', level_fptk)
                    level_number = int(match.group(1)) if match else 1
                else:
                    level_number = 1
                st.text_input("Level Number (auto)", value=str(level_number), disabled=True)

                alasan = st.selectbox("Alasan Permintaan FPTK *", [""] + alasan_options)
                if alasan:
                    auto_category = determine_category_fptk(alasan)
                    st.text_input("Category FPTK (auto)", value=auto_category, disabled=True)
                else:
                    st.text_input("Category FPTK (auto)", value="", disabled=True)

                pic_recruiter = st.text_input("PIC Recruiter *", value=user_pic_name, disabled=True)
                vacancy = st.number_input("Vacancy *", min_value=1, value=1)
                status = st.selectbox("Status *", status_options)

                sla_days = calculate_sla_days(level_number)
                st.text_input("Jumlah SLA (auto)", value=str(sla_days), disabled=True)

                if fptk_date and sla_days:
                    deadline_sla = calculate_deadline_sla(fptk_date, sla_days)
                    st.text_input("Deadline SLA (auto)", value=deadline_sla.strftime("%d/%m/%Y") if deadline_sla else "-", disabled=True)

                auto_detail_sla = calculate_detail_sla(
                    status=status,
                    deadline_sla=deadline_sla if fptk_date and sla_days else None,
                    offering_date=None
                )
                st.text_input("Detail SLA (auto)", value=auto_detail_sla, disabled=True)

            if status == "Closed":
                offering_date = st.date_input("Offering Date (required untuk Closed)", datetime.now())
            else:
                offering_date = None

            if status == "Cancel":
                cancel_date = st.date_input("FPTK Cancel Date (required untuk Cancel)", datetime.now())
            else:
                cancel_date = None

            st.markdown("---")
            st.markdown("### Data Tambahan")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Nama Kandidat**")
                st.caption("ℹ️ Kalau kandidat sudah ada di DB Sourcing, pilih dari dropdown. Kalau belum, ketik manual.")

                kandidat_kode_unik_preview = kode_unik_manual if kode_unik_manual else generate_kode_unik(user_pic_code, 1, fptk_date) if fptk_date else ""
                nama_kandidat = render_kandidat_picker(db, kandidat_kode_unik_preview, "manual_kandidat", "")

                lokasi_kerja = st.text_input("Lokasi Kerja", value=default_lokasi_kerja)
                lokasi_hr = st.text_input("Lokasi HR")
                user_manager = st.text_input("User (Manager)", value=default_user_manager)
                indirect_user = st.text_input("Indirect User", value=default_indirect_user)
                status_karyawan = st.text_input("Status Karyawan")
            with col2:
                estimasi_join = st.date_input("Estimasi Join", value=None)
                kebutuhan_laptop = st.selectbox("Kebutuhan Laptop", ["", "Ya", "Tidak"])
                lokasi_onboarding = st.selectbox("Lokasi Onboarding", [""] + lokasi_onboarding_options)
                fptk_availability = st.selectbox("FPTK Availability", ["", "Y", "N"])
                remark = st.text_area("Remark")

            st.markdown("---")
            submitted = st.form_submit_button("💾 Simpan FPTK", type="primary")

        if submitted:
            errors = []

            if not posisi: errors.append("Posisi wajib diisi")
            if not business_unit: errors.append("Business Unit wajib diisi")
            if not direktorat: errors.append("Direktorat wajib diisi")
            if not divisi: errors.append("Divisi wajib diisi")
            if not department: errors.append("Department wajib diisi")
            if not level_fptk: errors.append("Level FPTK wajib diisi")
            if not alasan: errors.append("Alasan Permintaan FPTK wajib diisi")
            if vacancy <= 0: errors.append("Vacancy wajib > 0")
            if not status: errors.append("Status wajib diisi")
            if status == "Closed" and not offering_date:
                errors.append("Offering Date wajib diisi jika Status = Closed")
            if status == "Cancel" and not cancel_date:
                errors.append("FPTK Cancel Date wajib diisi jika Status = Cancel")

            kode_angka = generate_kode_angka(db, posisi, kode_pic)

            if not kode_unik_manual and kode_pic and posisi and fptk_date:
                kode_unik = generate_kode_unik(kode_pic, kode_angka, fptk_date)
            elif kode_unik_manual:
                kode_unik = kode_unik_manual
            else:
                kode_unik = ""
                errors.append("Kode Unik tidak bisa di-generate. Pastikan Kode PIC dan Posisi terisi.")

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                should_continue = True
                fptk_date_kode_used = fptk_date
                kode_unik_used = kode_unik
                kode_angka_used = kode_angka

                existing = check_duplicate(db, kode_unik, posisi)

                if existing:
                    st.warning(f"⚠️ Kode Unik '{kode_unik}' dengan Posisi '{posisi}' sudah ada di database!")
                    st.info(f"📋 Data yang sudah ada: Kode Unik: {existing.kode_unik}, FPTK Date Kode: {existing.fptk_date_kode.strftime('%d/%m/%Y') if existing.fptk_date_kode else '-'}")

                    col1, col2 = st.columns(2)
                    with col1:
                        force_insert = st.button("✅ Tetap Masukkan (Auto-increment Kode)", key="force_manual")
                    with col2:
                        cancel_insert = st.button("❌ Batal", key="cancel_manual")

                    if cancel_insert:
                        st.info("❌ Insert dibatalkan.")
                        should_continue = False
                    elif force_insert:
                        with st.spinner("🔄 Memproses dengan Kode Unik baru..."):
                            last_date = get_last_fptk_date_kode(db, posisi, kode_pic)
                            if last_date:
                                new_fptk_date_kode = last_date + timedelta(days=1)
                            else:
                                new_fptk_date_kode = fptk_date

                            new_kode_angka = generate_kode_angka(db, posisi, kode_pic)
                            kode_unik_baru = generate_kode_unik(kode_pic, new_kode_angka, new_fptk_date_kode)

                            suffix_index = 0
                            while check_duplicate(db, kode_unik_baru, posisi):
                                suffix_index += 1
                                new_kode_angka += 1
                                kode_unik_baru = generate_kode_unik(kode_pic, new_kode_angka, new_fptk_date_kode)
                                if suffix_index > 100:
                                    break

                            kode_unik_used = kode_unik_baru
                            kode_angka_used = new_kode_angka
                            fptk_date_kode_used = new_fptk_date_kode
                            st.info(f"✅ Kode Unik baru: **{kode_unik_used}**")
                    else:
                        st.info("⏳ Silakan pilih 'Tetap Masukkan' atau 'Batal'")
                        should_continue = False

                if should_continue:
                    try:
                        if level_number <= 3:
                            sla_days = 30
                        elif level_number == 4:
                            sla_days = 45
                        else:
                            sla_days = 60

                        category_auto = determine_category_fptk(alasan)

                        if db.is_active:
                            db.rollback()

                        if posisi:
                            add_position_to_master(
                                db, posisi=posisi, direktorat=direktorat,
                                business_unit=business_unit, location=lokasi_kerja,
                                division=divisi, department=department,
                                user_manager=user_manager, indirect_user=indirect_user,
                                kode=kode_pic
                            )

                        created_count = 0
                        skipped_count = 0
                        last_kode_unik = ""

                        progress_bar = st.progress(0, text="Menyimpan FPTK...")

                        deadline_sla = fptk_date + timedelta(days=sla_days) if fptk_date else None
                        auto_detail_sla = calculate_detail_sla(
                            status=status, deadline_sla=deadline_sla, offering_date=offering_date
                        )

                        kode_angka_current = kode_angka_used

                        for i in range(vacancy):
                            fptk_date_kode_current = fptk_date_kode_used + timedelta(days=i)

                            if i > 0:
                                kode_angka_current = kode_angka_used + i

                            kode_unik_baru = generate_kode_unik(kode_pic, kode_angka_current, fptk_date_kode_current)

                            existing_check = check_duplicate(db, kode_unik_baru, posisi)
                            suffix_index = 0
                            while existing_check:
                                suffix_index += 1
                                kode_angka_current += 1
                                kode_unik_baru = generate_kode_unik(kode_pic, kode_angka_current, fptk_date_kode_current)
                                existing_check = check_duplicate(db, kode_unik_baru, posisi)
                                if suffix_index > 100:
                                    break

                            existing_check = check_duplicate(db, kode_unik_baru, posisi)
                            if existing_check:
                                skipped_count += 1
                                continue

                            last_kode_unik = kode_unik_baru

                            week_num = fptk_date.isocalendar()[1] if fptk_date else None
                            month_name = fptk_date.strftime("%B") if fptk_date else None
                            kode_bu = kode_pic[:4] if kode_pic else ""

                            filter_kat = ""
                            posisi_lower = posisi.lower()
                            if posisi_lower.startswith('cimory') or posisi_lower.startswith('fresh'):
                                filter_kat = 'CLAP FGDP'
                            elif level_number in [1, 2]:
                                filter_kat = 'Level 1-2'
                            elif level_number == 3:
                                filter_kat = 'Level 3'
                            elif level_number == 4:
                                filter_kat = 'Level 4'

                            new_fptk = FPTK(
                                kode_unik=kode_unik_baru,
                                posisi=posisi,
                                kode_pic=sanitize_value(kode_pic),
                                fptk_date_real=fptk_date,
                                fptk_date_kode=fptk_date_kode_current,
                                kode_angka=sanitize_value(kode_angka_current),
                                business_unit=business_unit,
                                direktorat=direktorat,
                                divisi=sanitize_value(divisi),
                                department=sanitize_value(department),
                                level_fptk=level_fptk,
                                level_number=level_number,
                                alasan_permintaan_fptk=alasan,
                                category_fptk=category_auto,
                                pic_recruiter=pic_recruiter,
                                filter_kategorisasi_fptk=filter_kat,
                                vacancy=1,
                                status=status,
                                offering_date=offering_date,
                                fptk_cancel_date=cancel_date,
                                jumlah_sla=sla_days,
                                deadline_sla=deadline_sla,
                                detail_sla=auto_detail_sla,
                                week_fptk_date=week_num,
                                month_fptk_date=month_name,
                                kode_bu=sanitize_value(kode_bu),
                                nama_kandidat=sanitize_value(nama_kandidat),
                                lokasi_kerja=sanitize_value(lokasi_kerja),
                                lokasi_hr=sanitize_value(lokasi_hr),
                                user_manager=sanitize_value(user_manager),
                                indirect_user=sanitize_value(indirect_user),
                                status_karyawan=sanitize_value(status_karyawan),
                                estimasi_join=estimasi_join,
                                kebutuhan_laptop=sanitize_value(kebutuhan_laptop),
                                lokasi_onboarding=sanitize_value(lokasi_onboarding),
                                fptk_availability=sanitize_value(fptk_availability),
                                remark=sanitize_value(remark),
                                source_user_id=user.id,
                                created_at=datetime.now(),
                                last_compile_action="MANUAL_INPUT"
                            )
                            db.add(new_fptk)
                            created_count += 1

                            progress = (i + 1) / vacancy
                            progress_bar.progress(progress, text=f"Menyimpan FPTK {i+1}/{vacancy}")

                        db.commit()
                        progress_bar.empty()

                        if created_count > 0:
                            st.success(f"✅ {created_count} FPTK berhasil disimpan!")
                            st.success(f"✅ Posisi '{posisi}' telah ditambahkan/diupdate ke DB Kode Posisi.")
                            if skipped_count > 0:
                                st.warning(f"⚠️ {skipped_count} FPTK dilewati (duplikat)")
                            st.info(f"📋 Kode Unik terakhir: **{last_kode_unik}**")
                            st.info(f"📋 Deadline SLA: **{deadline_sla.strftime('%d/%m/%Y') if deadline_sla else '-'}**")
                            st.info(f"📋 Detail SLA: **{auto_detail_sla}**")
                            st.balloons()
                            st.cache_data.clear()
                            st.session_state.manual_posisi = ""
                            st.session_state.manual_direktorat = ""
                            st.session_state.manual_position_data = {}
                            st.rerun()
                        else:
                            st.warning("⚠️ Tidak ada FPTK yang berhasil disimpan")

                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        db.rollback()

    with tab3:
        st.subheader("📧 Paste Informasi FPTK dari HR Portal")
        st.caption("Paste isi email permintaan FPTK. Sistem akan otomatis mengekstrak data.")

        if "parsed_email_data" not in st.session_state:
            st.session_state.parsed_email_data = {}

        email_body = st.text_area("Paste Informasi FPTK dari HR Portal di sini", height=200, placeholder="Copy paste isi email permintaan FPTK...", key="email_body_input")

        col1, col2 = st.columns([1, 5])
        with col1:
            process_email = st.button("🔍 Proses Email", type="primary")

        parsed_data = st.session_state.parsed_email_data.copy()

        if process_email and email_body:
            with st.spinner("Memproses email..."):
                parsed_data = parse_email_body(email_body, bu_options, alasan_options, category_options, direktorat_options)
                st.session_state.parsed_email_data = parsed_data
                if parsed_data.get("posisi"):
                    st.success("✅ Email berhasil diparse! Data sudah terisi di form.")
                    st.rerun()
                else:
                    st.warning("⚠️ Tidak ada data yang terdeteksi dari email.")

        user_pic_name = user.pic_recruiter or user.display_name or user.username
        user_pic_code = user.kode_pic or ""
        user_pic_bu = user.business_unit or ""

        st.info(f"👤 PIC Login: **{user_pic_name}** | Kode: **{user_pic_code}** | BU: **{user_pic_bu}**")

        if not parsed_data.get("pic_recruiter"):
            pic_mapping = get_pic_mapping()
            for key, val in pic_mapping.items():
                if val["name"].lower() == user_pic_name.lower():
                    user_pic_code = val["code"]
                    break
            if not user_pic_code:
                for key, val in pic_mapping.items():
                    if key == user.username.lower():
                        user_pic_code = val["code"]
                        break
            if is_admin(db) and not user_pic_code:
                user_pic_code = "ADM"
                user_pic_name = "Admin"
            parsed_data["pic_recruiter"] = user_pic_name or user.username
            parsed_data["kode_pic"] = user_pic_code or "ADM"

        st.markdown("---")
        st.markdown("### Data FPTK (Hasil Parse / Manual)")

        with st.form("fptk_email_form", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                kode_pic = st.text_input("Kode PIC", value=parsed_data.get("kode_pic", user_pic_code), disabled=True)

                if is_admin(db):
                    kode_unik_email_manual = st.text_input("Kode Unik", value=parsed_data.get("kode_unik", ""), placeholder="Admin: isi manual atau biarkan auto-generate")
                else:
                    kode_unik_email_manual = st.text_input("Kode Unik", value=parsed_data.get("kode_unik", ""), placeholder="Akan di-generate otomatis", disabled=True)

                posisi = st.text_input("Posisi *", value=parsed_data.get("posisi", ""), key="email_posisi_input")

                default_direktorat = parsed_data.get("direktorat", "")
                direktorat = st.selectbox(
                    "Direktorat *",
                    [""] + direktorat_options,
                    index=(direktorat_options.index(default_direktorat) + 1) if default_direktorat in direktorat_options else 0,
                    key="email_direktorat_input"
                )

                if posisi:
                    position_data = get_position_details_cached(db, posisi, direktorat)
                    if position_data:
                        st.success(f"✅ Data posisi ditemukan di master: **{position_data.get('position')}**")
                        if position_data.get("business_unit"):
                            st.caption(f"🏢 BU: {position_data.get('business_unit')} | 📍 Lokasi: {position_data.get('location') or '-'}")
                        default_bu_email = position_data.get("business_unit", "")
                        default_divisi_email = position_data.get("division_chris", "")
                        default_department_email = position_data.get("department_chris", "")
                        default_lokasi_kerja_email = position_data.get("location", "")
                        default_user_manager_email = position_data.get("user_manager", "")
                        default_indirect_user_email = position_data.get("indirect_user", "")
                    else:
                        st.warning(f"⚠️ Posisi '{posisi}' belum ada di DB Kode Posisi")
                        st.caption("📌 Data akan otomatis ditambahkan ke master saat FPTK disimpan.")
                        default_bu_email = parsed_data.get("business_unit", "")
                        default_divisi_email = parsed_data.get("divisi", "")
                        default_department_email = parsed_data.get("department", "")
                        default_lokasi_kerja_email = parsed_data.get("lokasi_kerja", "")
                        default_user_manager_email = ""
                        default_indirect_user_email = ""
                else:
                    default_bu_email = parsed_data.get("business_unit", "")
                    default_divisi_email = parsed_data.get("divisi", "")
                    default_department_email = parsed_data.get("department", "")
                    default_lokasi_kerja_email = parsed_data.get("lokasi_kerja", "")
                    default_user_manager_email = ""
                    default_indirect_user_email = ""

                business_unit = st.selectbox(
                    "Business Unit *",
                    [""] + bu_options,
                    index=(bu_options.index(default_bu_email) + 1) if default_bu_email in bu_options else 0
                )

                divisi = st.text_input("Divisi *", value=default_divisi_email)
                department = st.text_input("Department *", value=default_department_email)

            with col2:
                fptk_date = st.date_input("FPTK Date (Real) *", parsed_data.get("fptk_date", datetime.now()))
                level_fptk = st.selectbox(
                    "Level FPTK *",
                    level_options,
                    index=level_options.index(parsed_data.get("level_fptk", "1A")) if parsed_data.get("level_fptk", "1A") in level_options else 0
                )

                if level_fptk:
                    match = re.search(r'^(\d+)', level_fptk)
                    level_number = int(match.group(1)) if match else 1
                else:
                    level_number = 1
                st.text_input("Level Number (auto)", value=str(level_number), disabled=True)

                default_alasan = parsed_data.get("alasan", "")
                alasan = st.selectbox(
                    "Alasan Permintaan FPTK *",
                    [""] + alasan_options,
                    index=(alasan_options.index(default_alasan) + 1) if default_alasan in alasan_options else 0
                )

                default_category = parsed_data.get("category", "")
                category = st.selectbox(
                    "Category FPTK *",
                    [""] + category_options,
                    index=(category_options.index(default_category) + 1) if default_category in category_options else 0
                )

                pic_recruiter = st.text_input("PIC Recruiter *", value=parsed_data.get("pic_recruiter", user_pic_name), disabled=True)
                vacancy = st.number_input("Vacancy *", min_value=1, value=parsed_data.get("vacancy", 1))
                status = st.selectbox(
                    "Status *",
                    status_options,
                    index=0 if not parsed_data.get("status") else (status_options.index(parsed_data["status"]) if parsed_data.get("status") in status_options else 0)
                )

                sla_days = calculate_sla_days(level_number)
                st.text_input("Jumlah SLA (auto)", value=str(sla_days), disabled=True)

                if fptk_date and sla_days:
                    deadline_sla = calculate_deadline_sla(fptk_date, sla_days)
                    st.text_input("Deadline SLA (auto)", value=deadline_sla.strftime("%d/%m/%Y") if deadline_sla else "-", disabled=True)

                if status == "Closed":
                    offering_date_temp = datetime.now().date()
                else:
                    offering_date_temp = None

                auto_detail_sla_display = calculate_detail_sla(
                    status=status,
                    deadline_sla=deadline_sla if fptk_date and sla_days else None,
                    offering_date=offering_date_temp
                )
                st.text_input("Detail SLA (auto)", value=auto_detail_sla_display, disabled=True)

            if status == "Closed":
                offering_date = st.date_input("Offering Date (required untuk Closed)", datetime.now())
            else:
                offering_date = None

            if status == "Cancel":
                cancel_date = st.date_input("FPTK Cancel Date (required untuk Cancel)", datetime.now())
            else:
                cancel_date = None

            st.markdown("---")
            st.markdown("### Data Tambahan")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Nama Kandidat**")
                st.caption("ℹ️ Kalau kandidat sudah ada di DB Sourcing, pilih dari dropdown. Kalau belum, ketik manual.")

                kandidat_kode_unik_preview = kode_unik_email_manual if kode_unik_email_manual else parsed_data.get("kode_unik", "")
                nama_kandidat = render_kandidat_picker(db, kandidat_kode_unik_preview, "email_kandidat", parsed_data.get("nama_kandidat", ""))

                lokasi_kerja = st.text_input("Lokasi Kerja", value=parsed_data.get("lokasi_kerja", default_lokasi_kerja_email))
                lokasi_hr = st.text_input("Lokasi HR", value=parsed_data.get("lokasi_hr", ""))
                user_manager = st.text_input("User (Manager)", value=parsed_data.get("user_manager", default_user_manager_email))
                indirect_user = st.text_input("Indirect User", value=parsed_data.get("indirect_user", default_indirect_user_email))
                status_karyawan = st.text_input("Status Karyawan", value=parsed_data.get("status_karyawan", ""))
            with col2:
                estimasi_join = st.date_input("Estimasi Join", value=None)
                kebutuhan_laptop = st.selectbox("Kebutuhan Laptop", ["", "Ya", "Tidak"])
                lokasi_onboarding = st.selectbox("Lokasi Onboarding", [""] + lokasi_onboarding_options)
                fptk_availability = st.selectbox("FPTK Availability", ["", "Y", "N"])
                remark = st.text_area("Remark", value=parsed_data.get("remark", ""))

            st.markdown("---")
            submitted = st.form_submit_button("💾 Simpan FPTK", type="primary")

        if submitted:
            errors = []

            if not posisi: errors.append("Posisi wajib diisi")
            if not business_unit: errors.append("Business Unit wajib diisi")
            if not direktorat: errors.append("Direktorat wajib diisi")
            if not divisi: errors.append("Divisi wajib diisi")
            if not department: errors.append("Department wajib diisi")
            if not level_fptk: errors.append("Level FPTK wajib diisi")
            if not alasan: errors.append("Alasan Permintaan FPTK wajib diisi")
            if not category: errors.append("Category FPTK wajib diisi")
            if vacancy <= 0: errors.append("Vacancy wajib > 0")
            if not status: errors.append("Status wajib diisi")
            if status == "Closed" and not offering_date:
                errors.append("Offering Date wajib diisi jika Status = Closed")
            if status == "Cancel" and not cancel_date:
                errors.append("FPTK Cancel Date wajib diisi jika Status = Cancel")

            kode_angka = generate_kode_angka(db, posisi, kode_pic)

            if not kode_unik_email_manual and kode_pic and posisi and fptk_date:
                kode_unik = generate_kode_unik(kode_pic, kode_angka, fptk_date)
            elif kode_unik_email_manual:
                kode_unik = kode_unik_email_manual
            else:
                kode_unik = ""
                errors.append("Kode Unik tidak bisa di-generate. Pastikan Kode PIC dan Posisi terisi.")

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                should_continue = True
                fptk_date_kode_used = fptk_date
                kode_unik_used = kode_unik
                kode_angka_used = kode_angka

                existing = check_duplicate(db, kode_unik, posisi)

                if existing:
                    st.warning(f"⚠️ Kode Unik '{kode_unik}' dengan Posisi '{posisi}' sudah ada di database!")
                    st.info(f"📋 Data yang sudah ada: Kode Unik: {existing.kode_unik}, FPTK Date Kode: {existing.fptk_date_kode.strftime('%d/%m/%Y') if existing.fptk_date_kode else '-'}")

                    col1, col2 = st.columns(2)
                    with col1:
                        force_insert = st.button("✅ Tetap Masukkan (Auto-increment Kode)", key="force_email")
                    with col2:
                        cancel_insert = st.button("❌ Batal", key="cancel_email")

                    if cancel_insert:
                        st.info("❌ Insert dibatalkan.")
                        should_continue = False
                    elif force_insert:
                        with st.spinner("🔄 Memproses dengan Kode Unik baru..."):
                            last_date = get_last_fptk_date_kode(db, posisi, kode_pic)
                            if last_date:
                                new_fptk_date_kode = last_date + timedelta(days=1)
                            else:
                                new_fptk_date_kode = fptk_date

                            new_kode_angka = generate_kode_angka(db, posisi, kode_pic)
                            kode_unik_baru = generate_kode_unik(kode_pic, new_kode_angka, new_fptk_date_kode)

                            suffix_index = 0
                            while check_duplicate(db, kode_unik_baru, posisi):
                                suffix_index += 1
                                new_kode_angka += 1
                                kode_unik_baru = generate_kode_unik(kode_pic, new_kode_angka, new_fptk_date_kode)
                                if suffix_index > 100:
                                    break

                            kode_unik_used = kode_unik_baru
                            kode_angka_used = new_kode_angka
                            fptk_date_kode_used = new_fptk_date_kode
                            st.info(f"✅ Kode Unik baru: **{kode_unik_used}**")
                    else:
                        st.info("⏳ Silakan pilih 'Tetap Masukkan' atau 'Batal'")
                        should_continue = False

                if should_continue:
                    try:
                        if level_number <= 3: sla_days = 30
                        elif level_number == 4: sla_days = 45
                        else: sla_days = 60

                        deadline_sla = fptk_date + timedelta(days=sla_days) if fptk_date else None
                        week_num = fptk_date.isocalendar()[1] if fptk_date else None
                        month_name = fptk_date.strftime("%B") if fptk_date else None
                        kode_bu = kode_pic[:4] if kode_pic else ""

                        filter_kat = ""
                        posisi_lower = posisi.lower()
                        if posisi_lower.startswith('cimory') or posisi_lower.startswith('fresh'):
                            filter_kat = 'CLAP FGDP'
                        elif level_number in [1, 2]:
                            filter_kat = 'Level 1-2'
                        elif level_number == 3:
                            filter_kat = 'Level 3'
                        elif level_number == 4:
                            filter_kat = 'Level 4'

                        auto_detail_sla = calculate_detail_sla(
                            status=status, deadline_sla=deadline_sla, offering_date=offering_date
                        )

                        if db.is_active:
                            db.rollback()

                        if posisi:
                            add_position_to_master(
                                db, posisi=posisi, direktorat=direktorat,
                                business_unit=business_unit, location=lokasi_kerja,
                                division=divisi, department=department,
                                user_manager=user_manager, indirect_user=indirect_user,
                                kode=kode_pic
                            )

                        new_fptk = FPTK(
                            kode_unik=kode_unik_used,
                            posisi=posisi,
                            kode_pic=sanitize_value(kode_pic),
                            fptk_date_real=fptk_date,
                            fptk_date_kode=fptk_date_kode_used,
                            kode_angka=sanitize_value(kode_angka_used),
                            business_unit=business_unit,
                            direktorat=direktorat,
                            divisi=sanitize_value(divisi),
                            department=sanitize_value(department),
                            level_fptk=level_fptk,
                            level_number=level_number,
                            alasan_permintaan_fptk=alasan,
                            category_fptk=category,
                            pic_recruiter=pic_recruiter,
                            filter_kategorisasi_fptk=filter_kat,
                            vacancy=vacancy,
                            status=status,
                            offering_date=offering_date,
                            fptk_cancel_date=cancel_date,
                            jumlah_sla=sla_days,
                            deadline_sla=deadline_sla,
                            detail_sla=auto_detail_sla,
                            week_fptk_date=week_num,
                            month_fptk_date=month_name,
                            kode_bu=sanitize_value(kode_bu),
                            nama_kandidat=sanitize_value(nama_kandidat),
                            lokasi_kerja=sanitize_value(lokasi_kerja),
                            lokasi_hr=sanitize_value(lokasi_hr),
                            user_manager=sanitize_value(user_manager),
                            indirect_user=sanitize_value(indirect_user),
                            status_karyawan=sanitize_value(status_karyawan),
                            estimasi_join=estimasi_join,
                            kebutuhan_laptop=sanitize_value(kebutuhan_laptop),
                            lokasi_onboarding=sanitize_value(lokasi_onboarding),
                            fptk_availability=sanitize_value(fptk_availability),
                            remark=sanitize_value(remark),
                            source_user_id=user.id,
                            created_at=datetime.now(),
                            last_compile_action="EMAIL_PARSE"
                        )
                        db.add(new_fptk)
                        db.commit()

                        st.session_state.parsed_email_data = {}

                        st.success(f"✅ FPTK berhasil disimpan dari email!")
                        st.success(f"✅ Posisi '{posisi}' telah ditambahkan/diupdate ke DB Kode Posisi.")
                        st.info(f"📋 Kode Unik: **{kode_unik_used}**")
                        st.info(f"📋 Kode Angka: **{kode_angka_used}**")
                        st.info(f"📋 Deadline SLA: **{deadline_sla.strftime('%d/%m/%Y') if deadline_sla else '-'}**")
                        st.info(f"📋 Detail SLA: **{auto_detail_sla}**")
                        st.balloons()
                        st.cache_data.clear()
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        db.rollback()


def parse_email_body(body: str, bu_options: list = None, alasan_options: list = None,
                     category_options: list = None, direktorat_options: list = None) -> dict:
    result = {
        "posisi": "", "alasan": "", "business_unit": "", "divisi": "",
        "department": "", "level_fptk": "1A", "level_number": 1,
        "lokasi_kerja": "", "lokasi_hr": "", "status_karyawan": "",
        "vacancy": 1, "pic_email": "", "pic_recruiter": "",
        "kode_pic": "", "kode_bu": "", "category": "",
        "direktorat": "", "nama_kandidat": "", "user_manager": "",
        "indirect_user": "", "fptk_date": datetime.now(),
        "kode_unik": "", "remark": ""
    }

    if not body:
        return result

    pairs = extract_label_value_pairs(body)

    def find_in_pairs(keys):
        for k in keys:
            for pair_key, pair_val in pairs.items():
                if k.lower() in pair_key.lower():
                    return pair_val
        return ""

    result["posisi"] = find_in_pairs([
        "nama jabatan yang dicari", "jabatan yang dicari", "nama jabatan",
        "posisi", "position"
    ])

    result["alasan"] = find_in_pairs([
        "alasan permintaan fptk", "alasan fptk", "alasan"
    ])

    result["business_unit"] = find_in_pairs([
        "pt/business unit", "pt / business unit", "business unit", "bu"
    ])

    result["divisi"] = find_in_pairs(["divisi", "division"])
    result["department"] = find_in_pairs(["departemen", "department", "dept"])

    level_raw = find_in_pairs(["level posisi", "level fptk", "level"])
    if level_raw:
        match = re.match(r'^(\d)\s*([A-C])', str(level_raw).strip().upper())
        if match:
            result["level_number"] = int(match.group(1))
            result["level_fptk"] = f"{match.group(1)}{match.group(2)}"
        else:
            match = re.search(r'(\d)', str(level_raw))
            if match:
                level_num = int(match.group(1))
                if 1 <= level_num <= 5:
                    result["level_number"] = level_num
                    result["level_fptk"] = f"{level_num}A"

    result["lokasi_kerja"] = find_in_pairs(["lokasi kerja", "lokasi", "penempatan"])
    result["lokasi_hr"] = find_in_pairs(["lokasi hr"])
    result["status_karyawan"] = find_in_pairs(["status karyawan"])

    vacancy_raw = find_in_pairs(["jumlah posisi yang dicari", "jumlah posisi", "vacancy"])
    result["vacancy"] = safe_int(vacancy_raw) or 1

    result["pic_email"] = find_in_pairs([
        "email pic rekruter", "pic rekruter", "email pic recruiter"
    ])

    result["nama_kandidat"] = find_in_pairs(["nama kandidat"])
    result["remark"] = find_in_pairs(["remark", "catatan", "notes"])

    pic_mapping = get_pic_mapping()
    pic_found = False

    if result["pic_email"]:
        email_lower = result["pic_email"].lower()
        email_prefix = email_lower.split('@')[0]
        email_parts = re.split(r'[._\-]', email_prefix)

        for part in reversed(email_parts):
            for key, value in pic_mapping.items():
                if key == part:
                    result["pic_recruiter"] = value["name"]
                    result["kode_pic"] = value["code"]
                    result["kode_bu"] = value["bu"]
                    pic_found = True
                    break
            if pic_found:
                break

        if not pic_found:
            for key, value in pic_mapping.items():
                if key in email_lower:
                    result["pic_recruiter"] = value["name"]
                    result["kode_pic"] = value["code"]
                    result["kode_bu"] = value["bu"]
                    pic_found = True
                    break

    if not pic_found:
        body_lower = body.lower()
        for key, value in pic_mapping.items():
            if key in body_lower:
                result["pic_recruiter"] = value["name"]
                result["kode_pic"] = value["code"]
                result["kode_bu"] = value["bu"]
                pic_found = True
                break

    alasan_lower = result["alasan"].lower()
    if any(k in alasan_lower for k in ["keluar", "mutasi", "promosi", "replace"]):
        result["category"] = "REPLACEMENT"
    elif any(k in alasan_lower for k in ["penambahan", "jabatan baru", "new"]):
        result["category"] = "NEW"
    else:
        result["category"] = "REPLACEMENT"

    bu_mapping = get_bu_mapping()
    bu_lower = result["business_unit"].lower()
    for key, value in bu_mapping.items():
        if key.lower() in bu_lower or value["nama"].lower() in bu_lower:
            result["business_unit"] = value["nama"]
            result["kode_bu"] = key
            break

    if not result["kode_bu"] and result["kode_pic"]:
        for key, value in pic_mapping.items():
            if value["code"] == result["kode_pic"]:
                result["kode_bu"] = value["bu"]
                break

    if result["kode_bu"]:
        bu_map = {
            "CORP": "Corporate",
            "MP": "Commercial MP",
            "CMD": "Commercial CMD",
            "JESS": "Commercial JESS",
            "MS": "Commercial MS"
        }
        result["direktorat"] = bu_map.get(result["kode_bu"], "")

    return result
