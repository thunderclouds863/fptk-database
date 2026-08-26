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

def show_upload_compile():
    st.title("📤 Upload & Compile FPTK")
    st.markdown("Upload file Excel recruiter ATAU input FPTK secara manual ATAU paste email body.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # TABS
    tab1, tab2, tab3 = st.tabs(["📤 Upload Excel", "📝 Input Manual FPTK", "📧 Paste Email Body"])
    
    # ================================================================
    # TAB 1: UPLOAD EXCEL (SAMA SEPERTI SEBELUMNYA)
    # ================================================================
    with tab1:
        # ... (kode tab 1 tetap sama seperti sebelumnya) ...
        pass
    
    # ================================================================
    # TAB 2: INPUT MANUAL FPTK (SAMA SEPERTI SEBELUMNYA)
    # ================================================================
    with tab2:
        # ... (kode tab 2 tetap sama seperti sebelumnya) ...
        pass
    
    # ================================================================
    # TAB 3: PASTE EMAIL BODY (BARU - MIRIP VBA frmInputFPTK)
    # ================================================================
    with tab3:
        st.subheader("📧 Paste Email Body")
        st.caption("Paste isi email permintaan FPTK. Sistem akan otomatis mengekstrak data dan mengisi form.")
        
        # Load master data untuk dropdown
        master = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        
        pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
        kode_pic_options = sorted(set([m.kode_pic for m in master if m.kode_pic]))
        bu_options = sorted(set([m.bu for m in master if m.bu]))
        alasan_options = sorted(set([m.alasan for m in master if m.alasan]))
        category_options = sorted(set([m.category_fptk for m in master if m.category_fptk]))
        direktorat_options = sorted(set([m.nama_direktorat for m in master if m.nama_direktorat]))
        status_options = ["OP", "Closed", "Cancel"]
        
        # ============================================================
        # EMAIL BODY TEXTAREA
        # ============================================================
        email_body = st.text_area(
            "Paste Email Body di sini",
            height=200,
            placeholder="Copy paste isi email permintaan FPTK..."
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            process_email = st.button("🔍 Proses Email", type="primary")
        
        # ============================================================
        # PARSE EMAIL (mirip VBA F9_LoadParsedEmailToForm)
        # ============================================================
        parsed_data = {}
        
        if process_email and email_body:
            with st.spinner("Memproses email..."):
                parsed_data = parse_email_body(email_body)
                
                if parsed_data.get("posisi"):
                    st.success("✅ Email berhasil diparse!")
                else:
                    st.warning("⚠️ Tidak ada data yang terdeteksi dari email. Silakan cek kembali.")
        
        # ============================================================
        # FORM HASIL PARSE (auto-filled dari email)
        # ============================================================
        st.markdown("---")
        st.markdown("### Data FPTK (Hasil Parse / Manual)")
        
        with st.form("fptk_email_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Kode PIC - auto detect dari email
                kode_pic = st.selectbox(
                    "Kode PIC",
                    [""] + kode_pic_options,
                    index=0 if not parsed_data.get("kode_pic") else (kode_pic_options.index(parsed_data["kode_pic"]) + 1 if parsed_data.get("kode_pic") in kode_pic_options else 0)
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
                
                # Business Unit
                business_unit = st.selectbox(
                    "Business Unit *",
                    [""] + bu_options,
                    index=0 if not parsed_data.get("business_unit") else (bu_options.index(parsed_data["business_unit"]) + 1 if parsed_data.get("business_unit") in bu_options else 0)
                )
                
                # Direktorat
                direktorat = st.selectbox(
                    "Direktorat *",
                    [""] + direktorat_options,
                    index=0 if not parsed_data.get("direktorat") else (direktorat_options.index(parsed_data["direktorat"]) + 1 if parsed_data.get("direktorat") in direktorat_options else 0)
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
                # FPTK Date - auto increment jika ada duplikat
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
                
                # Alasan
                alasan = st.selectbox(
                    "Alasan Permintaan FPTK *",
                    [""] + alasan_options,
                    index=0 if not parsed_data.get("alasan") else (alasan_options.index(parsed_data["alasan"]) + 1 if parsed_data.get("alasan") in alasan_options else 0)
                )
                
                # Category
                category = st.selectbox(
                    "Category FPTK *",
                    [""] + category_options,
                    index=0 if not parsed_data.get("category") else (category_options.index(parsed_data["category"]) + 1 if parsed_data.get("category") in category_options else 0)
                )
                
                # PIC Recruiter
                pic_recruiter = st.selectbox(
                    "PIC Recruiter *",
                    [""] + pic_options,
                    index=0 if not parsed_data.get("pic_recruiter") else (pic_options.index(parsed_data["pic_recruiter"]) + 1 if parsed_data.get("pic_recruiter") in pic_options else 0)
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
                lokasi_onboarding = st.selectbox("Lokasi Onboarding", [""] + sorted(set([m.lokasi_onboarding for m in master if m.lokasi_onboarding])))
                fptk_availability = st.selectbox("FPTK Availability", ["", "Y", "N"])
                remark = st.text_area("Remark", value=parsed_data.get("remark", ""))
            
            st.markdown("---")
            submitted = st.form_submit_button("💾 Simpan FPTK", type="primary")
        
        # ============================================================
        # PROSES SIMPAN
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
def parse_email_body(body: str) -> dict:
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
    
    # Mapping PIC dari email/name (mirip VBA F9_ResolvePIC)
    pic_mapping = {
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
    
    # BU Mapping
    bu_mapping = {
        "cisarua mountain dairy": "PT CISARUA MOUNTAIN DAIRY, TBK",
        "macrosentra niagaboga": "PT MACROSENTRA NIAGABOGA",
        "java egg specialities": "PT JAVA EGG SPECIALITIES",
        "macroprima panganutama": "PT MACROPRIMA PANGANUTAMA",
        "macrotama binasantika": "PT MACROTAMA BINASANTIKA",
        "bavarian culinary haus": "PT BAVARIAN CULINARY HAUS",
        "artha rasa cimory": "PT ARTHA RASA CIMORY"
    }
    
    # ============================================================
    # EKSTRAK FIELD (mirip VBA F9_FindField)
    # ============================================================
    def find_field(field_names):
        for i, line in enumerate(lines):
            clean_line = line.strip()
            for name in field_names:
                if name.lower() in clean_line.lower():
                    # Ambil value setelah colon
                    if ':' in clean_line:
                        value = clean_line.split(':', 1)[1].strip()
                        if value:
                            return value
                    # Cek line berikutnya
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
        import re
        match = re.search(r'(\d+)', result["level_fptk"])
        if match:
            result["level_number"] = int(match.group(1))
    
    # Determine PIC from email
    if result["pic_email"]:
        email_lower = result["pic_email"].lower()
        for key, value in pic_mapping.items():
            if key in email_lower:
                result["pic_recruiter"] = value["name"]
                result["kode_pic"] = value["code"]
                break
    
    # Determine Category from Alasan
    alasan_lower = result["alasan"].lower()
    if "keluar" in alasan_lower or "mutasi" in alasan_lower or "promosi" in alasan_lower or "replace" in alasan_lower:
        result["category"] = "REPLACEMENT"
    elif "penambahan" in alasan_lower or "jabatan baru" in alasan_lower or "new" in alasan_lower:
        result["category"] = "NEW"
    else:
        result["category"] = "REPLACEMENT"
    
    # Determine BU from Business Unit
    bu_lower = result["business_unit"].lower()
    for key, value in bu_mapping.items():
        if key in bu_lower:
            result["business_unit"] = value
            break
    
    # Generate Kode Unik (if Kode PIC available)
    if result["kode_pic"] and result["posisi"]:
        date_code = datetime.now().strftime("%d%m%y")
        result["kode_unik"] = f"{result['kode_pic']}{date_code}"
    
    # Auto-increment FPTK Date if same position exists today
    # (Check database untuk cari last date)
    db = next(get_db())
    if result["posisi"] and result["business_unit"] and result["kode_pic"]:
        existing = db.query(FPTK).filter(
            FPTK.posisi == result["posisi"],
            FPTK.business_unit == result["business_unit"],
            FPTK.kode_pic == result["kode_pic"],
            FPTK.fptk_date_real == datetime.now().date()
        ).first()
        if existing:
            # If same date exists, increment by 1 day
            result["fptk_date"] = datetime.now().date() + timedelta(days=1)
        else:
            result["fptk_date"] = datetime.now().date()
    
    db.close()
    
    return result
