import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from core.database import get_db
from core.models import FPTK, MasterDropdown, User, UploadStatus, UploadLog
from core.auth import get_current_user, is_admin, hash_file, sanitize_filename
from core.upload_cycle import get_current_cycle, mark_user_uploading, mark_user_done
# Untuk FPTK
from core.validator import validate_fptk_file
valid, errors = validate_fptk_file(df_fptk, db, user.id)

# Untuk DB Sourcing
from core.validator import validate_db_sourcing_file
valid, errors = validate_db_sourcing_file(df_sourcing, db, user.id)

# Untuk Blacklist
from core.validator import validate_blacklist_file
valid, errors = validate_blacklist_file(df_blacklist, db, user.id)

# Untuk DB Kode Posisi
from core.validator import validate_db_kode_posisi_file
valid, errors = validate_db_kode_posisi_file(df_db_kode_posisi, db, user.id)
from core.compiler import compile_fptk
from core.utils import (
    normalize_key, safe_int, parse_date_dmy,
    calculate_sla_days,
    calculate_deadline_sla,
    calculate_detail_sla,
    get_sla_option_list,
    calculate_filter_kategorisasi
)

# ============================================================
# MAPPING PIC & KODE BU (SESUAI STRUKTUR)
# ============================================================

# Kode BU mapping
BU_CODE_MAPPING = {
    "CORP": {"nama": "Corporate", "kode": "CORP"},
    "MP": {"nama": "Macroprima Panganutama", "kode": "MP"},
    "CMD": {"nama": "Cisarua Mountain Dairy", "kode": "CMD"},
    "JESS": {"nama": "Java Egg Specialties", "kode": "JESS"},
    "MS": {"nama": "Macrosentra Niagaboga", "kode": "MS"},
}

# PIC mapping lengkap dengan BU
PIC_MAPPING = {
    # CORPORATE (CORP)
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
    
    # MP (Macroprima Panganutama)
    "pauline": {"name": "Pauline", "bu": "MP", "code": "MPPau"},
    "ratih": {"name": "Ratih", "bu": "MP", "code": "MPRat"},
    "achmad": {"name": "Achmad", "bu": "MP", "code": "MPAch"},
    "kasanah": {"name": "Kasanah", "bu": "MP", "code": "MPKas"},
    "alma": {"name": "Alma", "bu": "MP", "code": "MPAlm"},
    
    # CMD (Cisarua Mountain Dairy)
    "salwa": {"name": "Salwa", "bu": "CMD", "code": "CMDSal"},
    "elsi": {"name": "Elsi", "bu": "CMD", "code": "CMDEls"},
    "wahyu": {"name": "Wahyu", "bu": "CMD", "code": "CMDWah"},
    
    # JESS (Java Egg Specialties)
    "riska": {"name": "Riska", "bu": "JESS", "code": "JESSRis"},
    
    # MS (Macrosentra Niagaboga)
    "leo": {"name": "Leo", "bu": "MS", "code": "MSLeo"},
}

# Nama PIC per BU untuk dropdown
PIC_NAMES_BY_BU = {
    "CORP": ["Adista", "Brittney", "Eli", "Fiqra", "Karin", "Kenthansen", "Kevin", "Marta", "Omega", "Salsa", "Valendra", "Victor", "Yeremia", "Zwei"],
    "MP": ["Pauline", "Ratih", "Achmad", "Kasanah", "Alma"],
    "CMD": ["Salwa", "Elsi", "Wahyu"],
    "JESS": ["Riska"],
    "MS": ["Leo"],
}

# Semua PIC untuk dropdown
ALL_PIC_NAMES = sorted([name for names in PIC_NAMES_BY_BU.values() for name in names])

# Kode BU untuk dropdown
ALL_BU_CODES = sorted(BU_CODE_MAPPING.keys())

