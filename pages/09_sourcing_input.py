import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user
from core.utils import safe_int, parse_phone, is_valid_email, normalize_key
import time
import re

COPILOT_AGENT_URL = "https://m365.cloud.microsoft/chat/?titleId=T_e0524666-839c-757c-7ef5-d5e72311417d&source=embedded-builder"

# ============================================================
# CACHE FUNCTIONS
# ============================================================

@st.cache_data(ttl=3600)
def get_master_options_sourcing(_db):
    try:
        master = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
        bu_options = sorted(set([m.bu for m in master if m.bu]))
        return {
            'pic_options': pic_options,
            'bu_options': bu_options
        }
    except Exception as e:
        return {
            'pic_options': [],
            'bu_options': []
        }


@st.cache_data(ttl=3600)
def get_sourcing_options():
    return {
        'sumber_options': ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance", "Lainnya"],
        'jenjang_options': ["SMA/SMK", "D3", "D4", "S1", "S2"],
        'univ_options': ["Universitas Indonesia", "Universitas Gadjah Mada", "Institut Teknologi Bandung", "Universitas Airlangga", "Universitas Padjadjaran", "Universitas Diponegoro", "Universitas Brawijaya", "Institut Pertanian Bogor", "Universitas Sebelas Maret", "Telkom University", "Lainnya"],
        'jurusan_options': ["Manajemen", "Akuntansi", "Teknik Industri", "Teknik Informatika", "Sistem Informasi", "Psikologi", "Ilmu Komunikasi", "Hukum", "Ekonomi", "Lainnya"],
        'fmcg_options': ["", "Ya", "Tidak"],
        'pipeline_options': ["", "V", "X"]
    }


@st.cache_data(ttl=3600)
def get_pipeline_stages():
    return [
        {"field": "sourcing_freelance", "label": "Sourcing Freelance", "desc": "Sourcing oleh freelance"},
        {"field": "sourcing_hr", "label": "Sourcing HR", "desc": "Sourcing oleh HR internal"},
        {"field": "shortlist_cv", "label": "Shortlist CV", "desc": "CV sudah di-shortlist"},
        {"field": "psikotes", "label": "Psikotes", "desc": "Tes psikotes"},
        {"field": "hr_interview", "label": "HR Interview", "desc": "Interview dengan HR"},
        {"field": "technical_test_case_study", "label": "Technical Test / Case Study", "desc": "Tes teknis / case study"},
        {"field": "market_visit", "label": "Market Visit", "desc": "Kunjungan ke pasar / outlet"},
        {"field": "user_interview", "label": "User Interview", "desc": "Interview dengan user"},
        {"field": "panel_interview", "label": "Panel Interview", "desc": "Interview panel"},
        {"field": "reference_check", "label": "Reference Check", "desc": "Cek referensi"},
        {"field": "mcu", "label": "MCU", "desc": "Medical Check Up"},
        {"field": "offering", "label": "Offering", "desc": "Penawaran"},
        {"field": "day1", "label": "Day 1", "desc": "Hari pertama kerja"}
    ]


