import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user
from core.utils import safe_int, parse_phone, is_valid_email
import time

COPILOT_AGENT_URL = "https://m365.cloud.microsoft/chat/?titleId=T_e0524666-839c-757c-7ef5-d5e72311417d&source=embedded-builder"


# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_data(ttl=3600)
def get_master_options_sourcing(_db):
    """Mengambil semua opsi dari MasterDropdown untuk Sourcing - cache 1 jam"""
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
    """Mengembalikan opsi statis untuk sourcing - cache 1 jam"""
    return {
        'sumber_options': ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance", "Lainnya"],
        'jenjang_options': ["SMA/SMK", "D3", "D4", "S1", "S2"],
        'univ_options': ["Universitas Indonesia", "Universitas Gadjah Mada", "Institut Teknologi Bandung", "Universitas Airlangga", "Universitas Padjadjaran", "Universitas Diponegoro", "Universitas Brawijaya", "Institut Pertanian Bogor", "Universitas Sebelas Maret", "Telkom University", "Lainnya"],
        'jurusan_options': ["Manajemen", "Akuntansi", "Teknik Industri", "Teknik Informatika", "Sistem Informasi", "Psikologi", "Ilmu Komunikasi", "Hukum", "Ekonomi", "Lainnya"],
        'fmcg_options': ["", "Ya", "Tidak"],
        'pipeline_options': ["", "V", "X"],
        'status_options': ["", "V", "X"]
    }