# Level FPTK (1A sampai 5B)
LEVEL_OPTIONS = []
for num in range(1, 6):
    for letter in ['A', 'B']:
        LEVEL_OPTIONS.append(f"{num}{letter}")


def show_upload_compile():
    st.title("📤 Upload & Compile FPTK")
    st.markdown("Upload file Excel recruiter ATAU input FPTK secara manual ATAU paste email body.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # LOAD MASTER DROPDOWN
    # ============================================================
    master_records = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
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
    
    # TABS
    tab1, tab2, tab3 = st.tabs(["📤 Upload Excel", "📝 Input Manual FPTK", "📧 Paste Email Body"])
    
    # ================================================================
    # TAB 1: UPLOAD EXCEL (SAMA)
    # ================================================================
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
        
        uploaded_files = st.file_uploader(
            "Pilih file Excel (.xlsx, .xlsm)",
            type=["xlsx", "xlsm"],
            accept_multiple_files=True
        )
        is_sto = st.checkbox("☑️ File ini adalah file STO (Tulang Punggung)")
        
        if st.button("🚀 Compile", type="primary"):
            if not uploaded_files:
                st.warning("Pilih file dulu!")
            else:
                for file in uploaded_files:
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
                            continue
                        
                        df.columns = df.iloc[header_row].astype(str).str.strip()
                        df = df.iloc[header_row+1:].reset_index(drop=True)
                        
                        validated, errors = validate_fptk_file(df, db, user.id, is_sto)
                        
                        if errors:
                            st.error(f"❌ {file.name}: {len([e for e in errors if e.get('field') != 'SUMMARY'])} error (file ditolak)")
                            
                            # ============================================================
                            # TAMPILKAN ERROR DETAIL
                            # ============================================================
                            st.markdown("### 📋 Detail Error:")
                            
                            for err in errors:
                                if err.get("field") == "SUMMARY":
                                    st.warning(f"📌 {err.get('error', '')}")
                                    continue
                                
                                row = err.get("row", "?")
                                field = err.get("field", "Unknown")
                                value = err.get("value", "")
                                error_msg = err.get("error", "")
                                expected = err.get("expected", "")
                                example = err.get("example", "")
                                
                                # Buat expander per error
                                with st.expander(f"⚠️ Row {row} - {field}", expanded=False):
                                    st.markdown(f"""
                                    | **Field** | **Value** | **Error** | **Expected** | **Example** |
                                    |-----------|-----------|-----------|--------------|-------------|
                                    | {field} | `{value}` | {error_msg} | {expected} | {example} |
                                    """)
                            
                            # Tambahkan tombol download error detail
                            error_df = pd.DataFrame([
                                {
                                    "Row": e.get("row", ""),
                                    "Field": e.get("field", ""),
                                    "Value": e.get("value", ""),
                                    "Error": e.get("error", ""),
                                    "Expected": e.get("expected", ""),
                                    "Example": e.get("example", "")
                                }
                                for e in errors if e.get("field") != "SUMMARY"
                            ])
                            
                            if not error_df.empty:
                                csv = error_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Error Detail (CSV)",
                                    data=csv,
                                    file_name=f"errors_{file.name}.csv",
                                    mime="text/csv"
                                )
                            
                            st.info("💡 **Tips:** Perbaiki error di atas, lalu upload ulang file yang sudah diperbaiki.")
                            continue
                        
                        # Proses compile kalo valid
                        file_bytes = file.read()
                        result = compile_fptk(
                            db, df, user.id, cycle.id,
                            sanitize_filename(file.name), file_bytes, is_sto
                        )
                        
                        if result["success"]:
                            st.success(
                                f"✅ {file.name}: Imported {result.get('imported',0)}, "
                                f"Updated {result.get('updated',0)}"
                            )
                            mark_user_uploading(db, user.id, cycle.id)
                        else:
                            st.error(f"❌ {file.name}: Compile gagal - {result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        st.error(f"❌ {file.name}: {str(e)}")
                        st.info("💡 Pastikan file Excel memiliki sheet bernama 'FPTK' dan format yang benar.")
                
                st.success("✅ Compile selesai!")
                if st.button("📌 Saya Selesai Upload", type="primary"):
                    mark_user_done(db, user.id, cycle.id)
                    st.success("Status Anda diupdate ke Done!")
                    st.rerun()        
        # Upload History
        st.markdown("---")
        st.subheader("📜 Riwayat Upload")
        logs = db.query(UploadLog).filter(
            UploadLog.user_id == user.id,
            UploadLog.cycle_id == cycle.id
        ).order_by(UploadLog.uploaded_at.desc()).limit(50).all()
        
        if logs:
            data = [{
                "Tanggal": l.uploaded_at.strftime("%d/%m/%Y %H:%M"),
                "File": l.file_name,
                "Status": l.status,
                "Records": l.record_count or 0
            } for l in logs]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
    
    # ================================================================
    # TAB 2: INPUT MANUAL FPTK
    # ================================================================
    with tab2:
        st.subheader("Input FPTK Manual")
        st.caption("Input satu per satu. PIC otomatis dari user yang login.")
        
        # Ambil data PIC dari user yang login
        user_pic_name = user.pic_recruiter or ""
        user_pic_code = ""
        user_pic_bu = ""
        
        # Cari di mapping
        for key, val in PIC_MAPPING.items():
            if val["name"].lower() == user_pic_name.lower():
                user_pic_code = val["code"]
                user_pic_bu = val["bu"]
                break
        
        if not user_pic_code:
            for key, val in PIC_MAPPING.items():
                if key == user.username.lower():
                    user_pic_name = val["name"]
                    user_pic_code = val["code"]
                    user_pic_bu = val["bu"]
                    break
        
        st.info(f"👤 PIC Login: **{user_pic_name}** | Kode: **{user_pic_code}** | BU: **{user_pic_bu}**")
        
        with st.form("fptk_manual_form", clear_on_submit=True):
            st.markdown("### Data FPTK")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Kode PIC - auto dari login
                kode_pic = st.text_input(
                    "Kode PIC",
                    value=user_pic_code,
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                # ============================================================
                # KODE UNIK - ADMIN BISA ISI MANUAL, USER AUTO
                # ============================================================
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
                
                # Posisi
                posisi = st.text_input("Posisi *")
                
                # Business Unit - dropdown
                business_unit = st.selectbox("Business Unit *", [""] + bu_options)
                
                # Direktorat - dropdown
                direktorat = st.selectbox("Direktorat *", [""] + direktorat_options)
                
                # Divisi
                divisi = st.text_input("Divisi *")
                
                # Department
                department = st.text_input("Department *")
            
            with col2:
                # FPTK Date
                fptk_date = st.date_input("FPTK Date (Real) *", datetime.now())
                
                # Level FPTK - DROPDOWN 1A SAMPAI 5B
                level_fptk = st.selectbox("Level FPTK *", LEVEL_OPTIONS, index=0)
                
                # Level Number - AUTO dari Level FPTK
                if level_fptk:
                    match = re.search(r'(\d+)', level_fptk)
                    level_number = int(match.group(1)) if match else 1
                else:
                    level_number = 1
                st.text_input("Level Number (auto)", value=str(level_number), disabled=True)
                
                # Alasan - dropdown
                alasan = st.selectbox("Alasan Permintaan FPTK *", [""] + alasan_options)
                
                # Category - dropdown
                category = st.selectbox("Category FPTK *", [""] + category_options)
                
                # PIC Recruiter - auto dari login
                pic_recruiter = st.text_input(
                    "PIC Recruiter *",
                    value=user_pic_name,
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                # Vacancy
                vacancy = st.number_input("Vacancy *", min_value=1, value=1)
                
                # Status
                status = st.selectbox("Status *", status_options)
                # Di dalam form, setelah Jumlah SLA / Deadline SLA, tambahkan:

                # Jumlah SLA (auto-calculate)
                sla_days = calculate_sla_days(level_number)
                st.text_input("Jumlah SLA (auto)", value=str(sla_days), disabled=True)
                # Deadline SLA (auto-calculate)
                if fptk_date and sla_days:
                    deadline_sla = calculate_deadline_sla(fptk_date, sla_days)
                    st.text_input("Deadline SLA (auto)", value=deadline_sla.strftime("%d/%m/%Y") if deadline_sla else "-", disabled=True)
                # Detail SLA - DROPDOWN (bisa diisi manual)
                detail_sla_options = [
                    "OP Belum Lewat SLA",
                    "OP Tidak Lulus SLA",
                    "Closed Lulus SLA",
                    "Closed Tidak Lulus SLA",
                    "Cancel FPTK"
                ]
                new_detail_sla = st.selectbox("Detail SLA", [""] + detail_sla_options)
            
            # Conditional fields
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
        
        # Proses simpan
        if submitted:
            errors = []
            
            # Validasi
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
            
            # Generate Kode Unik jika kosong
            if not kode_unik and kode_pic:
                date_code = fptk_date.strftime("%d%m%y")
                # Ambil 4 huruf pertama dari posisi
                posisi_code = ""
                if posisi:
                    posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper()
                kode_unik = f"{kode_pic}{posisi_code}{date_code}"
                if not kode_unik:
                    errors.append("Kode Unik tidak bisa di-generate. Isi Kode PIC dulu.")
            
            # Cek duplikat Kode Unik
            if kode_unik:
                existing = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
                if existing:
                    errors.append(f"Kode Unik '{kode_unik}' sudah ada di database!")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                try:
                    # Hitung SLA
                    if level_number <= 3: sla_days = 30
                    elif level_number == 4: sla_days = 45
                    else: sla_days = 60
                    
                    deadline_sla = fptk_date + timedelta(days=sla_days) if fptk_date else None
                    week_num = fptk_date.isocalendar()[1] if fptk_date else None
                    month_name = fptk_date.strftime("%B") if fptk_date else None
                    kode_bu = kode_pic[:4] if kode_pic else ""
                    
                    # Tentukan filter kategorisasi
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
                    
                    # Simpan
                    new_fptk = FPTK(
                        kode_unik=kode_unik,
                        posisi=posisi,
                        kode_pic=kode_pic,
                        fptk_date_real=fptk_date,
                        fptk_date_kode=fptk_date,
                        kode_angka=f"{kode_pic}{vacancy}" if kode_pic else "",
                        business_unit=business_unit,
                        direktorat=direktorat,
                        divisi=divisi,
                        department=department,
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
                        week_fptk_date=week_num,
                        month_fptk_date=month_name,
                        kode_bu=kode_bu,
                        nama_kandidat=nama_kandidat,
                        lokasi_kerja=lokasi_kerja,
                        lokasi_hr=lokasi_hr,
                        user_manager=user_manager,
                        indirect_user=indirect_user,
                        status_karyawan=status_karyawan,
                        estimasi_join=estimasi_join,
                        kebutuhan_laptop=kebutuhan_laptop,
                        lokasi_onboarding=lokasi_onboarding,
                        fptk_availability=fptk_availability,
                        remark=remark,
                        source_user_id=user.id,
                        created_at=datetime.now(),
                        last_compile_action="MANUAL_INPUT"
                    )
                    db.add(new_fptk)
                    db.commit()
                    
                    st.success(f"✅ FPTK berhasil disimpan!")
                    st.info(f"📋 Kode Unik: **{kode_unik}**")
                    st.info(f"📋 Deadline SLA: **{deadline_sla.strftime('%d/%m/%Y') if deadline_sla else '-'}**")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
    
    # ================================================================
    # TAB 3: PASTE EMAIL BODY (DENGAN AUTO-FILL DARI PIC LOGIN & LEVEL DROPDOWN)
    # ================================================================
    with tab3:
        st.subheader("📧 Paste Email Body")
        st.caption("Paste isi email permintaan FPTK. Sistem akan otomatis mengekstrak data.")
        
        email_body = st.text_area(
            "Paste Email Body di sini",
            height=200,
            placeholder="Copy paste isi email permintaan FPTK..."
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            process_email = st.button("🔍 Proses Email", type="primary")
        
        # Parse email
        parsed_data = {}
        
        if process_email and email_body:
            with st.spinner("Memproses email..."):
                parsed_data = parse_email_body(email_body, bu_options, alasan_options, category_options, direktorat_options)
                
                if parsed_data.get("posisi"):
                    st.success("✅ Email berhasil diparse!")
                else:
                    st.warning("⚠️ Tidak ada data yang terdeteksi dari email.")
        
        # Fallback: jika email tidak terdeteksi, tetap pakai PIC login
        if not parsed_data.get("pic_recruiter"):
            parsed_data["pic_recruiter"] = user_pic_name
            parsed_data["kode_pic"] = user_pic_code
            parsed_data["kode_bu"] = user_pic_bu
        
        # ============================================================
        # FORM HASIL PARSE
        # ============================================================
        st.markdown("---")
        st.markdown("### Data FPTK (Hasil Parse / Manual)")
        
        with st.form("fptk_email_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Kode PIC - auto dari login atau hasil parse
                kode_pic = st.text_input(
                    "Kode PIC",
                    value=parsed_data.get("kode_pic", user_pic_code),
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                # ============================================================
                # KODE UNIK - ADMIN BISA ISI MANUAL, USER AUTO
                # ============================================================
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
                
                # Posisi
                posisi = st.text_input("Posisi *", value=parsed_data.get("posisi", ""))
                
                # Business Unit
                default_bu = parsed_data.get("business_unit", "")
                business_unit = st.selectbox(
                    "Business Unit *",
                    [""] + bu_options,
                    index=(bu_options.index(default_bu) + 1) if default_bu in bu_options else 0
                )
                
                # Direktorat
                default_direktorat = parsed_data.get("direktorat", "")
                direktorat = st.selectbox(
                    "Direktorat *",
                    [""] + direktorat_options,
                    index=(direktorat_options.index(default_direktorat) + 1) if default_direktorat in direktorat_options else 0
                )
                
                # Divisi
                divisi = st.text_input("Divisi *", value=parsed_data.get("divisi", ""))
                
                # Department
                department = st.text_input("Department *", value=parsed_data.get("department", ""))
            
            with col2:
                # FPTK Date
                fptk_date = st.date_input(
                    "FPTK Date (Real) *",
                    parsed_data.get("fptk_date", datetime.now())
                )
                
                # Level FPTK - DROPDOWN 1A SAMPAI 5B
                default_level = parsed_data.get("level_fptk", "1A")
                if default_level not in LEVEL_OPTIONS:
                    default_level = "1A"
                level_fptk = st.selectbox(
                    "Level FPTK *",
                    LEVEL_OPTIONS,
                    index=LEVEL_OPTIONS.index(default_level) if default_level in LEVEL_OPTIONS else 0
                )
                
                # Level Number - AUTO
                if level_fptk:
                    match = re.search(r'(\d+)', level_fptk)
                    level_number = int(match.group(1)) if match else 1
                else:
                    level_number = 1
                st.text_input("Level Number (auto)", value=str(level_number), disabled=True)
                
                # Alasan
                default_alasan = parsed_data.get("alasan", "")
                alasan = st.selectbox(
                    "Alasan Permintaan FPTK *",
                    [""] + alasan_options,
                    index=(alasan_options.index(default_alasan) + 1) if default_alasan in alasan_options else 0
                )
                
                # Category
                default_category = parsed_data.get("category", "")
                category = st.selectbox(
                    "Category FPTK *",
                    [""] + category_options,
                    index=(category_options.index(default_category) + 1) if default_category in category_options else 0
                )
                
                # PIC Recruiter - auto dari login
                pic_recruiter = st.text_input(
                    "PIC Recruiter *",
                    value=parsed_data.get("pic_recruiter", user_pic_name),
                    disabled=True,
                    help="Otomatis dari PIC yang login"
                )
                
                # Vacancy
                vacancy = st.number_input(
                    "Vacancy *",
                    min_value=1,
                    value=parsed_data.get("vacancy", 1)
                )
                
                # Status
                status = st.selectbox(
                    "Status *",
                    status_options,
                    index=0 if not parsed_data.get("status") else (status_options.index(parsed_data["status"]) if parsed_data.get("status") in status_options else 0)
                )
                # Jumlah SLA (auto-calculate)
                sla_days = calculate_sla_days(level_number)
                st.text_input("Jumlah SLA (auto)", value=str(sla_days), disabled=True)
                # Deadline SLA (auto-calculate)
                if fptk_date and sla_days:
                    deadline_sla = calculate_deadline_sla(fptk_date, sla_days)
                    st.text_input("Deadline SLA (auto)", value=deadline_sla.strftime("%d/%m/%Y") if deadline_sla else "-", disabled=True)
                # Detail SLA - DROPDOWN (bisa diisi manual)
                detail_sla_options = [
                    "OP Belum Lewat SLA",
                    "OP Tidak Lulus SLA",
                    "Closed Lulus SLA",
                    "Closed Tidak Lulus SLA",
                    "Cancel FPTK"
                ]
                new_detail_sla = st.selectbox("Detail SLA", [""] + detail_sla_options)
            # Conditional fields
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
        
        # Proses simpan (sama seperti tab 2)
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
            
            if not kode_unik and kode_pic:
                date_code = fptk_date.strftime("%d%m%y")
                posisi_code = ""
                if posisi:
                    posisi_code = re.sub(r'[^A-Za-z]', '', posisi)[:4].upper()
                kode_unik = f"{kode_pic}{posisi_code}{date_code}"
                if not kode_unik:
                    errors.append("Kode Unik tidak bisa di-generate.")
            
            if kode_unik:
                existing = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
                if existing:
                    errors.append(f"Kode Unik '{kode_unik}' sudah ada!")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
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
                    
                    new_fptk = FPTK(
                        kode_unik=kode_unik,
                        posisi=posisi,
                        kode_pic=kode_pic,
                        fptk_date_real=fptk_date,
                        fptk_date_kode=fptk_date,
                        kode_angka=f"{kode_pic}{vacancy}" if kode_pic else "",
                        business_unit=business_unit,
                        direktorat=direktorat,
                        divisi=divisi,
                        department=department,
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
                        week_fptk_date=week_num,
                        month_fptk_date=month_name,
                        kode_bu=kode_bu,
                        nama_kandidat=nama_kandidat,
                        lokasi_kerja=lokasi_kerja,
                        lokasi_hr=lokasi_hr,
                        user_manager=user_manager,
                        indirect_user=indirect_user,
                        status_karyawan=status_karyawan,
                        estimasi_join=estimasi_join,
                        kebutuhan_laptop=kebutuhan_laptop,
                        lokasi_onboarding=lokasi_onboarding,
                        fptk_availability=fptk_availability,
                        remark=remark,
                        source_user_id=user.id,
                        created_at=datetime.now(),
                        last_compile_action="EMAIL_PARSE"
                    )
                    db.add(new_fptk)
                    db.commit()
                    
                    st.success(f"✅ FPTK berhasil disimpan dari email!")
                    st.info(f"📋 Kode Unik: **{kode_unik}**")
                    st.info(f"📋 Deadline SLA: **{deadline_sla.strftime('%d/%m/%Y') if deadline_sla else '-'}**")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()


# ============================================================
# FUNGSI PARSE EMAIL (MIRIP VBA F9_LoadParsedEmailToForm)
# ============================================================
def parse_email_body(body: str, bu_options: list, alasan_options: list, category_options: list, direktorat_options: list) -> dict:
    """
    Parse email body untuk ekstrak field FPTK.
    Mirip dengan F9_LoadParsedEmailToForm di VBA.
    """
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
    
    # Normalize text
    text = body.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    
    # ============================================================
    # EKSTRAK FIELD (mirip VBA F9_FindField)
    # ============================================================
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
    
    # Ekstrak field
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
    
    # Extract Level Number dari Level FPTK
    if result["level_fptk"]:
        match = re.search(r'(\d+)', result["level_fptk"])
        if match:
            result["level_number"] = int(match.group(1))
            # Pastikan level_fptk sesuai format 1A-5B
            level_num = result["level_number"]
            if 1 <= level_num <= 5:
                result["level_fptk"] = f"{level_num}A"
    else:
        result["level_fptk"] = "1A"
        result["level_number"] = 1
    
    # ============================================================
    # RESOLVE PIC (mirip VBA F9_ResolvePIC)
    # ============================================================
    pic_found = False
    
    # Coba dari email
    if result["pic_email"]:
        email_lower = result["pic_email"].lower()
        for key, value in PIC_MAPPING.items():
            if key in email_lower:
                result["pic_recruiter"] = value["name"]
                result["kode_pic"] = value["code"]
                result["kode_bu"] = value["bu"]
                pic_found = True
                break
    
    # Coba dari text body
    if not pic_found:
        body_lower = body.lower()
        for key, value in PIC_MAPPING.items():
            if key in body_lower:
                result["pic_recruiter"] = value["name"]
                result["kode_pic"] = value["code"]
                result["kode_bu"] = value["bu"]
                pic_found = True
                break
    
    # ============================================================
    # DETERMINE CATEGORY (mirip VBA F9_DetermineCategoryFPTK)
    # ============================================================
    alasan_lower = result["alasan"].lower()
    if "keluar" in alasan_lower or "mutasi" in alasan_lower or "promosi" in alasan_lower or "replace" in alasan_lower:
        result["category"] = "REPLACEMENT"
    elif "penambahan" in alasan_lower or "jabatan baru" in alasan_lower or "new" in alasan_lower:
        result["category"] = "NEW"
    else:
        result["category"] = "REPLACEMENT"
    
    # ============================================================
    # DETERMINE BUSINESS UNIT & DIREKTORAT
    # ============================================================
    # Coba dari mapping BU
    bu_lower = result["business_unit"].lower()
    for key, value in BU_CODE_MAPPING.items():
        if key.lower() in bu_lower or value["nama"].lower() in bu_lower:
            result["business_unit"] = value["nama"]
            result["kode_bu"] = key
            break
    
    # Jika dari Kode PIC
    if not result["kode_bu"] and result["kode_pic"]:
        for key, value in PIC_MAPPING.items():
            if value["code"] == result["kode_pic"]:
                result["kode_bu"] = value["bu"]
                break
    
    # Set Direktorat dari Kode BU
    if result["kode_bu"]:
        bu_map = {
            "CORP": "Corporate",
            "MP": "Commercial MP",
            "CMD": "Commercial CMD",
            "JESS": "Commercial JESS",
            "MS": "Commercial MS"
        }
        result["direktorat"] = bu_map.get(result["kode_bu"], "")
    
    # ============================================================
    # GENERATE KODE UNIK
    # ============================================================
    if result["kode_pic"]:
        date_code = datetime.now().strftime("%d%m%y")
        posisi_code = ""
        if result["posisi"]:
            posisi_code = re.sub(r'[^A-Za-z]', '', result["posisi"])[:4].upper()
        result["kode_unik"] = f"{result['kode_pic']}{posisi_code}{date_code}"
    
    return result
