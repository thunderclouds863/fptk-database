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
        
        with st.form("fptk_manual_form", clear_on_submit=True):
            st.markdown("### Data FPTK")
            
            col1, col2 = st.columns(2)
            
            with col1:
                kode_pic = st.selectbox("Kode PIC", [""] + kode_pic_options)
                kode_unik = st.text_input("Kode Unik", placeholder="Akan di-generate otomatis")
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
                kode_angka = kode_pic[:4] if kode_pic else "XXXX"
                kode_unik = f"{kode_pic}{kode_angka}{date_code}"
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
    # TAB 3: PASTE EMAIL BODY (DENGAN AUTO-FILL)
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
        # FORM HASIL PARSE (dengan dropdown)
        # ============================================================
        st.markdown("---")
        st.markdown("### Data FPTK (Hasil Parse / Manual)")
        
        with st.form("fptk_email_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Kode PIC - auto detect atau dropdown
                default_kode_pic = parsed_data.get("kode_pic", "")
                kode_pic = st.selectbox(
                    "Kode PIC",
                    [""] + kode_pic_options,
                    index=(kode_pic_options.index(default_kode_pic) + 1) if default_kode_pic in kode_pic_options else 0
                )
                
                # Kode Unik - auto generate
                kode_unik = st.text_input(
                    "Kode Unik",
                    value=parsed_data.get("kode_unik", ""),
                    placeholder="Akan di-generate otomatis"
                )
                
                # Posisi
                posisi = st.text_input(
                    "Posisi *",
                    value=parsed_data.get("posisi", "")
                )
                
                # Business Unit - dropdown
                default_bu = parsed_data.get("business_unit", "")
                business_unit = st.selectbox(
                    "Business Unit *",
                    [""] + bu_options,
                    index=(bu_options.index(default_bu) + 1) if default_bu in bu_options else 0
                )
                
                # Direktorat - dropdown
                default_direktorat = parsed_data.get("direktorat", "")
                direktorat = st.selectbox(
                    "Direktorat *",
                    [""] + direktorat_options,
                    index=(direktorat_options.index(default_direktorat) + 1) if default_direktorat in direktorat_options else 0
                )
                
                # Divisi
                divisi = st.text_input(
                    "Divisi *",
                    value=parsed_data.get("divisi", "")
                )
                
                # Department
                department = st.text_input(
                    "Department *",
                    value=parsed_data.get("department", "")
                )
            
            with col2:
                # FPTK Date
                fptk_date = st.date_input(
                    "FPTK Date (Real) *",
                    parsed_data.get("fptk_date", datetime.now())
                )
                
                # Level FPTK
                level_fptk = st.text_input(
                    "Level FPTK *",
                    value=parsed_data.get("level_fptk", ""),
                    placeholder="Contoh: 1A, 2B, 3A"
                )
                
                # Level Number
                level_number = st.number_input(
                    "Level Number *",
                    min_value=1,
                    max_value=10,
                    value=parsed_data.get("level_number", 1)
                )
                
                # Alasan - dropdown
                default_alasan = parsed_data.get("alasan", "")
                alasan = st.selectbox(
                    "Alasan Permintaan FPTK *",
                    [""] + alasan_options,
                    index=(alasan_options.index(default_alasan) + 1) if default_alasan in alasan_options else 0
                )
                
                # Category - dropdown
                default_category = parsed_data.get("category", "")
                category = st.selectbox(
                    "Category FPTK *",
                    [""] + category_options,
                    index=(category_options.index(default_category) + 1) if default_category in category_options else 0
                )
                
                # PIC Recruiter - auto detect
                default_pic = parsed_data.get("pic_recruiter", "")
                pic_recruiter = st.selectbox(
                    "PIC Recruiter *",
                    [""] + pic_recruiter_options,
                    index=(pic_recruiter_options.index(default_pic) + 1) if default_pic in pic_recruiter_options else 0
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
        
        # ============================================================
        # PROSES SIMPAN (sama seperti tab 2)
        # ============================================================
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
                kode_angka = kode_pic[:4] if kode_pic else "XXXX"
                kode_unik = f"{kode_pic}{kode_angka}{date_code}"
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
def parse_email_body(body: str, kode_pic_options: list, bu_options: list, pic_recruiter_options: list) -> dict:
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
        "level_fptk": "",
        "level_number": 1,
        "lokasi_kerja": "",
        "lokasi_hr": "",
        "status_karyawan": "",
        "vacancy": 1,
        "pic_email": "",
        "pic_recruiter": "",
        "kode_pic": "",
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
    
    # Extract Level Number from Level FPTK (e.g., "1A" -> 1)
    if result["level_fptk"]:
        match = re.search(r'(\d+)', result["level_fptk"])
        if match:
            result["level_number"] = int(match.group(1))
    
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
                pic_found = True
                break
    
    # Coba dari text body
    if not pic_found:
        body_lower = body.lower()
        for key, value in PIC_MAPPING.items():
            if key in body_lower:
                result["pic_recruiter"] = value["name"]
                result["kode_pic"] = value["code"]
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
    # DETERMINE BUSINESS UNIT (mirip VBA F9_GetBUCodeFromPIC / LookupBU)
    # ============================================================
    bu_lower = result["business_unit"].lower()
    for key, value in BU_MAPPING.items():
        if key in bu_lower:
            result["business_unit"] = value
            break
    
    # Jika BU masih kosong dan Kode PIC ada, coba dari Kode PIC
    if not result["business_unit"] and result["kode_pic"]:
        kode = result["kode_pic"].upper()
        if kode.startswith("CORP"):
            result["business_unit"] = "PT CISARUA MOUNTAIN DAIRY, TBK"
        elif kode.startswith("CMD"):
            result["business_unit"] = "PT CISARUA MOUNTAIN DAIRY, TBK"
        elif kode.startswith("MS"):
            result["business_unit"] = "PT MACROSENTRA NIAGABOGA"
        elif kode.startswith("JESS"):
            result["business_unit"] = "PT JAVA EGG SPECIALITIES"
        elif kode.startswith("MP"):
            result["business_unit"] = "PT MACROPRIMA PANGANUTAMA"
        elif kode.startswith("MB"):
            result["business_unit"] = "PT MACROTAMA BINASANTIKA"
        elif kode.startswith("BHC"):
            result["business_unit"] = "PT BAVARIAN CULINARY HAUS"
        elif kode.startswith("ARC"):
            result["business_unit"] = "PT ARTHA RASA CIMORY"
    
    # ============================================================
    # GENERATE KODE UNIK (mirip VBA UpdateKodeUnik)
    # ============================================================
    if result["kode_pic"]:
        date_code = datetime.now().strftime("%d%m%y")
        # Coba ambil posisi code dari posisi
        posisi_code = ""
        if result["posisi"]:
            # Ambil 4 huruf pertama dari posisi
            posisi_code = re.sub(r'[^A-Za-z]', '', result["posisi"])[:4].upper()
        result["kode_unik"] = f"{result['kode_pic']}{posisi_code}{date_code}"
    
    # ============================================================
    # DETERMINE DIREKTORAT (dari master atau mapping)
    # ============================================================
    if result["business_unit"]:
        # Coba mapping sederhana
        bu_lower = result["business_unit"].lower()
        if "cmd" in bu_lower or "cisarua" in bu_lower:
            result["direktorat"] = "Commercial CMD"
        elif "ms" in bu_lower or "macrosentra" in bu_lower:
            result["direktorat"] = "Commercial MS"
        elif "jess" in bu_lower or "java egg" in bu_lower:
            result["direktorat"] = "Commercial JESS"
        elif "mp" in bu_lower or "macroprima" in bu_lower:
            result["direktorat"] = "Commercial MP"
        elif "mb" in bu_lower or "macrotama" in bu_lower:
            result["direktorat"] = "Commercial MB"
        elif "bhc" in bu_lower or "bavarian" in bu_lower:
            result["direktorat"] = "Commercial BHC"
        elif "arc" in bu_lower or "artha rasa" in bu_lower:
            result["direktorat"] = "Commercial ARC"
    
    # ============================================================
    # FORMAT LEVEL DISPLAY (mirip VBA F9_FormatLevelDisplay)
    # ============================================================
    if result["level_number"] > 0:
        # Cari suffix huruf dari level_fptk
        suffix = ""
        if result["level_fptk"]:
            match = re.search(r'[A-Za-z]+$', result["level_fptk"])
            if match:
                suffix = match.group(0).upper()
            else:
                suffix = "A"
        else:
            suffix = "A"
        result["level_fptk"] = f"{result['level_number']}{suffix}"
    
    # ============================================================
    # AUTO-INCREMENT DATE (mirip VBA AutoIncrementFPTKDate)
    # ============================================================
    # Cek apakah ada FPTK dengan posisi + BU + Kode PIC + tanggal yang sama
    db = next(get_db())
    if result["posisi"] and result["business_unit"] and result["kode_pic"]:
        existing = db.query(FPTK).filter(
            FPTK.posisi == result["posisi"],
            FPTK.business_unit == result["business_unit"],
            FPTK.kode_pic == result["kode_pic"],
            FPTK.fptk_date_real == datetime.now().date()
        ).first()
        if existing:
            # Cari tanggal terakhir untuk kombinasi ini
            last_date = db.query(FPTK.fptk_date_real).filter(
                FPTK.posisi == result["posisi"],
                FPTK.business_unit == result["business_unit"],
                FPTK.kode_pic == result["kode_pic"]
            ).order_by(FPTK.fptk_date_real.desc()).first()
            
            if last_date and last_date[0]:
                result["fptk_date"] = last_date[0] + timedelta(days=1)
            else:
                result["fptk_date"] = datetime.now().date() + timedelta(days=1)
        else:
            result["fptk_date"] = datetime.now().date()
    
    db.close()
    
    return result                                      
