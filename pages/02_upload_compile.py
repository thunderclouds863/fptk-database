import streamlit as st
import pandas as pd
import re
import hashlib  
from datetime import datetime, timedelta
from core.database import get_db
from core.models import FPTK, MasterDropdown, User, UploadStatus, UploadLog, UploadTemplate
from core.auth import get_current_user, is_admin, hash_file, sanitize_filename
from core.upload_cycle import get_current_cycle, mark_user_uploading, mark_user_done
from core.validator import validate_fptk_file, validate_db_sourcing_file, validate_db_kode_posisi_file
from core.compiler import compile_fptk, compile_db_sourcing, compile_db_kode_posisi
from core.utils import (
    normalize_key, safe_int, safe_float, safe_string, safe_boolean_char, safe_date, parse_date_dmy,
    calculate_sla_days,
    calculate_deadline_sla,
    calculate_detail_sla,
    get_sla_option_list,
    calculate_filter_kategorisasi
)
from core.utils import determine_category_fptk
from core.template_manager import (
    save_template,
    get_active_template,
    get_template_bytes
)
import time

# ============================================================
# CONSTANTS
# ============================================================

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
    "pauline": {"name": "Pauline", "bu": "MP", "code": "MPPau"},
    "ratih": {"name": "Ratih", "bu": "MP", "code": "MPRat"},
    "achmad": {"name": "Achmad", "bu": "MP", "code": "MPAch"},
    "kasanah": {"name": "Kasanah", "bu": "MP", "code": "MPKas"},
    "alma": {"name": "Alma", "bu": "MP", "code": "MPAlm"},
    "salwa": {"name": "Salwa", "bu": "CMD", "code": "CMDSal"},
    "elsi": {"name": "Elsi", "bu": "CMD", "code": "CMDEls"},
    "wahyu": {"name": "Wahyu", "bu": "CMD", "code": "CMDWah"},
    "riska": {"name": "Riska", "bu": "JESS", "code": "JESSRis"},
    "leo": {"name": "Leo", "bu": "MS", "code": "MSLeo"},
}

PIC_NAMES_BY_BU = {
    "CORP": ["Adista", "Brittney", "Eli", "Fiqra", "Karin", "Kenthansen", "Kevin", "Marta", "Omega", "Salsa", "Valendra", "Victor", "Yeremia", "Zwei"],
    "MP": ["Pauline", "Ratih", "Achmad", "Kasanah", "Alma"],
    "CMD": ["Salwa", "Elsi", "Wahyu"],
    "JESS": ["Riska"],
    "MS": ["Leo"],
}

ALL_PIC_NAMES = sorted([name for names in PIC_NAMES_BY_BU.values() for name in names])
ALL_BU_CODES = sorted(BU_CODE_MAPPING.keys())

LEVEL_OPTIONS = []
for num in range(1, 6):
    for letter in ['A', 'B']:
        LEVEL_OPTIONS.append(f"{num}{letter}")


# ============================================================
# 🔥🔥🔥 FUNGSI DETAIL SLA OTOMATIS 🔥🔥🔥
# ============================================================

def calculate_detail_sla_auto(status, fptk_date_real, deadline_sla, offering_date, today=None):
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


def sanitize_value(value):
    if value == "" or value == " ":
        return None
    return value


# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_data(ttl=3600)
def get_master_options(_db):
    try:
        master_records = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        
        bu_options = sorted(set([m.bu for m in master_records if m.bu]))
        alasan_options = sorted(set([m.alasan for m in master_records if m.alasan]))
        category_options = sorted(set([m.category_fptk for m in master_records if m.category_fptk]))
        filter_options = sorted(set([m.filter_fptk for m in master_records if m.filter_fptk]))
        status_options = ["OP", "Closed", "Cancel"]
        lokasi_onboarding_options = sorted(set([m.lokasi_onboarding for m in master_records if m.lokasi_onboarding]))
        detail_sla_options = sorted(set([m.detail_sla for m in master_records if m.detail_sla]))
        keterangan_0_options = sorted(set([m.keterangan_0 for m in master_records if m.keterangan_0]))
        keterangan_1_options = sorted(set([m.keterangan_1 for m in master_records if m.keterangan_1]))
        keterangan_cancel_options = sorted(set([m.keterangan_cancel for m in master_records if m.keterangan_cancel]))
        direktorat_options = sorted(set([m.nama_direktorat for m in master_records if m.nama_direktorat]))
        model_options = sorted(set([m.model for m in master_records if m.model]))
        sumber_options = sorted(set([m.sumber_sourcing for m in master_records if m.sumber_sourcing]))
        jenjang_options = sorted(set([m.jenjang_pendidikan for m in master_records if m.jenjang_pendidikan]))
        univ_options = sorted(set([m.nama_universitas_top10 for m in master_records if m.nama_universitas_top10]))
        jurusan_options = sorted(set([m.jurusan for m in master_records if m.jurusan]))
        univ_tier_options = sorted(set([m.university_tier for m in master_records if m.university_tier]))
        ipk_tier_options = sorted(set([m.ipk_tier for m in master_records if m.ipk_tier]))
        kode_pic_options = sorted(set([m.kode_pic for m in master_records if m.kode_pic]))
        
        return {
            'bu_options': bu_options,
            'alasan_options': alasan_options,
            'category_options': category_options,
            'filter_options': filter_options,
            'status_options': status_options,
            'lokasi_onboarding_options': lokasi_onboarding_options,
            'detail_sla_options': detail_sla_options,
            'keterangan_0_options': keterangan_0_options,
            'keterangan_1_options': keterangan_1_options,
            'keterangan_cancel_options': keterangan_cancel_options,
            'direktorat_options': direktorat_options,
            'model_options': model_options,
            'sumber_options': sumber_options,
            'jenjang_options': jenjang_options,
            'univ_options': univ_options,
            'jurusan_options': jurusan_options,
            'univ_tier_options': univ_tier_options,
            'ipk_tier_options': ipk_tier_options,
            'kode_pic_options': kode_pic_options
        }
    except Exception as e:
        return {
            'bu_options': [],
            'alasan_options': [],
            'category_options': [],
            'filter_options': [],
            'status_options': ["OP", "Closed", "Cancel"],
            'lokasi_onboarding_options': [],
            'detail_sla_options': [],
            'keterangan_0_options': [],
            'keterangan_1_options': [],
            'keterangan_cancel_options': [],
            'direktorat_options': [],
            'model_options': [],
            'sumber_options': [],
            'jenjang_options': [],
            'univ_options': [],
            'jurusan_options': [],
            'univ_tier_options': [],
            'ipk_tier_options': [],
            'kode_pic_options': []
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


@st.cache_data(ttl=3600)
def get_pic_names_by_bu():
    return PIC_NAMES_BY_BU.copy()


@st.cache_data(ttl=3600)
def get_all_pic_names():
    return ALL_PIC_NAMES.copy()


@st.cache_data(ttl=3600)
def get_all_bu_codes():
    return ALL_BU_CODES.copy()


# ============================================================
# 🔥🔥🔥 FUNGSI GENERATE KODE UNIK & KODE ANGKA 🔥🔥🔥
# ============================================================

def generate_kode_angka(db, posisi, kode_pic):
    """
    Generate Kode Angka dengan auto-increment dari angka terakhir
    Format: [KodePIC][AngkaAutoIncrement]
    Contoh: ADM001, ADM002, dst.
    """
    if not posisi or not kode_pic:
        return f"{kode_pic}001" if kode_pic else "ADM001"
    
    # Cari angka terakhir untuk posisi dan kode_pic yang sama
    last_entry = db.query(FPTK).filter(
        FPTK.posisi == posisi,
        FPTK.kode_pic == kode_pic
    ).order_by(FPTK.id.desc()).first()
    
    if last_entry and last_entry.kode_angka:
        # Ambil angka dari kode_angka (format: [KodePIC][Angka])
        last_angka = re.sub(r'[^0-9]', '', last_entry.kode_angka)
        if last_angka and last_angka.isdigit():
            new_number = int(last_angka) + 1
            return f"{kode_pic}{str(new_number).zfill(3)}"
    
    # Jika belum ada, mulai dari 001
    return f"{kode_pic}001"


def generate_kode_unik(kode_pic, posisi, fptk_date):
    """Generate Kode Unik dari Kode PIC + Posisi + Tanggal"""
    if not kode_pic or not posisi or not fptk_date:
        if kode_pic and fptk_date:
            date_code = fptk_date.strftime("%d%m%y")
            return f"{kode_pic}XXXX{date_code}"
        return ""
    
    date_code = fptk_date.strftime("%d%m%y")
    posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper()
    if not posisi_code:
        posisi_code = "XXXX"
    return f"{kode_pic}{posisi_code}{date_code}"


def get_last_fptk_date_kode(db, posisi, kode_pic):
    """Mendapatkan fptk_date_kode terakhir untuk posisi dan kode_pic"""
    last_entry = db.query(FPTK).filter(
        FPTK.posisi == posisi,
        FPTK.kode_pic == kode_pic
    ).order_by(FPTK.fptk_date_kode.desc()).first()
    
    if last_entry and last_entry.fptk_date_kode:
        return last_entry.fptk_date_kode
    return None


def check_duplicate(db, kode_unik, posisi):
    """Cek apakah kombinasi kode_unik + posisi sudah ada"""
    if not kode_unik:
        return None
    return db.query(FPTK).filter(
        FPTK.kode_unik == kode_unik,
        FPTK.posisi == posisi
    ).first()


def compile_with_progress(file, df, _db, user, cycle, is_sto, progress_placeholder, status_placeholder):
    """Compile file dengan progress bar"""
    status_placeholder.info("📋 Step 1/5: Validasi struktur file...")
    progress_placeholder.progress(10, text="Validasi file...")
    time.sleep(0.3)
    
    status_placeholder.info("📊 Step 2/5: Compile FPTK...")
    progress_placeholder.progress(30, text="Compile FPTK...")
    time.sleep(0.3)
    
    file_bytes = file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    if _db.is_active:
        _db.rollback()
    
    result = compile_fptk(
        _db, df, user.id, cycle.id,
        sanitize_filename(file.name), file_bytes, is_sto
    )
    
    if not result["success"]:
        progress_placeholder.progress(100, text="❌ Gagal!")
        status_placeholder.error(f"❌ Compile FPTK gagal: {result.get('errors', ['Unknown error'])}")
        return False, None
    
    progress_placeholder.progress(50, text="✅ FPTK selesai")
    status_placeholder.info("📊 Step 3/5: Compile DB Sourcing...")
    time.sleep(0.3)
    
    try:
        with pd.ExcelFile(file) as xls:
            if "DB Sourcing" in xls.sheet_names:
                sourcing_df = pd.read_excel(file, sheet_name="DB Sourcing", header=0)
                if sourcing_df is not None and not sourcing_df.empty:
                    progress_placeholder.progress(60, text="Compile DB Sourcing...")
                    sourcing_result = compile_db_sourcing(
                        db=_db,
                        df=sourcing_df,
                        user_id=user.id,
                        cycle_id=cycle.id,
                        file_name=sanitize_filename(file.name),
                        file_hash=file_hash
                    )
                    if sourcing_result["success"]:
                        st.success(f"✅ DB Sourcing: {sourcing_result.get('imported', 0)} rows imported")
                    else:
                        st.warning(f"⚠️ DB Sourcing: {len(sourcing_result.get('errors', []))} errors")
    except Exception as e:
        st.warning(f"⚠️ DB Sourcing error: {str(e)}")
    
    progress_placeholder.progress(75, text="✅ DB Sourcing selesai")
    status_placeholder.info("📊 Step 4/5: Compile DB Kode Posisi...")
    time.sleep(0.3)
    
    try:
        with pd.ExcelFile(file) as xls:
            if "DB Kode Posisi" in xls.sheet_names:
                dbk_df = pd.read_excel(file, sheet_name="DB Kode Posisi", header=0)
                if dbk_df is not None and not dbk_df.empty:
                    progress_placeholder.progress(85, text="Compile DB Kode Posisi...")
                    if _db.is_active:
                        _db.rollback()
                    dbk_result = compile_db_kode_posisi(
                        db=_db,
                        df=dbk_df,
                        user_id=user.id,
                        cycle_id=cycle.id,
                        file_name=sanitize_filename(file.name),
                        file_hash=file_hash
                    )
                    if dbk_result["success"]:
                        st.success(f"✅ DB Kode Posisi: {dbk_result.get('imported', 0)} rows")
                    else:
                        st.warning(f"⚠️ DB Kode Posisi: {len(dbk_result.get('errors', []))} errors")
    except Exception as e:
        st.warning(f"⚠️ DB Kode Posisi error: {str(e)}")
    
    progress_placeholder.progress(95, text="Finalisasi...")
    status_placeholder.info("📊 Step 5/5: Menyimpan status...")
    time.sleep(0.3)
    
    mark_user_uploading(_db, user.id, cycle.id)
    
    progress_placeholder.progress(100, text="✅ Selesai!")
    status_placeholder.success(f"✅ {file.name}: Selesai! FPTK Imported {result.get('imported',0)}, Updated {result.get('updated',0)}")
    time.sleep(0.5)
    
    return True, result


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show_upload_compile():
    st.title("📤 Upload & Compile FPTK")
    st.markdown("Upload file Excel recruiter ATAU input FPTK secara manual ATAU paste email body.")
    
    db = next(get_db())
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

    # ============================================================
    # ADMIN TEMPLATE MANAGEMENT
    # ============================================================
    
    if is_admin(db):
        st.markdown("---")
        st.subheader("⚙️ Admin - Template Excel")
    
        template_file = st.file_uploader(
            "Upload Template Excel",
            type=["xlsx"],
            key="admin_template_upload"
        )
    
        if template_file:
            if st.button("💾 Simpan Template", key="save_template_btn"):
                save_template(db, template_file, user.id)
                st.cache_data.clear()
                st.success("✅ Template berhasil diperbarui")
                st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["📤 Upload Excel", "📝 Input Manual FPTK", "📧 Paste Email Body"])
    
    # ============================================================
    # TAB 1: UPLOAD EXCEL
    # ============================================================
    
    with tab1:
        cycle = get_current_cycle(db)
        if not cycle:
            st.error("Belum ada Upload Cycle aktif. Hubungi Admin.")
            return
        st.info(f"📋 Upload Cycle: **{cycle.cycle_name}**")
        
        status = db.query(UploadStatus).filter(
            UploadStatus.user_id == user.id,
            UploadStatus.cycle_id == cycle.id
        ).first()
        st.caption(f"Status Anda: **{status.status if status else 'Belum Mulai'}**")
        
        st.markdown("---")
        st.subheader("📁 Upload File Excel")
        
        active_template = get_active_template(db)
        
        if active_template:
            template_bytes = get_template_bytes(active_template)
            st.download_button(
                label="📥 Download Template Excel",
                data=template_bytes,
                file_name=active_template.file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.caption(f"Template aktif versi {active_template.version}")
        else:
            st.warning("⚠️ Template Excel belum tersedia. Hubungi Admin.")
        
        uploaded_files = st.file_uploader(
            "Pilih file Excel (.xlsx, .xlsm)",
            type=["xlsx", "xlsm"],
            accept_multiple_files=True
        )
        is_sto = st.checkbox("☑️ File ini adalah file STO (Tulang Punggung)")
        
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        if st.button("🚀 Compile", type="primary"):
            if not uploaded_files:
                st.warning("Pilih file dulu!")
            else:
                total_files = len(uploaded_files)
                success_count = 0
                error_count = 0
                
                for idx, file in enumerate(uploaded_files):
                    file_num = idx + 1
                    status_placeholder.info(f"📄 Memproses file {file_num}/{total_files}: **{file.name}**")
                    
                    try:
                        df = pd.read_excel(file, sheet_name="FPTK", header=None)
                        header_row = None
                        for i, row in df.iterrows():
                            row_text = " ".join([str(x) for x in row.values if pd.notna(x)])
                            if "Kode Unik" in row_text and "Posisi" in row_text:
                                header_row = i
                                break
                        
                        if header_row is None:
                            st.error(f"❌ {file.name}: Header tidak ditemukan")
                            st.info(f"📌 Pastikan sheet pertama (FPTK) memiliki kolom: Kode Unik, Posisi, Kode PIC, FPTK Date (Real), Business Unit, Direktorat, Level FPTK, Vacancy, Status")
                            error_count += 1
                            continue
                        
                        df.columns = df.iloc[header_row].astype(str).str.strip()
                        df = df.iloc[header_row+1:].reset_index(drop=True)
                        
                        validated, errors = validate_fptk_file(df, db, user.id, is_sto)
                        
                        warnings = [e for e in errors if e.get("warning") == True]
                        real_errors = [e for e in errors if e.get("warning") != True]
                        
                        if warnings:
                            st.warning(f"⚠️ {file.name}: {len(warnings)} warning")
                            with st.expander(f"⚠️ Lihat Warning Detail ({len(warnings)})", expanded=False):
                                for err in warnings:
                                    row = err.get("row", "?")
                                    field = err.get("field", "Unknown")
                                    value = err.get("value", "")
                                    error_msg = err.get("error", "")
                                    st.markdown(f"- **Row {row}** - {field}: `{value}` → {error_msg}")
                        
                        if real_errors:
                            st.error(f"❌ {file.name}: {len([e for e in real_errors if e.get('field') != 'SUMMARY'])} error (file ditolak)")
                            with st.expander(f"❌ Lihat Error Detail ({len(real_errors)})", expanded=True):
                                for err in real_errors:
                                    if err.get("field") == "SUMMARY":
                                        st.warning(f"📌 {err.get('error', '')}")
                                        continue
                                    row = err.get("row", "?")
                                    field = err.get("field", "Unknown")
                                    value = err.get("value", "")
                                    error_msg = err.get("error", "")
                                    expected = err.get("expected", "")
                                    st.markdown(f"- **Row {row}** - {field}: `{value}` → {error_msg} (Expected: {expected})")
                            
                            error_count += 1
                            continue
                        
                        success, result = compile_with_progress(
                            file, df, db, user, cycle, is_sto,
                            progress_placeholder, status_placeholder
                        )
                        
                        if success:
                            success_count += 1
                            st.cache_data.clear()
                        else:
                            error_count += 1
                        
                    except Exception as e:
                        st.error(f"❌ {file.name}: {str(e)}")
                        db.rollback()
                        error_count += 1
                
                progress_placeholder.empty()
                status_placeholder.empty()
                
                st.markdown("---")
                st.markdown("### 📊 Ringkasan Compile")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total File", total_files)
                col2.metric("✅ Berhasil", success_count)
                col3.metric("❌ Gagal", error_count)
                
                if success_count > 0 and error_count == 0:
                    st.success("🎉 Semua file berhasil di-compile!")
                    st.balloons()
                elif success_count > 0:
                    st.warning(f"⚠️ {success_count} file berhasil, {error_count} file gagal")
                else:
                    st.error("❌ Semua file gagal di-compile")
                
                if success_count > 0:
                    if st.button("📌 Saya Selesai Upload", type="primary"):
                        mark_user_done(db, user.id, cycle.id)
                        st.success("Status Anda diupdate ke Done!")
                        st.rerun()
                
                time.sleep(2)
                progress_placeholder.empty()
                status_placeholder.empty()
                    
        st.markdown("---")
        st.subheader("📜 Riwayat Upload")
        
        try:
            if db.is_active:
                db.rollback()
            
            logs = db.query(UploadLog).filter(
                UploadLog.user_id == user.id,
                UploadLog.cycle_id == cycle.id
            ).order_by(UploadLog.uploaded_at.desc()).limit(50).all()
            
            if logs:
                data = [{
                    "Tanggal": l.uploaded_at.strftime("%d/%m/%Y %H:%M") if l.uploaded_at else "-",
                    "File": l.file_name,
                    "Status": l.status,
                    "Records": l.record_count or 0
                } for l in logs]
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.info("📭 Belum ada riwayat upload")
        except Exception as e:
            db.rollback()
            st.warning(f"⚠️ Gagal mengambil riwayat upload: {str(e)}")
            st.info("📭 Silakan upload file terlebih dahulu")
    
    # ============================================================
    # TAB 2: INPUT MANUAL FPTK (DIPERBAIKI)
    # ============================================================
    
    with tab2:
        st.subheader("Input FPTK Manual")
        st.caption("Input satu per satu. PIC otomatis dari user yang login.")
        
        pic_mapping = get_pic_mapping()
        level_options = get_level_options()
        
        user_pic_name = user.pic_recruiter or ""
        user_pic_code = ""
        user_pic_bu = ""
        
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
        
        # 🔥🔥🔥 JIKA USER ADALAH ADMIN DAN KODE_PIC KOSONG, PAKAI "ADM" 🔥🔥🔥
        if is_admin(db) and not user_pic_code:
            user_pic_code = "ADM"
            user_pic_bu = "CORP"
            user_pic_name = "Admin"
        
        st.info(f"👤 PIC Login: **{user_pic_name}** | Kode: **{user_pic_code}** | BU: **{user_pic_bu}**")
        
        with st.form("fptk_manual_form", clear_on_submit=True):
            st.markdown("### Data FPTK")
            
            col1, col2 = st.columns(2)
            
            with col1:
                kode_pic = st.text_input(
                    "Kode PIC",
                    value=user_pic_code,
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                if is_admin(db):
                    kode_unik = st.text_input(
                        "Kode Unik",
                        value="",
                        placeholder="Admin: isi manual atau biarkan auto-generate",
                        help="Admin bisa isi kode unik manual. Kosongkan untuk auto-generate."
                    )
                else:
                    kode_unik = st.text_input(
                        "Kode Unik",
                        value="",
                        placeholder="Akan di-generate otomatis",
                        disabled=True,
                        help="Auto-generate dari Kode PIC + Posisi + Tanggal"
                    )
                
                posisi = st.text_input("Posisi *")
                business_unit = st.selectbox("Business Unit *", [""] + bu_options)
                direktorat = st.selectbox("Direktorat *", [""] + direktorat_options)
                divisi = st.text_input("Divisi *")
                department = st.text_input("Department *")
            
            with col2:
                fptk_date = st.date_input("FPTK Date (Real) *", datetime.now())
                level_fptk = st.selectbox("Level FPTK *", level_options, index=0)
                
                if level_fptk:
                    match = re.search(r'(\d+)', level_fptk)
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
                
                pic_recruiter = st.text_input(
                    "PIC Recruiter *",
                    value=user_pic_name,
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                vacancy = st.number_input("Vacancy *", min_value=1, value=1)
                status = st.selectbox("Status *", status_options)
                
                sla_days = calculate_sla_days(level_number)
                st.text_input("Jumlah SLA (auto)", value=str(sla_days), disabled=True)
                
                if fptk_date and sla_days:
                    deadline_sla = calculate_deadline_sla(fptk_date, sla_days)
                    st.text_input("Deadline SLA (auto)", value=deadline_sla.strftime("%d/%m/%Y") if deadline_sla else "-", disabled=True)
                
                auto_detail_sla = calculate_detail_sla_auto(
                    status=status,
                    fptk_date_real=fptk_date,
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
                nama_kandidat = st.text_input("Nama Kandidat")
                lokasi_kerja = st.text_input("Lokasi Kerja")
                lokasi_hr = st.text_input("Lokasi HR")
                user_manager = st.text_input("User (Manager)")
                indirect_user = st.text_input("Indirect User")
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
            
            # 🔥🔥🔥 GENERATE KODE UNIK 🔥🔥🔥
            if not kode_unik and kode_pic and posisi and fptk_date:
                kode_unik = generate_kode_unik(kode_pic, posisi, fptk_date)
                if not kode_unik:
                    errors.append("Kode Unik tidak bisa di-generate. Pastikan Kode PIC dan Posisi terisi.")
            
            # 🔥🔥🔥 GENERATE KODE ANGKA 🔥🔥🔥
            kode_angka = generate_kode_angka(db, posisi, kode_pic)
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                # 🔥🔥🔥 CEK DUPLIKAT 🔥🔥🔥
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
                            
                            kode_unik_baru = generate_kode_unik(kode_pic, posisi, new_fptk_date_kode)
                            
                            # Ambil posisi_code untuk suffix
                            posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper() if posisi else "XXXX"
                            
                            suffix_index = 0
                            while check_duplicate(db, kode_unik_baru, posisi):
                                suffix_index += 1
                                test_kode = f"{kode_pic}{posisi_code}{new_fptk_date_kode.strftime('%d%m%y')}{chr(65 + suffix_index - 1)}"
                                if not check_duplicate(db, test_kode, posisi):
                                    kode_unik_baru = test_kode
                                    break
                                if suffix_index > 100:
                                    break
                            
                            kode_unik_used = kode_unik_baru
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
                        
                        created_count = 0
                        skipped_count = 0
                        last_kode_unik = ""
                        
                        progress_bar = st.progress(0, text="Menyimpan FPTK...")
                        
                        deadline_sla = fptk_date + timedelta(days=sla_days) if fptk_date else None
                        auto_detail_sla = calculate_detail_sla_auto(
                            status=status,
                            fptk_date_real=fptk_date,
                            deadline_sla=deadline_sla,
                            offering_date=offering_date
                        )
                        
                        kode_angka_base = kode_angka_used
                        posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper() if posisi else "XXXX"
                        
                        for i in range(vacancy):
                            fptk_date_kode_current = fptk_date_kode_used + timedelta(days=i)
                            kode_angka_current = kode_angka_base
                            
                            if i > 0:
                                angka_part = re.sub(r'[^0-9]', '', kode_angka_base)
                                if angka_part and angka_part.isdigit():
                                    new_num = int(angka_part) + i
                                    kode_angka_current = f"{kode_pic}{str(new_num).zfill(3)}"
                            
                            date_code = fptk_date_kode_current.strftime("%d%m%y")
                            kode_unik_baru = f"{kode_pic}{posisi_code}{date_code}"
                            
                            existing_check = check_duplicate(db, kode_unik_baru, posisi)
                            suffix_index = 0
                            while existing_check:
                                suffix_index += 1
                                test_kode = f"{kode_pic}{posisi_code}{date_code}{chr(65 + suffix_index - 1)}"
                                existing_check = check_duplicate(db, test_kode, posisi)
                                if not existing_check:
                                    kode_unik_baru = test_kode
                                    break
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
                            if skipped_count > 0:
                                st.warning(f"⚠️ {skipped_count} FPTK dilewati (duplikat)")
                            st.info(f"📋 Kode Unik terakhir: **{last_kode_unik}**")
                            st.info(f"📋 Deadline SLA: **{deadline_sla.strftime('%d/%m/%Y') if deadline_sla else '-'}**")
                            st.info(f"📋 Detail SLA: **{auto_detail_sla}**")
                            st.balloons()
                            st.cache_data.clear()
                        else:
                            st.warning("⚠️ Tidak ada FPTK yang berhasil disimpan")
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        db.rollback()
    
    # ============================================================
    # TAB 3: PASTE EMAIL BODY (DIPERBAIKI)
    # ============================================================
    
    with tab3:
        st.subheader("📧 Paste Email Body")
        st.caption("Paste isi email permintaan FPTK. Sistem akan otomatis mengekstrak data.")
        
        if "parsed_email_data" not in st.session_state:
            st.session_state.parsed_email_data = {}
        
        email_body = st.text_area(
            "Paste Email Body di sini",
            height=200,
            placeholder="Copy paste isi email permintaan FPTK...",
            key="email_body_input"
        )
        
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
        
        # Default PIC untuk admin
        user_pic_name = user.pic_recruiter or ""
        user_pic_code = ""
        
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
            
            # 🔥🔥🔥 JIKA ADMIN, PAKAI "ADM" 🔥🔥🔥
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
                kode_pic = st.text_input(
                    "Kode PIC",
                    value=parsed_data.get("kode_pic", user_pic_code),
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                if is_admin(db):
                    kode_unik = st.text_input(
                        "Kode Unik",
                        value=parsed_data.get("kode_unik", ""),
                        placeholder="Admin: isi manual atau biarkan auto-generate",
                        help="Admin bisa isi kode unik manual. Kosongkan untuk auto-generate."
                    )
                else:
                    kode_unik = st.text_input(
                        "Kode Unik",
                        value=parsed_data.get("kode_unik", ""),
                        placeholder="Akan di-generate otomatis",
                        disabled=True,
                        help="Auto-generate dari Kode PIC + Posisi + Tanggal"
                    )
                
                posisi = st.text_input("Posisi *", value=parsed_data.get("posisi", ""))
                
                default_bu = parsed_data.get("business_unit", "")
                business_unit = st.selectbox(
                    "Business Unit *",
                    [""] + bu_options,
                    index=(bu_options.index(default_bu) + 1) if default_bu in bu_options else 0
                )
                
                default_direktorat = parsed_data.get("direktorat", "")
                direktorat = st.selectbox(
                    "Direktorat *",
                    [""] + direktorat_options,
                    index=(direktorat_options.index(default_direktorat) + 1) if default_direktorat in direktorat_options else 0
                )
                
                divisi = st.text_input("Divisi *", value=parsed_data.get("divisi", ""))
                department = st.text_input("Department *", value=parsed_data.get("department", ""))
            
            with col2:
                fptk_date = st.date_input(
                    "FPTK Date (Real) *",
                    parsed_data.get("fptk_date", datetime.now())
                )
                
                level_options = get_level_options()
                default_level = parsed_data.get("level_fptk", "1A")
                if default_level not in level_options:
                    default_level = "1A"
                level_fptk = st.selectbox(
                    "Level FPTK *",
                    level_options,
                    index=level_options.index(default_level) if default_level in level_options else 0
                )
                
                if level_fptk:
                    match = re.search(r'(\d+)', level_fptk)
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
                
                pic_recruiter = st.text_input(
                    "PIC Recruiter *",
                    value=parsed_data.get("pic_recruiter", user_pic_name),
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                vacancy = st.number_input(
                    "Vacancy *",
                    min_value=1,
                    value=parsed_data.get("vacancy", 1)
                )
                
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
                
                auto_detail_sla_display = calculate_detail_sla_auto(
                    status=status,
                    fptk_date_real=fptk_date,
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
                nama_kandidat = st.text_input("Nama Kandidat", value=parsed_data.get("nama_kandidat", ""))
                lokasi_kerja = st.text_input("Lokasi Kerja", value=parsed_data.get("lokasi_kerja", ""))
                lokasi_hr = st.text_input("Lokasi HR", value=parsed_data.get("lokasi_hr", ""))
                user_manager = st.text_input("User (Manager)", value=parsed_data.get("user_manager", ""))
                indirect_user = st.text_input("Indirect User", value=parsed_data.get("indirect_user", ""))
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
            
            # 🔥🔥🔥 GENERATE KODE UNIK 🔥🔥🔥
            if not kode_unik and kode_pic and posisi and fptk_date:
                kode_unik = generate_kode_unik(kode_pic, posisi, fptk_date)
                if not kode_unik:
                    errors.append("Kode Unik tidak bisa di-generate. Pastikan Kode PIC dan Posisi terisi.")
            
            # 🔥🔥🔥 GENERATE KODE ANGKA 🔥🔥🔥
            kode_angka = generate_kode_angka(db, posisi, kode_pic)
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                # 🔥🔥🔥 CEK DUPLIKAT 🔥🔥🔥
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
                            
                            kode_unik_baru = generate_kode_unik(kode_pic, posisi, new_fptk_date_kode)
                            
                            posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper() if posisi else "XXXX"
                            
                            suffix_index = 0
                            while check_duplicate(db, kode_unik_baru, posisi):
                                suffix_index += 1
                                test_kode = f"{kode_pic}{posisi_code}{new_fptk_date_kode.strftime('%d%m%y')}{chr(65 + suffix_index - 1)}"
                                if not check_duplicate(db, test_kode, posisi):
                                    kode_unik_baru = test_kode
                                    break
                                if suffix_index > 100:
                                    break
                            
                            kode_unik_used = kode_unik_baru
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
                        
                        auto_detail_sla = calculate_detail_sla_auto(
                            status=status,
                            fptk_date_real=fptk_date,
                            deadline_sla=deadline_sla,
                            offering_date=offering_date
                        )
                        
                        if db.is_active:
                            db.rollback()
                        
                        posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper() if posisi else "XXXX"
                        kode_angka_base = kode_angka_used
                        
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


# ============================================================
# FUNGSI PARSE EMAIL
# ============================================================

def parse_email_body(body: str, bu_options: list, alasan_options: list, category_options: list, direktorat_options: list) -> dict:
    result = {
        "posisi": "",
        "alasan": "",
        "business_unit": "",
        "divisi": "",
        "department": "",
        "level_fptk": "1A",
        "level_number": 1,
        "lokasi_kerja": "",
        "lokasi_hr": "",
        "status_karyawan": "",
        "vacancy": 1,
        "pic_email": "",
        "pic_recruiter": "",
        "kode_pic": "",
        "kode_bu": "",
        "category": "",
        "direktorat": "",
        "nama_kandidat": "",
        "user_manager": "",
        "indirect_user": "",
        "fptk_date": datetime.now(),
        "kode_unik": "",
        "remark": ""
    }
    
    if not body:
        return result
    
    text = body.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    
    def find_field(field_names):
        for i, line in enumerate(lines):
            clean_line = line.strip()
            for name in field_names:
                if name.lower() in clean_line.lower():
                    if ':' in clean_line:
                        value = clean_line.split(':', 1)[1].strip()
                        if value:
                            return value
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not any(k in next_line.lower() for k in ["nama", "posisi", "alasan", "email"]):
                            return next_line
        return ""
    
    result["posisi"] = find_field(["Nama Jabatan Yang Dicari", "Jabatan Yang Dicari", "Position", "Posisi"])
    result["alasan"] = find_field(["Alasan Permintaan FPTK", "Alasan FPTK"])
    result["business_unit"] = find_field(["PT/Business Unit", "Business Unit", "PT / Business Unit"])
    result["divisi"] = find_field(["Divisi"])
    result["department"] = find_field(["Department", "Departemen"])
    result["level_fptk"] = find_field(["Level Posisi", "Level FPTK", "Level"])
    result["lokasi_kerja"] = find_field(["Lokasi Kerja"])
    result["lokasi_hr"] = find_field(["Lokasi HR", "HR Location"])
    result["status_karyawan"] = find_field(["Status Karyawan"])
    result["vacancy"] = safe_int(find_field(["Jumlah Posisi Yang Dicari", "Jumlah Posisi", "Vacancy"])) or 1
    result["pic_email"] = find_field(["Email PIC Rekruter", "PIC Rekruter", "Email PIC Recruiter"])
    
    if result["level_fptk"]:
        match = re.search(r'(\d+)', result["level_fptk"])
        if match:
            result["level_number"] = int(match.group(1))
            level_num = result["level_number"]
            if 1 <= level_num <= 5:
                result["level_fptk"] = f"{level_num}A"
    else:
        result["level_fptk"] = "1A"
        result["level_number"] = 1
    
    pic_mapping = get_pic_mapping()
    pic_found = False
    
    if result["pic_email"]:
        email_lower = result["pic_email"].lower()
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
    if "keluar" in alasan_lower or "mutasi" in alasan_lower or "promosi" in alasan_lower or "replace" in alasan_lower:
        result["category"] = "REPLACEMENT"
    elif "penambahan" in alasan_lower or "jabatan baru" in alasan_lower or "new" in alasan_lower:
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
    
    if result["kode_pic"]:
        date_code = datetime.now().strftime("%d%m%y")
        posisi_code = ""
        if result["posisi"]:
            posisi_code = re.sub(r'[^A-Za-z]', '', result["posisi"])[:4].upper()
        result["kode_unik"] = f"{result['kode_pic']}{posisi_code}{date_code}"
    
    return result