def parse_cv_text(raw_text: str) -> dict:
    """Parse CV text ke dictionary fields - support format Copilot"""
    parsed = {
        "nama": "",
        "email": "",
        "hp": "",
        "universitas": "",
        "jenjang": "",
        "jurusan": "",
        "ipk": "",
        "tahun_lulus": "",
        "domisili": "",
        "last_position": "",
        "last_company": "",
        "last_tenure": "",
        "total_tenure": "",
        "fmcg": "",
        "sumber": "",
        "posisi": "",
        "kode_unik": "",
        "univ_lain": ""
    }
    
    if not raw_text:
        return parsed
    
    lines = raw_text.split('\n')
    
    # Map key yang lebih lengkap
    key_map = {
        'nama': ['nama', 'name', 'full name', 'candidate name'],
        'email': ['email', 'email address'],
        'hp': ['hp', 'no hp', 'nomor hp', 'phone', 'phone number', 'no. hp'],
        'universitas': ['universitas', 'university', 'univ', 'college'],
        'jenjang': ['jenjang', 'jenjang pendidikan', 'education level', 'level'],
        'jurusan': ['jurusan', 'major', 'program studi'],
        'ipk': ['ipk', 'gpa', 'grade point average'],
        'tahun_lulus': ['tahun lulus', 'graduation year', 'year of graduation', 'lulus'],
        'domisili': ['domisili', 'domicile', 'location', 'city', 'kota', 'address'],
        'last_position': ['last position', 'posisi terakhir', 'previous position', 'last job'],
        'last_company': ['last company', 'perusahaan terakhir', 'previous company', 'last employer'],
        'last_tenure': ['last tenure', 'tenure in last position', 'lama di posisi terakhir'],
        'total_tenure': ['total tenure', 'total pengalaman', 'length of experience', 'total experience'],
        'fmcg': ['fmcg', 'pernah di fmcg', 'fmcg experience', 'industry', 'pengalaman fmcg'],
        'sumber': ['sumber', 'source', 'sourcing source'],
        'posisi': ['posisi', 'position', 'applied position'],
        'kode_unik': ['kode unik', 'unique code', 'kode']
    }
    
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()
            
            # Cari match di key_map
            matched_key = None
            for target, aliases in key_map.items():
                for alias in aliases:
                    if alias in key:
                        matched_key = target
                        break
                if matched_key:
                    break
            
            if matched_key and val:
                # Handling khusus untuk Jenjang
                if matched_key == 'jenjang':
                    jenjang_upper = val.upper()
                    if jenjang_upper in ['S1', 'S2', 'S3', 'D3', 'D4', 'SMA', 'SMK']:
                        parsed[matched_key] = jenjang_upper
                    else:
                        parsed[matched_key] = val
                elif matched_key == 'ipk':
                    # Normalisasi IPK (ganti koma dengan titik)
                    parsed[matched_key] = val.replace(',', '.')
                elif matched_key == 'tahun_lulus':
                    # Ambil angka tahun (4 digit)
                    tahun_match = re.search(r'\b(19|20)\d{2}\b', val)
                    if tahun_match:
                        parsed[matched_key] = tahun_match.group(0)
                    else:
                        parsed[matched_key] = val
                elif matched_key == 'hp':
                    # Bersihkan HP
                    parsed[matched_key] = re.sub(r'[^0-9+]', '', val)
                else:
                    parsed[matched_key] = val
    
    # Fallback: kalau ga ada label 'Nama:', ambil baris pertama yang ada isinya
    if not parsed.get('nama'):
        for line in lines:
            line = line.strip()
            # Skip baris kosong atau yang mengandung kata-kata umum
            if line and ':' not in line and len(line) > 2 and len(line) < 80:
                if not any(word in line.lower() for word in ['cv', 'curriculum', 'resume', 'data', 'pendidikan']):
                    parsed['nama'] = line
                    break
    
    # Cleanup: jika nama masih kosong, coba cari dari baris pertama setelah "Nama:" di text
    if not parsed.get('nama'):
        nama_match = re.search(r'Nama\s*[:;]\s*([^\n]+)', raw_text, re.IGNORECASE)
        if nama_match:
            parsed['nama'] = nama_match.group(1).strip()
    
    return parsed


