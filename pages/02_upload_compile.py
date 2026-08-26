import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
from core.database import get_db
from core.models import FPTK, MasterDropdown, User, UploadStatus, UploadLog
from core.auth import get_current_user, is_admin, hash_file, sanitize_filename
from core.upload_cycle import get_current_cycle, mark_user_uploading, mark_user_done
from core.validator import validate_fptk_file
from core.compiler import compile_fptk
from core.utils import normalize_key, safe_int, parse_date_dmy


# ============================================================
# MAPPING PIC (MIRIP VBA F9_ResolvePIC)
# ============================================================
PIC_MAPPING = {
    "pauline": {"name": "Pauline", "code": "CORPPau"},
    "khaerina": {"name": "Khaerina", "code": "CORPKar"},
    "karin": {"name": "Khaerina", "code": "CORPKar"},
    "ratih": {"name": "Ratih", "code": "CORPTih"},
    "alexa": {"name": "Alexa", "code": "CORPLex"},
    "alexandra": {"name": "Alexa", "code": "CORPLex"},
    "marta": {"name": "Marta", "code": "CORPMar"},
    "brittney": {"name": "Brittney", "code": "CORPBrit"},
    "britney": {"name": "Brittney", "code": "CORPBrit"},
    "omega": {"name": "Omega", "code": "CORPOme"},
    "zwei": {"name": "Zwei", "code": "CORPZwei"},
    "kenthansen": {"name": "Kenthansen", "code": "CORPKen"},
    "desi": {"name": "Desi", "code": "CORPDesi"},
    "elsi": {"name": "Elsi", "code": "CMDEls"},
    "salwa": {"name": "Salwa", "code": "CMDSal"},
    "wahyu": {"name": "Wahyu", "code": "CMDWah"},
    "achmad": {"name": "Achmad", "code": "MPAch"},
    "kasanah": {"name": "Kasanah", "code": "MPKas"},
    "eli": {"name": "Eli", "code": "MPEli"},
    "gabbie": {"name": "Gabbie", "code": "MPGab"},
    "leo": {"name": "Leo", "code": "MSLeo"},
    "fiscall": {"name": "Fiscall", "code": "JESSFis"}
}

# ============================================================
# MAPPING BU (MIRIP VBA GetBUCode / F9_GetBUCodeFromPIC)
# ============================================================
BU_MAPPING = {
    "cisarua mountain dairy": "PT CISARUA MOUNTAIN DAIRY, TBK",
    "macrosentra niagaboga": "PT MACROSENTRA NIAGABOGA",
    "java egg specialities": "PT JAVA EGG SPECIALITIES",
    "macroprima panganutama": "PT MACROPRIMA PANGANUTAMA",
    "macrotama binasantika": "PT MACROTAMA BINASANTIKA",
    "bavarian culinary haus": "PT BAVARIAN CULINARY HAUS",
    "artha rasa cimory": "PT ARTHA RASA CIMORY"
}


