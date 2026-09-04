import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user
from core.utils import safe_int, parse_phone, is_valid_email
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
    """Parse CV text ke dictionary fields - IMPROVED VERSION"""
    parsed = {
        'nama': '',
        'email': '',
        'hp': '',
        'univ': '',
        'jurusan': '',
        'ipk': '',
        'tahun_lulus': '',
        'domisili': '',
        'last_position': '',
        'last_company': '',
        'last_tenure': '',
        'total_tenure': '',
        'sumber': '',
        'posisi': '',
        'kode_unik': '',
        'jenjang': '',
        'fmcg': ''
    }
    
    if not raw_text:
        return parsed
    
    lines = raw_text.split('\n')
    
    # Regex patterns
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(\+62|0)[0-9\s\-\(\)]{9,15}'
    ipk_pattern = r'([0-4][\.,]\d{1,2})'
    
    # Normalize text
    raw_text_lower = raw_text.lower()
    
    # 1. EMAIL (regex)
    email_match = re.search(email_pattern, raw_text)
    if email_match:
        parsed['email'] = email_match.group()
    
    # 2. PHONE (regex)
    phone_match = re.search(phone_pattern, raw_text)
    if phone_match:
        parsed['hp'] = re.sub(r'[\s\-\(\)]', '', phone_match.group())
    
    # 3. IPK (regex)
    ipk_match = re.search(ipk_pattern, raw_text)
    if ipk_match:
        parsed['ipk'] = ipk_match.group().replace(',', '.')
    
    # 4. TAHUN LULUS (regex)
    year_match = re.search(r'(20[0-9]{2})', raw_text)
    if year_match:
        parsed['tahun_lulus'] = year_match.group()
    
    # 5. Parse line by line for Label:Value format
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()
            
            if not val:
                continue
                
            # Nama
            if any(k in key for k in ['nama', 'name', 'full name', 'candidate name']):
                parsed['nama'] = val
            
            # Universitas
            elif any(k in key for k in ['universitas', 'university', 'univ']):
                # Normalize university name
                univ_lower = val.lower()
                if 'universitas indonesia' in univ_lower or 'university of indonesia' in univ_lower:
                    parsed['univ'] = 'Universitas Indonesia'
                elif 'universitas gadjah mada' in univ_lower or 'gadjah mada university' in univ_lower or 'ugm' in univ_lower:
                    parsed['univ'] = 'Universitas Gadjah Mada'
                elif 'institut teknologi bandung' in univ_lower or 'bandung institute of technology' in univ_lower or 'itb' in univ_lower:
                    parsed['univ'] = 'Institut Teknologi Bandung'
                elif 'universitas airlangga' in univ_lower or 'airlangga university' in univ_lower or 'unair' in univ_lower:
                    parsed['univ'] = 'Universitas Airlangga'
                elif 'universitas padjadjaran' in univ_lower or 'padjadjaran university' in univ_lower or 'unpad' in univ_lower:
                    parsed['univ'] = 'Universitas Padjadjaran'
                elif 'universitas diponegoro' in univ_lower or 'diponegoro university' in univ_lower or 'undip' in univ_lower:
                    parsed['univ'] = 'Universitas Diponegoro'
                elif 'universitas brawijaya' in univ_lower or 'brawijaya university' in univ_lower:
                    parsed['univ'] = 'Universitas Brawijaya'
                elif 'institut pertanian bogor' in univ_lower or 'bogor agricultural university' in univ_lower or 'ipb' in univ_lower:
                    parsed['univ'] = 'Institut Pertanian Bogor'
                elif 'universitas sebelas maret' in univ_lower or 'sebelas maret university' in univ_lower or 'uns' in univ_lower:
                    parsed['univ'] = 'Universitas Sebelas Maret'
                elif 'telkom university' in univ_lower or 'universitas telkom' in univ_lower:
                    parsed['univ'] = 'Telkom University'
                else:
                    # Capitalize each word
                    parsed['univ'] = ' '.join([w.capitalize() for w in val.split()])
            
            # Jenjang
            elif any(k in key for k in ['jenjang', 'education', 'level']):
                if 's1' in val.lower() or 'bachelor' in val.lower() or 'sarjana' in val.lower():
                    parsed['jenjang'] = 'S1'
                elif 's2' in val.lower() or 'master' in val.lower() or 'magister' in val.lower():
                    parsed['jenjang'] = 'S2'
                elif 'd3' in val.lower() or 'diploma 3' in val.lower():
                    parsed['jenjang'] = 'D3'
                elif 'd4' in val.lower() or 'diploma 4' in val.lower():
                    parsed['jenjang'] = 'D4'
                elif 'smk' in val.lower() or 'vocational' in val.lower():
                    parsed['jenjang'] = 'SMK'
                elif 'sma' in val.lower() or 'high school' in val.lower():
                    parsed['jenjang'] = 'SMA/SMK'
                else:
                    parsed['jenjang'] = val
            
            # Jurusan
            elif any(k in key for k in ['jurusan', 'major']):
                parsed['jurusan'] = val
            
            # Domisili
            elif any(k in key for k in ['domisili', 'domicile', 'location', 'kota', 'city']):
                parsed['domisili'] = val
            
            # HP / Phone
            elif any(k in key for k in ['hp', 'phone', 'nomor', 'no hp', 'no telp']):
                parsed['hp'] = re.sub(r'[\s\-\(\)]', '', val)
            
            # Last Position
            elif any(k in key for k in ['last position', 'posisi terakhir']):
                parsed['last_position'] = val
            
            # Last Company
            elif any(k in key for k in ['last company', 'perusahaan terakhir', 'company']):
                parsed['last_company'] = val
            
            # Last Tenure
            elif any(k in key for k in ['last tenure', 'tenure last']):
                parsed['last_tenure'] = val
            
            # Total Tenure
            elif any(k in key for k in ['total tenure', 'tenure', 'lama kerja', 'pengalaman']):
                parsed['total_tenure'] = val
            
            # Sumber
            elif any(k in key for k in ['sumber', 'source']):
                parsed['sumber'] = val
            
            # FMCG
            elif any(k in key for k in ['fmcg', 'pernah di fmcg']):
                val_lower = val.lower()
                if 'ya' in val_lower or 'yes' in val_lower or 'y' in val_lower:
                    parsed['fmcg'] = 'Ya'
                elif 'tidak' in val_lower or 'no' in val_lower or 'n' in val_lower:
                    parsed['fmcg'] = 'Tidak'
                else:
                    parsed['fmcg'] = val
            
            # Posisi FPTK
            elif any(k in key for k in ['posisi fptk', 'fptk posisi']):
                parsed['posisi'] = val
            
            # Kode Unik
            elif any(k in key for k in ['kode unik', 'unique code']):
                parsed['kode_unik'] = val
    
    # 6. Fallback: jika Nama kosong, ambil baris pertama yang ada isinya
    if not parsed['nama']:
        for line in lines:
            line = line.strip()
            if line and ':' not in line and len(line) > 2 and not line.startswith('http'):
                parsed['nama'] = line
                break
    
    # 7. Detect Jenjang from text if not found
    if not parsed['jenjang']:
        text_lower = raw_text.lower()
        if 's1' in text_lower or 'bachelor' in text_lower or 'sarjana' in text_lower:
            parsed['jenjang'] = 'S1'
        elif 's2' in text_lower or 'master' in text_lower or 'magister' in text_lower:
            parsed['jenjang'] = 'S2'
        elif 'd3' in text_lower or 'diploma 3' in text_lower:
            parsed['jenjang'] = 'D3'
        elif 'smk' in text_lower or 'vocational' in text_lower:
            parsed['jenjang'] = 'SMK'
        elif 'sma' in text_lower or 'high school' in text_lower:
            parsed['jenjang'] = 'SMA/SMK'
    
    # 8. Detect FMCG from text if not found
    if not parsed['fmcg']:
        text_lower = raw_text.lower()
        if 'fmcg' in text_lower:
            if 'ya' in text_lower or 'yes' in text_lower:
                parsed['fmcg'] = 'Ya'
            elif 'tidak' in text_lower or 'no' in text_lower:
                parsed['fmcg'] = 'Tidak'
    
    return parsed