def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input kandidat baru ke DB Sourcing")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # ============================================================
    # LOAD FROM CACHE
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        master_options = get_master_options_sourcing(db)
        sourcing_options = get_sourcing_options()
        pipeline_stages = get_pipeline_stages()
    
    pic_options = master_options['pic_options']
    sumber_options = sourcing_options['sumber_options']
    jenjang_options = sourcing_options['jenjang_options']
    univ_options = sourcing_options['univ_options']
    jurusan_options = sourcing_options['jurusan_options']
    fmcg_options = sourcing_options['fmcg_options']
    pipeline_options = sourcing_options['pipeline_options']
    
    # State untuk parsing
    if 'parsed_cv_data' not in st.session_state:
        st.session_state.parsed_cv_data = {}
    if 'show_parsed_form' not in st.session_state:
        st.session_state.show_parsed_form = False
    
    # ============================================================
    # COPILOT AGENT BUTTON
    # ============================================================
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("### 🤖 Copilot Agent")
        st.caption("Parsing CV gambar/PDF scan menggunakan Copilot Agent")
    with col2:
        st.link_button("🚀 Buka Copilot Agent", COPILOT_AGENT_URL, use_container_width=True, type="primary")
    with col3:
        st.caption("Upload CV → Copy hasil → Paste di sini")
    
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📝 Manual Input", "📋 Paste Text", "📦 Batch CV"])
    
    # ============================================================
    # TAB 1: MANUAL INPUT (FORM KOSONG)
    # ============================================================
    with tab1:
        st.subheader("Manual Input Kandidat")
        show_sourcing_form(
            db=db,
            user=user,
            pic_options=pic_options,
            sourcing_options=sourcing_options,
            pipeline_options=pipeline_options,
            initial_data=None,
            form_key="form_manual",
            is_parse_mode=False,
            batch_mode=False
        )
    
    # ============================================================
    # TAB 2: PASTE TEXT → TAMPILKAN DI FORM EDIT
    # ============================================================
    with tab2:
        st.subheader("Paste Text CV")
        st.caption("Paste hasil copy dari Jobstreet / LinkedIn / Copilot Agent")
        
        raw_text = st.text_area("Paste teks CV di sini", height=150)
        
        col1, col2 = st.columns([1, 4])
        with col1:
            parse_btn = st.button("🔍 Parse & Tampilkan di Form", use_container_width=True, type="primary")
        
        if parse_btn and raw_text:
            with st.spinner("Memproses..."):
                parsed = parse_cv_text(raw_text)
                if parsed.get('nama'):
                    st.success(f"✅ Data ditemukan: {parsed.get('nama')}")
                    st.session_state.parsed_cv_data = parsed
                    st.session_state.show_parsed_form = True
                else:
                    st.warning("Tidak ada data terdeteksi. Pastikan formatnya 'Nama: ...'")
        
        # ============================================================
        # 🔥🔥🔥 FORM DENGAN DATA HASIL PARSE 🔥🔥🔥
        # ============================================================
        if st.session_state.show_parsed_form and st.session_state.parsed_cv_data:
            st.markdown("---")
            st.markdown("### ✏️ Review & Edit Data Sebelum Simpan")
            st.caption("Data dari hasil parse sudah diisi otomatis. Silakan edit jika diperlukan.")
            
            show_sourcing_form(
                db=db,
                user=user,
                pic_options=pic_options,
                sourcing_options=sourcing_options,
                pipeline_options=pipeline_options,
                initial_data=st.session_state.parsed_cv_data,
                form_key="form_parse_edit",
                is_parse_mode=True,
                batch_mode=False
            )
    
    # ============================================================
    # TAB 3: BATCH CV
    # ============================================================
    with tab3:
        st.subheader("Batch Paste CV (Banyak Kandidat)")
        st.caption("Paste hasil dari Copilot Agent atau multiple CV. Pisahkan dengan separator.")
        
        separator = st.text_input("Separator kandidat", value="=== CV ===")
        batch_text = st.text_area("Paste batch CV di sini", height=300)
        
        if batch_text and st.button("🚀 Proses Batch", type="primary"):
            candidates = [c.strip() for c in batch_text.split(separator) if c.strip()]
            st.info(f"📋 Ditemukan {len(candidates)} kandidat")
            
            # Simpan ke session state untuk diproses satu per satu
            st.session_state.batch_candidates = candidates
            st.session_state.batch_index = 0
            st.rerun()
        
        # Proses batch satu per satu
        if 'batch_candidates' in st.session_state and st.session_state.batch_candidates:
            idx = st.session_state.batch_index
            candidates = st.session_state.batch_candidates
            
            if idx < len(candidates):
                st.markdown("---")
                st.subheader(f"📄 Kandidat {idx+1} dari {len(candidates)}")
                
                raw_text = candidates[idx]
                parsed = parse_cv_text(raw_text)
                
                if parsed.get('nama'):
                    show_sourcing_form(
                        db=db,
                        user=user,
                        pic_options=pic_options,
                        sourcing_options=sourcing_options,
                        pipeline_options=pipeline_options,
                        initial_data=parsed,
                        form_key=f"form_batch_{idx}",
                        is_parse_mode=True,
                        batch_mode=True
                    )
                else:
                    st.warning(f"⚠️ Kandidat {idx+1} tidak terdeteksi datanya")
                    if st.button("⏭️ Lewati", key=f"skip_{idx}"):
                        st.session_state.batch_index = idx + 1
                        st.rerun()
            else:
                st.success("✅ Semua kandidat selesai diproses!")
                st.session_state.batch_candidates = []
                st.session_state.batch_index = 0


