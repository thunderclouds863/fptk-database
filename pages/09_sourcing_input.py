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
    """Parse CV text ke dictionary fields"""
    parsed = {}
    if not raw_text:
        return parsed
    
    lines = raw_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()
            
            if 'nama' in key or 'name' in key:
                parsed['nama'] = val
            elif 'email' in key:
                parsed['email'] = val
            elif 'hp' in key or 'phone' in key or 'nomor' in key or 'no hp' in key:
                parsed['hp'] = val
            elif 'universitas' in key or 'university' in key or 'univ' in key:
                parsed['univ'] = val
            elif 'jurusan' in key or 'major' in key:
                parsed['jurusan'] = val
            elif 'ipk' in key or 'gpa' in key:
                parsed['ipk'] = val
            elif 'tahun lulus' in key or 'graduation' in key:
                parsed['tahun_lulus'] = val
            elif 'domisili' in key or 'domicile' in key or 'location' in key:
                parsed['domisili'] = val
            elif 'last position' in key or 'posisi terakhir' in key:
                parsed['last_position'] = val
            elif 'last company' in key or 'perusahaan terakhir' in key:
                parsed['last_company'] = val
            elif 'sumber' in key or 'source' in key:
                parsed['sumber'] = val
            elif 'posisi' in key or 'position' in key:
                parsed['posisi'] = val
            elif 'kode unik' in key or 'kode' in key:
                parsed['kode_unik'] = val
            elif 'tenure' in key or 'lama kerja' in key:
                parsed['total_tenure'] = val
            elif 'last tenure' in key:
                parsed['last_tenure'] = val
    
    # Fallback: kalau ga ada label 'Nama:', ambil baris pertama yang ada isinya
    if not parsed.get('nama'):
        for line in lines:
            line = line.strip()
            if line and ':' not in line and len(line) > 2:
                parsed['nama'] = line
                break
    
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
        show_manual_form(db, user, pic_options, sourcing_options, pipeline_options)
    
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
    # SEARCH FPTK
    # ============================================================
    st.markdown("---")
    st.subheader("🔍 Cari FPTK untuk Kode Unik")
    
    search_fptk = st.text_input("Cari Kode Unik atau Posisi", placeholder="Ketik keyword...")
    if search_fptk:
        results = db.query(FPTK).filter(
            (FPTK.kode_unik.ilike(f"%{search_fptk}%")) |
            (FPTK.posisi.ilike(f"%{search_fptk}%"))
        ).limit(20).all()
        
        if results:
            data = []
            for r in results:
                data.append({
                    "Kode Unik": r.kode_unik,
                    "Posisi": r.posisi,
                    "PIC": r.pic_recruiter,
                    "Status": r.status
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            st.info("📋 Copy Kode Unik ke form input di atas")
        else:
            st.warning("Tidak ada data ditemukan")


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
    univ = initial_data.get('univ', '') if initial_data else ''
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
        st.info(f"📋 Data dari parse: **{nama}**")
    
    with st.form(form_key):
        col1, col2 = st.columns(2)
        with col1:
            nama_input = st.text_input("Nama *", value=nama)
            posisi_input = st.text_input("Posisi", value=posisi)
            kode_unik_input = st.text_input("Kode Unik", value=kode_unik)
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
        
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            try:
                # Cek duplikat
                existing = db.query(DBSourcing).filter(DBSourcing.nama == nama_input).first()
                if existing:
                    st.warning(f"⚠️ Nama '{nama_input}' sudah ada!")
                    if not st.button("Tetap simpan (force)", key=f"force_{form_key}"):
                        st.stop()
                
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


# ============================================================
# FUNGSI MANUAL FORM (TAB 1)
# ============================================================
def show_manual_form(db, user, pic_options, sourcing_options, pipeline_options):
    """Form manual input sourcing (tanpa data awal)"""
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