def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input kandidat baru ke DB Sourcing")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # Load master data
    with st.spinner("📋 Memuat data..."):
        master_options = get_master_options_sourcing(db)
        sourcing_options = get_sourcing_options()
        pipeline_stages = get_pipeline_stages()
        
        # Load FPTK for dropdown
        fptk_list = db.query(FPTK).filter(FPTK.status == 'OP').order_by(FPTK.kode_unik).all()
        fptk_options = [(f.kode_unik, f.posisi, f.pic_recruiter) for f in fptk_list]
    
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
    # TAB 1: MANUAL INPUT
    # ============================================================
    with tab1:
        st.subheader("Manual Input Kandidat")
        show_manual_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options)
    
    # ============================================================
    # TAB 2: PASTE TEXT
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
        # FORM DENGAN DATA HASIL PARSE
        # ============================================================
        if st.session_state.show_parsed_form and st.session_state.parsed_cv_data:
            st.markdown("---")
            st.markdown("### ✏️ Review & Edit Data Sebelum Simpan")
            st.caption("Data dari hasil parse sudah diisi otomatis. Silakan edit jika diperlukan.")
            
            show_sourcing_form(
                db=db,
                user=user,
                pic_options=pic_options,
                fptk_options=fptk_options,
                sourcing_options=sourcing_options,
                pipeline_options=pipeline_options,
                initial_data=st.session_state.parsed_cv_data,
                form_key="form_parse_edit",
                is_parse_mode=True
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
                        fptk_options=fptk_options,
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
def show_sourcing_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options, 
                       initial_data=None, form_key="sourcing_form", is_parse_mode=False, batch_mode=False):
    """Form input sourcing yang reusable untuk manual, parse, dan batch"""
    
    sumber_options = sourcing_options['sumber_options']
    jenjang_options = sourcing_options['jenjang_options']
    univ_options = sourcing_options['univ_options']
    jurusan_options = sourcing_options['jurusan_options']
    fmcg_options = sourcing_options['fmcg_options']
    pipeline_opts = pipeline_options
    
    # ============================================================
    # AMBIL DATA DARI INITIAL_DATA (HASIL PARSE)
    # ============================================================
    nama = initial_data.get('nama', '') if initial_data else ''
    email = initial_data.get('email', '') if initial_data else ''
    hp = initial_data.get('hp', '') if initial_data else ''
    univ = initial_data.get('univ', '') if initial_data else ''
    jurusan = initial_data.get('jurusan', '') if initial_data else ''
    ipk = initial_data.get('ipk', '') if initial_data else ''
    tahun_lulus = initial_data.get('tahun_lulus', '') if initial_data else ''
    domisili = initial_data.get('domisili', '') if initial_data else ''
    jenjang = initial_data.get('jenjang', '') if initial_data else ''
    last_position = initial_data.get('last_position', '') if initial_data else ''
    last_company = initial_data.get('last_company', '') if initial_data else ''
    last_tenure = initial_data.get('last_tenure', '') if initial_data else ''
    total_tenure = initial_data.get('total_tenure', '') if initial_data else ''
    fmcg = initial_data.get('fmcg', '') if initial_data else ''
    sumber = initial_data.get('sumber', '') if initial_data else ''
    posisi = initial_data.get('posisi', '') if initial_data else ''
    kode_unik = initial_data.get('kode_unik', '') if initial_data else ''
    
    # ============================================================
    # FPTK DROPDOWN
    # ============================================================
    fptk_display = []
    fptk_map = {}
    fptk_posisi_map = {}
    for kode, pos, pic in fptk_options:
        display = f"{kode} - {pos[:50]}"
        fptk_display.append(display)
        fptk_map[display] = kode
        fptk_posisi_map[display] = pos
    
    # Cari default index
    default_fptk_index = 0
    if kode_unik or posisi:
        for idx, (kode, pos, pic) in enumerate(fptk_options):
            if kode_unik and kode == kode_unik:
                default_fptk_index = idx
                break
            if posisi and pos == pos:
                default_fptk_index = idx
                break
    
    # Tampilkan info parsing
    if is_parse_mode and initial_data:
        st.info(f"📋 Data dari parse: **{nama}**")
    
    with st.form(form_key):
        col1, col2 = st.columns(2)
        with col1:
            nama_input = st.text_input("Nama *", value=nama)
            
            # FPTK DROPDOWN (bukan free text)
            if fptk_display:
                selected_fptk = st.selectbox(
                    "Pilih FPTK (Kode Unik - Posisi)",
                    fptk_display,
                    index=min(default_fptk_index, len(fptk_display)-1)
                )
                kode_unik_input = fptk_map.get(selected_fptk, '')
                posisi_input = fptk_posisi_map.get(selected_fptk, '')
                
                st.text_input("Kode Unik (auto)", value=kode_unik_input, disabled=True)
                st.text_input("Posisi (auto)", value=posisi_input, disabled=True)
            else:
                st.warning("⚠️ Tidak ada FPTK OP yang tersedia. Buat FPTK dulu.")
                kode_unik_input = ''
                posisi_input = ''
                selected_fptk = None
            
            pic_recruiter_input = st.selectbox("PIC Recruiter *", [""] + pic_options)
            hp_input = st.text_input("No HP", value=hp)
            email_input = st.text_input("Email", value=email)
            sumber_input = st.selectbox("Sumber *", [""] + sumber_options, 
                                       index=([""] + sumber_options).index(sumber) if sumber in sumber_options else 0)
            domisili_input = st.text_input("Domisili", value=domisili)
            
        with col2:
            jenjang_input = st.selectbox("Jenjang", [""] + jenjang_options,
                                        index=([""] + jenjang_options).index(jenjang) if jenjang in jenjang_options else 0)
            
            univ_input = st.selectbox("Universitas", [""] + univ_options,
                                     index=([""] + univ_options).index(univ) if univ in univ_options else 0)
            
            if univ_input == "Lainnya":
                univ_lain = st.text_input("Univ Lainnya", value=initial_data.get('univ_lain', '') if initial_data else '')
            else:
                univ_lain = ""
            
            jurusan_input = st.selectbox("Jurusan", [""] + jurusan_options,
                                        index=([""] + jurusan_options).index(jurusan) if jurusan in jurusan_options else 0)
            ipk_input = st.text_input("IPK", value=ipk, placeholder="Contoh: 3.50")
            
            try:
                default_tahun = int(tahun_lulus) if tahun_lulus and str(tahun_lulus).isdigit() else None
            except:
                default_tahun = None
            tahun_lulus_input = st.number_input("Tahun Lulus", min_value=1990, max_value=2030, step=1, 
                                               value=default_tahun)
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
        if not fptk_display:
            errors.append("Tidak ada FPTK OP yang tersedia")
        elif not selected_fptk:
            errors.append("Pilih FPTK")
        
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            try:
                # Cek duplikat
                existing = db.query(DBSourcing).filter(DBSourcing.nama == nama_input).first()
                if existing:
                    st.warning(f"⚠️ Nama '{nama_input}' sudah ada!")
                
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
                    nomor_hp=hp_input,
                    email=email_input,
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


# ============================================================
# FUNGSI MANUAL FORM (TAB 1)
# ============================================================
def show_manual_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options):
    """Form manual input sourcing (tanpa data awal)"""
    show_sourcing_form(
        db=db,
        user=user,
        pic_options=pic_options,
        fptk_options=fptk_options,
        sourcing_options=sourcing_options,
        pipeline_options=pipeline_options,
        initial_data=None,
        form_key="form_manual",
        is_parse_mode=False,
        batch_mode=False
    )