@st.cache_data(ttl=3600)
def get_pipeline_stages():
    """Pipeline stages untuk sourcing - cache 1 jam"""
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


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input kandidat baru ke DB Sourcing")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # ============================================================
    # 🔥🔥🔥 LOAD FROM CACHE 🔥🔥🔥
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
        with st.form("form_manual"):
            col1, col2 = st.columns(2)
            with col1:
                nama = st.text_input("Nama *")
                posisi = st.text_input("Posisi")
                kode_unik = st.text_input("Kode Unik")
                pic_recruiter = st.selectbox("PIC Recruiter *", [""] + pic_options)
                hp = st.text_input("No HP")
                email = st.text_input("Email")
                sumber = st.selectbox("Sumber *", [""] + sumber_options)
                domisili = st.text_input("Domisili")
                
            with col2:
                jenjang = st.selectbox("Jenjang", [""] + jenjang_options)
                univ = st.selectbox("Universitas", [""] + univ_options)
                univ_lain = st.text_input("Univ Lainnya") if univ == "Lainnya" else ""
                jurusan = st.selectbox("Jurusan", [""] + jurusan_options)
                ipk = st.text_input("IPK", placeholder="Contoh: 3.50")
                tahun_lulus = st.number_input("Tahun Lulus", min_value=1990, max_value=2030, step=1, value=None)
                fmcg = st.selectbox("Pernah di FMCG?", [""] + fmcg_options)
            
            st.markdown("---")
            st.markdown("### Riwayat Pekerjaan")
            col1, col2 = st.columns(2)
            with col1:
                last_position = st.text_input("Last Position")
                last_company = st.text_input("Last Company")
            with col2:
                last_tenure = st.text_input("Last Tenure")
                total_tenure = st.text_input("Total Tenure")
            
            st.markdown("---")
            st.markdown("### Pipeline (Status awal)")
            
            # 🔥🔥🔥 SOURCING FREELANCE - PIPELINE AWAL 🔥🔥🔥
            st.markdown("#### Sourcing Freelance (Pipeline Awal)")
            col1, col2 = st.columns(2)
            with col1:
                sourcing_freelance = st.selectbox("Sourcing Freelance", [""] + pipeline_options)
            with col2:
                if sourcing_freelance:
                    tanggal_sourcing_freelance = st.date_input("Tanggal Sourcing Freelance", datetime.now())
                else:
                    tanggal_sourcing_freelance = None
                    st.date_input("Tanggal Sourcing Freelance", datetime.now(), disabled=True)
            
            st.markdown("#### Sourcing HR")
            col1, col2 = st.columns(2)
            with col1:
                sourcing_hr = st.selectbox("Sourcing HR", [""] + pipeline_options)
            with col2:
                if sourcing_hr:
                    tanggal_sourcing = st.date_input("Tanggal Sourcing HR", datetime.now())
                else:
                    tanggal_sourcing = None
                    st.date_input("Tanggal Sourcing HR", datetime.now(), disabled=True)
            
            submitted = st.form_submit_button("💾 Simpan Kandidat", type="primary")
        
        if submitted:
            errors = []
            if not nama:
                errors.append("Nama wajib diisi")
            if not sumber:
                errors.append("Sumber wajib diisi")
            if not pic_recruiter:
                errors.append("PIC Recruiter wajib diisi")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                try:
                    # Cek duplikat
                    existing = db.query(DBSourcing).filter(DBSourcing.nama == nama).first()
                    if existing:
                        st.warning(f"⚠️ Nama '{nama}' sudah ada!")
                        if not st.button("Tetap simpan (force)"):
                            st.stop()
                    
                    last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                    next_no = (last_no.no + 1) if last_no and last_no.no else 1
                    
                    # 🔥🔥🔥 PIPELINE LENGKAP 🔥🔥🔥
                    new = DBSourcing(
                        no=next_no,
                        nama=nama,
                        posisi=posisi,
                        kode_unik=kode_unik,
                        rekruter=pic_recruiter,
                        sumber_sourcing=sumber,
                        domisili=domisili,
                        jenjang_pendidikan=jenjang,
                        nama_universitas_top10=univ if univ != "Lainnya" else "",
                        nama_universitas_lainnya=univ_lain if univ == "Lainnya" else "",
                        jurusan=jurusan,
                        ipk=safe_int(ipk.replace(',', '.')) if ipk else None,
                        tahun_lulus=tahun_lulus if tahun_lulus and tahun_lulus > 0 else None,
                        nomor_hp=parse_phone(hp),
                        email=email if is_valid_email(email) else "",
                        last_position=last_position,
                        last_company=last_company,
                        last_tenure=last_tenure,
                        total_tenure=total_tenure,
                        pernah_di_fmcg=fmcg,
                        # 🔥🔥🔥 PIPELINE SOURCING FREELANCE 🔥🔥🔥
                        sourcing_freelance=sourcing_freelance if sourcing_freelance else None,
                        tanggal_sourcing_freelance=tanggal_sourcing_freelance if sourcing_freelance else None,
                        # 🔥🔥🔥 PIPELINE SOURCING HR 🔥🔥🔥
                        sourcing_hr=sourcing_hr if sourcing_hr else None,
                        tanggal_sourcing=tanggal_sourcing if sourcing_hr else None,
                        sourcing_date=datetime.now().date(),
                        source_user_id=user.id,
                        created_at=datetime.now(),
                        last_compile_action="MANUAL_INPUT"
                    )
                    db.add(new)
                    db.commit()
                    st.success(f"✅ '{nama}' berhasil disimpan!")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
    
    # ============================================================
    # TAB 2: PASTE TEXT
    # ============================================================
    with tab2:
        st.subheader("Paste Text CV")
        st.caption("Paste hasil copy dari Jobstreet / LinkedIn / Copilot Agent")
        
        raw_text = st.text_area("Paste teks CV di sini", height=250)
        
        col1, col2 = st.columns([1, 4])
        with col1:
            parse_btn = st.button("🔍 Parse Text", use_container_width=True, type="primary")
        
        if parse_btn and raw_text:
            with st.spinner("Memproses..."):
                parsed = {}
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
                
                if parsed.get('nama'):
                    st.success(f"✅ Data ditemukan: {parsed.get('nama')}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.json(parsed)
                    
                    with col2:
                        st.markdown("**Hasil Parse:**")
                        for k, v in parsed.items():
                            if v:
                                st.markdown(f"- **{k}:** {v}")
                    
                    if st.button("💾 Simpan dari Parse", type="primary"):
                        try:
                            last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                            next_no = (last_no.no + 1) if last_no and last_no.no else 1
                            
                            new = DBSourcing(
                                no=next_no,
                                nama=parsed.get('nama', ''),
                                email=parsed.get('email', ''),
                                nomor_hp=parse_phone(parsed.get('hp', '')),
                                domisili=parsed.get('domisili', ''),
                                nama_universitas_top10=parsed.get('univ', ''),
                                jurusan=parsed.get('jurusan', ''),
                                ipk=safe_int(parsed.get('ipk', '').replace(',', '.')),
                                tahun_lulus=parsed.get('tahun_lulus') if parsed.get('tahun_lulus') and str(parsed.get('tahun_lulus')).isdigit() else None,
                                last_position=parsed.get('last_position', ''),
                                last_company=parsed.get('last_company', ''),
                                sumber_sourcing=parsed.get('sumber', ''),
                                rekruter=user.pic_recruiter,
                                sourcing_date=datetime.now().date(),
                                source_user_id=user.id,
                                created_at=datetime.now()
                            )
                            db.add(new)
                            db.commit()
                            st.success(f"✅ '{parsed.get('nama')}' berhasil disimpan!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            db.rollback()
                else:
                    st.warning("Tidak ada data terdeteksi. Pastikan formatnya 'Nama: ...'")
    
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
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            success = 0
            failed = 0
            
            for i, text in enumerate(candidates):
                status_text.text(f"Memproses {i+1}/{len(candidates)}")
                
                nama = ""
                lines = text.split('\n')
                for line in lines:
                    if ':' in line:
                        key, val = line.split(':', 1)
                        if 'nama' in key.lower() or 'name' in key.lower():
                            nama = val.strip()
                            break
                
                if not nama:
                    for line in lines:
                        if line.strip() and ':' not in line:
                            nama = line.strip()
                            break
                
                if nama:
                    try:
                        last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                        next_no = (last_no.no + 1) if last_no and last_no.no else 1
                        
                        new = DBSourcing(
                            no=next_no,
                            nama=nama,
                            rekruter=user.pic_recruiter,
                            sourcing_date=datetime.now().date(),
                            source_user_id=user.id,
                            created_at=datetime.now()
                        )
                        db.add(new)
                        db.commit()
                        success += 1
                    except Exception as e:
                        failed += 1
                        st.warning(f"❌ Gagal: {nama} - {str(e)}")
                        db.rollback()
                else:
                    failed += 1
                
                progress_bar.progress((i + 1) / len(candidates))
            
            status_text.text("Selesai!")
            st.success(f"✅ Batch selesai! Berhasil: {success}, Gagal: {failed}")
    
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