def show_upload_compile():
    st.title("📤 Upload & Compile FPTK")
    st.markdown("Upload file Excel recruiter ATAU input FPTK secara manual ATAU paste email body.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # LOAD MASTER DROPDOWN (UNTUK SEMUA TAB)
    # ============================================================
    master_records = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
    # Extract unique values untuk dropdown
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
    pic_recruiter_options = sorted(set([m.pic_recruiter for m in master_records if m.pic_recruiter]))
    kode_pic_options = sorted(set([m.kode_pic for m in master_records if m.kode_pic]))
    lokasi_pic_options = sorted(set([m.lokasi_pic_recruiter for m in master_records if m.lokasi_pic_recruiter]))
    
    # TABS
    tab1, tab2, tab3 = st.tabs(["📤 Upload Excel", "📝 Input Manual FPTK", "📧 Paste Email Body"])
    
    # ================================================================
    # TAB 1: UPLOAD EXCEL
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
        st.caption(f"Status Anda: **{status.status if status else 'Belum Mulai'}")
        
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
                            continue
                        
                        df.columns = df.iloc[header_row].astype(str).str.strip()
                        df = df.iloc[header_row+1:].reset_index(drop=True)
                        
                        validated, errors = validate_fptk_file(df, db, user.id, is_sto)
                        if errors:
                            st.error(f"❌ {file.name}: {len(errors)} error (file ditolak)")
                            continue
                        
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
                            st.error(f"❌ {file.name}: Compile gagal")
                    except Exception as e:
                        st.error(f"❌ {file.name}: {str(e)}")
                
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
    # TAB 2: INPUT MANUAL FPTK (DENGAN DROPDOWN DARI MASTER)
    # ================================================================
    with tab2:
        st.subheader("Input FPTK Manual")
        st.caption("Input satu per satu. Dropdown otomatis dari master data.")
        
        # SESSION STATE untuk autofill
        if "manual_kode_unik" not in st.session_state:
            st.session_state.manual_kode_unik = ""
        if "manual_posisi" not in st.session_state:
            st.session_state.manual_posisi = ""
        
        with st.form("fptk_manual_form", clear_on_submit=True):
            st.markdown("### Data FPTK")
            
            col1, col2 = st.columns(2)
            
            with col1:
                kode_pic = st.selectbox("Kode PIC", [""] + kode_pic_options)
                
                kode_unik = st.text_input(
                    "Kode Unik",
                    placeholder="Akan di-generate otomatis"
                )
                
                posisi = st.text_input("Posisi *")
                
                business_unit = st.selectbox("Business Unit *", [""] + bu_options)
                
                direktorat = st.selectbox("Direktorat *", [""] + direktorat_options)
                
                divisi = st.text_input("Divisi *")
                
                department = st.text_input("Department *")
            
            with col2:
                fptk_date = st.date_input("FPTK Date (Real) *", datetime.now())
                
                level_fptk = st.text_input("Level FPTK *", placeholder="Contoh: 1A, 2B, 3A")
                
                level_number = st.number_input("Level Number *", min_value=1, max_value=10, value=1)
                
                alasan = st.selectbox("Alasan Permintaan FPTK *", [""] + alasan_options)
                
                category = st.selectbox("Category FPTK *", [""] + category_options)
                
                pic_recruiter = st.selectbox("PIC Recruiter *", [""] + pic_recruiter_options)
                
                vacancy = st.number_input("Vacancy *", min_value=1, value=1)
                
                status = st.selectbox("Status *", status_options)
            
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
            if level_number <= 0: errors.append("Level Number wajib > 0")
            if not alasan: errors.append("Alasan Permintaan FPTK wajib diisi")
            if not category: errors.append("Category FPTK wajib diisi")
            if not pic_recruiter: errors.append("PIC Recruiter wajib diisi")
            if vacancy <= 0: errors.append("Vacancy wajib > 0")
            if not status: errors.append("Status wajib diisi")
            if status == "Closed" and not offering_date:
                errors.append("Offering Date wajib diisi jika Status = Closed")
            if status == "Cancel" and not cancel_date:
                errors.append("FPTK Cancel Date wajib diisi jika Status = Cancel")
            
            # Generate Kode Unik jika kosong
            if not kode_unik and kode_pic:
                date_code = fptk_date.strftime("%d%m%y")
                kode_unik = f"{kode_pic}{date_code}"
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
    # TAB 3: PASTE EMAIL BODY
    # ================================================================
    with tab3:
        st.subheader("📧 Paste Email Body")
        st.caption("Paste isi email permintaan FPTK. Sistem akan otomatis mengekstrak data dan mengisi form.")
        
        email_body = st.text_area(
            "Paste Email Body di sini",
            height=200,
            placeholder="Copy paste isi email permintaan FPTK..."
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            process_email = st.button("🔍 Proses Email", type="primary")
        
        # ============================================================
        # PARSE EMAIL
        # ============================================================
        parsed_data = {}
        
        if process_email and email_body:
            with st.spinner("Memproses email..."):
                parsed_data = parse_email_body(email_body, kode_pic_options, bu_options, pic_recruiter_options)
                
                if parsed_data.get("posisi"):
                    st.success("✅ Email berhasil diparse!")
                else:
                    st.warning("⚠️ Tidak ada data yang terdeteksi dari email.")
        
        # ============================================================
        # FORM HASIL PARSE
        # ============================================================
        st.markdown("---")
        st.markdown("### Data FPTK (Hasil Parse / Manual)")
        
        with st.form("fptk_email_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                default_kode_pic = parsed_data.get("kode_pic", "")
                kode_pic = st.selectbox(
                    "Kode PIC",
                    [""] + kode_pic_options,
                    index=(kode_pic_options.index(default_kode_pic) + 1) if default_kode_pic in kode_pic_options else 0
                )
                
                kode_unik = st.text_input(
                    "Kode Unik",
                    value=parsed_data.get("kode_unik", ""),
                    placeholder="Akan di-generate otomatis"
                )
                
                posisi = st.text_input(
                    "Posisi *",
                    value=parsed_data.get("posisi", "")
                )
                
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