# ============================================================
# FUNGSI FORM SOURCING (REUSABLE)
# ============================================================
def show_sourcing_form(db, user, pic_options, sourcing_options, pipeline_options, 
                       initial_data=None, form_key="sourcing_form", is_parse_mode=False, batch_mode=False):
    """Form input sourcing yang reusable untuk manual, parse, dan batch"""
    
    sumber_options = sourcing_options['sumber_options']
    jenjang_options = sourcing_options['jenjang_options']
    univ_options = sourcing_options['univ_options']
    jurusan_options = sourcing_options['jurusan_options']
    fmcg_options = sourcing_options['fmcg_options']
    pipeline_opts = pipeline_options
    
    # Default values dari initial_data
    nama = initial_data.get('nama', '') if initial_data else ''
    posisi = initial_data.get('posisi', '') if initial_data else ''
    kode_unik = initial_data.get('kode_unik', '') if initial_data else ''
    hp = initial_data.get('hp', '') if initial_data else ''
    email = initial_data.get('email', '') if initial_data else ''
    sumber = initial_data.get('sumber', '') if initial_data else ''
    domisili = initial_data.get('domisili', '') if initial_data else ''
    jenjang = initial_data.get('jenjang', '') if initial_data else ''
    univ = initial_data.get('universitas', '') if initial_data else ''
    jurusan = initial_data.get('jurusan', '') if initial_data else ''
    ipk = initial_data.get('ipk', '') if initial_data else ''
    tahun_lulus = initial_data.get('tahun_lulus', '') if initial_data else ''
    last_position = initial_data.get('last_position', '') if initial_data else ''
    last_company = initial_data.get('last_company', '') if initial_data else ''
    last_tenure = initial_data.get('last_tenure', '') if initial_data else ''
    total_tenure = initial_data.get('total_tenure', '') if initial_data else ''
    fmcg = initial_data.get('fmcg', '') if initial_data else ''
    
    # Tampilkan info parsing
    if is_parse_mode and initial_data:
        detected = [k for k, v in initial_data.items() if v and k not in ['nama']]
        st.success(f"✅ Data hasil parse: **{initial_data.get('nama', '')}**")
        if detected:
            st.caption(f"📋 Field terdeteksi: {', '.join(detected)}")
    
    # --- SEARCH FPTK ---
    st.markdown("#### 🔍 Cari FPTK (Kode Unik akan mengisi posisi otomatis)")
    
    search_kode = st.text_input("Cari Kode Unik atau Posisi", key=f"search_fptk_{form_key}", placeholder="Ketik Kode Unik atau Posisi...")
    
    fptk_list = []
    fptk_map = {}
    selected_kode = kode_unik
    selected_posisi = posisi
    
    if search_kode and len(search_kode) >= 2:
        results = db.query(FPTK).filter(
            (FPTK.kode_unik.ilike(f"%{search_kode}%")) |
            (FPTK.posisi.ilike(f"%{search_kode}%"))
        ).limit(50).all()
        
        for r in results:
            display = f"{r.kode_unik} | {r.posisi} | {r.pic_recruiter}"
            fptk_list.append(display)
            fptk_map[display] = {"kode_unik": r.kode_unik, "posisi": r.posisi, "pic": r.pic_recruiter}
        
        if fptk_list:
            selected = st.selectbox("Pilih FPTK", [""] + fptk_list, key=f"select_fptk_{form_key}")
            if selected:
                data = fptk_map.get(selected)
                if data:
                    selected_kode = data["kode_unik"]
                    selected_posisi = data["posisi"]
                    # Update kode_unik & posisi untuk form
                    kode_unik = selected_kode
                    posisi = selected_posisi
                    st.success(f"✅ Terpilih: {selected_kode} - {selected_posisi}")
            else:
                # Kembali ke nilai awal
                kode_unik = initial_data.get('kode_unik', '') if initial_data else ''
                posisi = initial_data.get('posisi', '') if initial_data else ''
        else:
            st.info("Tidak ada FPTK ditemukan. Ketik minimal 2 karakter.")
    
    with st.form(form_key):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Data Kandidat")
            nama_input = st.text_input("Nama *", value=nama)
            posisi_input = st.text_input("Posisi", value=posisi)
            kode_unik_input = st.text_input("Kode Unik", value=kode_unik, 
                                           placeholder="Dari search di atas atau manual")
            pic_recruiter_input = st.selectbox("PIC Recruiter *", [""] + pic_options)
            hp_input = st.text_input("No HP", value=hp)
            email_input = st.text_input("Email", value=email)
            sumber_input = st.selectbox("Sumber *", [""] + sumber_options, 
                                       index=([""] + sumber_options).index(sumber) if sumber in sumber_options else 0)
            domisili_input = st.text_input("Domisili", value=domisili)
            
        with col2:
            st.markdown("### Pendidikan")
            jenjang_input = st.selectbox("Jenjang", [""] + jenjang_options,
                                        index=([""] + jenjang_options).index(jenjang) if jenjang in jenjang_options else 0)
            
            univ_input = st.selectbox("Universitas", [""] + univ_options,
                                     index=([""] + univ_options).index(univ) if univ in univ_options else 0)
            
            univ_lain = ""
            if univ_input == "Lainnya":
                univ_lain = st.text_input("Univ Lainnya", value=initial_data.get('univ_lain', '') if initial_data else '')
            
            jurusan_input = st.selectbox("Jurusan", [""] + jurusan_options,
                                        index=([""] + jurusan_options).index(jurusan) if jurusan in jurusan_options else 0)
            ipk_input = st.text_input("IPK", value=ipk, placeholder="Contoh: 3.50")
            
            try:
                default_tahun = int(tahun_lulus) if tahun_lulus and str(tahun_lulus).isdigit() else None
            except:
                default_tahun = None
            tahun_lulus_input = st.number_input("Tahun Lulus", min_value=1990, max_value=2030, step=1, 
                                               value=default_tahun if default_tahun else None)
            
            fmcg_input = st.selectbox("Pernah di FMCG?", [""] + fmcg_options,
                                     index=([""] + fmcg_options).index(fmcg) if fmcg in fmcg_options else 0)
        
        st.markdown("---")
        st.markdown("### Riwayat Pekerjaan")
        col1, col2 = st.columns(2)
        with col1:
            last_position_input = st.text_input("Last Position", value=last_position)
            last_company_input = st.text_input("Last Company", value=last_company)
        with col2:
            last_tenure_input = st.text_input("Last Tenure", value=last_tenure)
            total_tenure_input = st.text_input("Total Tenure", value=total_tenure)
        
        st.markdown("---")
        st.markdown("### Pipeline (Status awal)")
        
        st.markdown("#### Sourcing Freelance (Pipeline Awal)")
        col1, col2 = st.columns(2)
        with col1:
            sourcing_freelance_input = st.selectbox("Sourcing Freelance", [""] + pipeline_opts)
        with col2:
            if sourcing_freelance_input:
                tanggal_sourcing_freelance_input = st.date_input("Tanggal Sourcing Freelance", datetime.now())
            else:
                tanggal_sourcing_freelance_input = None
                st.date_input("Tanggal Sourcing Freelance", datetime.now(), disabled=True)
        
        st.markdown("#### Sourcing HR")
        col1, col2 = st.columns(2)
        with col1:
            sourcing_hr_input = st.selectbox("Sourcing HR", [""] + pipeline_opts)
        with col2:
            if sourcing_hr_input:
                tanggal_sourcing_input = st.date_input("Tanggal Sourcing HR", datetime.now())
            else:
                tanggal_sourcing_input = None
                st.date_input("Tanggal Sourcing HR", datetime.now(), disabled=True)
        
        # Tombol aksi
        col1, col2 = st.columns([1, 4])
        with col1:
            submitted = st.form_submit_button("💾 Simpan", type="primary")
        if is_parse_mode:
            with col2:
                if st.form_submit_button("🔄 Reset / Parse Ulang", type="secondary"):
                    st.session_state.parsed_cv_data = {}
                    st.session_state.show_parsed_form = False
                    st.rerun()
    
    if submitted:
        errors = []
        if not nama_input:
            errors.append("Nama wajib diisi")
        if not sumber_input:
            errors.append("Sumber wajib diisi")
        if not pic_recruiter_input:
            errors.append("PIC Recruiter wajib diisi")
        
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            try:
                # Cek duplikat
                existing = db.query(DBSourcing).filter(DBSourcing.nama == nama_input).first()
                if existing:
                    st.warning(f"⚠️ Nama '{nama_input}' sudah ada!")
                    # Tetap lanjutkan, user bisa force dengan klik tombol
                
                last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                next_no = (last_no.no + 1) if last_no and last_no.no else 1
                
                new = DBSourcing(
                    no=next_no,
                    nama=nama_input,
                    posisi=posisi_input,
                    kode_unik=kode_unik_input,
                    rekruter=pic_recruiter_input,
                    sumber_sourcing=sumber_input,
                    domisili=domisili_input,
                    jenjang_pendidikan=jenjang_input,
                    nama_universitas_top10=univ_input if univ_input != "Lainnya" else "",
                    nama_universitas_lainnya=univ_lain if univ_input == "Lainnya" else "",
                    jurusan=jurusan_input,
                    ipk=safe_int(ipk_input.replace(',', '.')) if ipk_input else None,
                    tahun_lulus=tahun_lulus_input if tahun_lulus_input and tahun_lulus_input > 0 else None,
                    nomor_hp=parse_phone(hp_input),
                    email=email_input if is_valid_email(email_input) else "",
                    last_position=last_position_input,
                    last_company=last_company_input,
                    last_tenure=last_tenure_input,
                    total_tenure=total_tenure_input,
                    pernah_di_fmcg=fmcg_input,
                    sourcing_freelance=sourcing_freelance_input if sourcing_freelance_input else None,
                    tanggal_sourcing_freelance=tanggal_sourcing_freelance_input if sourcing_freelance_input else None,
                    sourcing_hr=sourcing_hr_input if sourcing_hr_input else None,
                    tanggal_sourcing=tanggal_sourcing_input if sourcing_hr_input else None,
                    sourcing_date=datetime.now().date(),
                    source_user_id=user.id,
                    created_at=datetime.now(),
                    last_compile_action="MANUAL_INPUT"
                )
                db.add(new)
                db.commit()
                st.success(f"✅ '{nama_input}' berhasil disimpan!")
                st.balloons()
                
                # Reset jika mode parse atau batch
                if is_parse_mode:
                    st.session_state.parsed_cv_data = {}
                    st.session_state.show_parsed_form = False
                
                if batch_mode:
                    if 'batch_index' in st.session_state:
                        st.session_state.batch_index += 1
                    st.rerun()
                
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
