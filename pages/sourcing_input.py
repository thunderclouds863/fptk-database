import streamlit as st
import pandas as pd
import re
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown, User
from core.auth import get_current_user
from core.utils import normalize_key, parse_date_dmy, safe_int

def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input data kandidat sourcing manual atau dari hasil parse CV.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # LOAD MASTER DATA
    # ============================================================
    master = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
    # Extract unique values untuk dropdown
    model_options = sorted(set([m.model for m in master if m.model]))
    sumber_options = sorted(set([m.sumber_sourcing for m in master if m.sumber_sourcing]))
    jenjang_options = sorted(set([m.jenjang_pendidikan for m in master if m.jenjang_pendidikan]))
    univ_top_options = sorted(set([m.nama_universitas_top10 for m in master if m.nama_universitas_top10]))
    jurusan_options = sorted(set([m.jurusan for m in master if m.jurusan]))
    univ_tier_options = sorted(set([m.university_tier for m in master if m.university_tier]))
    ipk_tier_options = sorted(set([m.ipk_tier for m in master if m.ipk_tier]))
    fmcg_options = ["Ya", "Tidak"]
    
    # ============================================================
    # TABS
    # ============================================================
    tab1, tab2 = st.tabs(["📝 Input Manual", "📄 Parse CV Text"])
    
    # ============================================================
    # TAB 1: INPUT MANUAL
    # ============================================================
    with tab1:
        with st.form("sourcing_input_form", clear_on_submit=True):
            st.markdown("### Data Kandidat")
            
            # Cari FPTK
            col1, col2 = st.columns([3, 1])
            with col1:
                search_fptk = st.text_input("Cari Kode Unik FPTK", placeholder="Ketik Kode Unik...")
            with col2:
                if st.form_submit_button("🔍 Cari FPTK", type="secondary"):
                    if search_fptk:
                        fptk_result = db.query(FPTK).filter(FPTK.kode_unik.ilike(f"%{search_fptk}%")).first()
                        if fptk_result:
                            st.session_state['sourcing_fptk'] = fptk_result.kode_unik
                            st.session_state['sourcing_posisi'] = fptk_result.posisi
                            st.session_state['sourcing_pic'] = fptk_result.pic_recruiter
                            st.success(f"✅ FPTK ditemukan: {fptk_result.kode_unik} - {fptk_result.posisi}")
                        else:
                            st.error("FPTK tidak ditemukan")
            
            # Data Kandidat
            col1, col2 = st.columns(2)
            with col1:
                kode_unik = st.text_input("Kode Unik *", value=st.session_state.get('sourcing_fptk', ''))
                nama = st.text_input("Nama Kandidat *")
                posisi = st.text_input("Posisi", value=st.session_state.get('sourcing_posisi', ''))
                sumber = st.selectbox("Sumber Sourcing *", [""] + sumber_options)
                model = st.selectbox("Model Rekrutmen", [""] + model_options)
                rekruter = st.text_input("Rekruter", value=st.session_state.get('sourcing_pic', ''))
                sourcing_date = st.date_input("Sourcing Date *", datetime.now())
            
            with col2:
                email = st.text_input("Email")
                nomor_hp = st.text_input("Nomor HP")
                domisili = st.text_input("Domisili")
                jenjang = st.selectbox("Jenjang Pendidikan", [""] + jenjang_options)
                univ_top = st.selectbox("Universitas TOP 10", [""] + univ_top_options)
                univ_lain = st.text_input("Universitas Lainnya")
                jurusan = st.selectbox("Jurusan", [""] + jurusan_options)
                tahun_lulus = st.number_input("Tahun Lulus", min_value=1950, max_value=datetime.now().year+5, value=None, step=1)
                ipk = st.text_input("IPK", placeholder="Contoh: 3.50")
                skor_inggris = st.text_input("Skor Bahasa Inggris")
                univ_tier = st.selectbox("University Tier", [""] + univ_tier_options)
                ipk_tier = st.selectbox("IPK Tier", [""] + ipk_tier_options)
                pernah_fmcg = st.selectbox("Pernah di FMCG?", [""] + fmcg_options)
            
            # Experience
            st.markdown("### Pengalaman Kerja")
            col1, col2, col3 = st.columns(3)
            with col1:
                last_position = st.text_input("Last Position")
            with col2:
                last_company = st.text_input("Last Company")
            with col3:
                last_tenure = st.text_input("Last Tenure")
            total_tenure = st.text_input("Total Tenure")
            
            # Notes
            notes = st.text_area("Notes")
            
            st.markdown("---")
            submitted = st.form_submit_button("💾 Simpan Kandidat", type="primary")
            
            if submitted:
                errors = []
                
                if not kode_unik:
                    errors.append("Kode Unik wajib diisi")
                if not nama:
                    errors.append("Nama Kandidat wajib diisi")
                if not sumber:
                    errors.append("Sumber Sourcing wajib diisi")
                if not sourcing_date:
                    errors.append("Sourcing Date wajib diisi")
                
                # Cek duplikat
                if kode_unik and nama:
                    existing = db.query(DBSourcing).filter(
                        DBSourcing.kode_unik == kode_unik,
                        DBSourcing.nama == nama
                    ).first()
                    if existing:
                        errors.append(f"Kandidat dengan Kode Unik '{kode_unik}' dan Nama '{nama}' sudah ada!")
                
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    try:
                        # Parse IPK
                        ipk_val = None
                        if ipk:
                            try:
                                ipk_val = float(ipk.replace(',', '.'))
                            except:
                                pass
                        
                        new_sourcing = DBSourcing(
                            kode_unik=kode_unik,
                            nama=nama,
                            posisi=posisi,
                            sumber_sourcing=sumber,
                            model_rekrutmen=model,
                            rekruter=rekruter,
                            sourcing_date=sourcing_date,
                            email=email,
                            nomor_hp=nomor_hp,
                            domisili=domisili,
                            jenjang_pendidikan=jenjang,
                            nama_universitas_top10=univ_top,
                            nama_universitas_lainnya=univ_lain,
                            jurusan=jurusan,
                            tahun_lulus=tahun_lulus,
                            ipk=ipk_val,
                            skor_bahasa_inggris=skor_inggris,
                            university_tier=univ_tier,
                            ipk_tier=ipk_tier,
                            pernah_di_fmcg=pernah_fmcg,
                            last_position=last_position,
                            last_company=last_company,
                            last_tenure=last_tenure,
                            total_tenure=total_tenure,
                            notes=notes,
                            source_user_id=user.id,
                            created_at=datetime.now(),
                            last_compile_action="MANUAL_INPUT"
                        )
                        db.add(new_sourcing)
                        db.commit()
                        
                        st.success(f"✅ Kandidat berhasil disimpan!")
                        st.info(f"📋 Nama: {nama}")
                        st.info(f"📋 Kode Unik: {kode_unik}")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Error menyimpan data: {str(e)}")
                        db.rollback()
    
    # ============================================================
    # TAB 2: PARSE CV TEXT
    # ============================================================
    with tab2:
        st.markdown("### Paste CV Text")
        st.caption("Paste hasil copy dari CV / Jobstreet / LinkedIn. Sistem akan mencoba mengekstrak data.")
        
        cv_text = st.text_area("Paste CV Text di sini", height=300)
        
        col1, col2 = st.columns([1, 5])
        with col1:
            parse_btn = st.button("🔍 Parse CV", type="primary")
        
        if parse_btn and cv_text:
            # Parse CV text dengan regex sederhana
            parsed = parse_cv_text(cv_text)
            
            if parsed:
                st.success("✅ CV berhasil diparse!")
                
                # Tampilkan hasil parse
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Nama:** {parsed.get('nama', '')}")
                    st.markdown(f"**Email:** {parsed.get('email', '')}")
                    st.markdown(f"**No HP:** {parsed.get('nomor_hp', '')}")
                    st.markdown(f"**Universitas:** {parsed.get('universitas', '')}")
                    st.markdown(f"**Jurusan:** {parsed.get('jurusan', '')}")
                    st.markdown(f"**IPK:** {parsed.get('ipk', '')}")
                with col2:
                    st.markdown(f"**Tahun Lulus:** {parsed.get('tahun_lulus', '')}")
                    st.markdown(f"**Domisili:** {parsed.get('domisili', '')}")
                    st.markdown(f"**Jenjang:** {parsed.get('jenjang', '')}")
                    st.markdown(f"**Last Position:** {parsed.get('last_position', '')}")
                    st.markdown(f"**Last Company:** {parsed.get('last_company', '')}")
                
                # Auto-fill ke form (gunakan session state)
                st.info("💡 Data di atas bisa digunakan untuk mengisi form Input Manual.")
                
                # Simpan ke session state untuk dipakai di tab manual
                if st.button("📋 Gunakan Data Ini ke Form"):
                    for key, val in parsed.items():
                        st.session_state[f'cv_parsed_{key}'] = val
                    st.success("Data sudah siap! Pindah ke tab 'Input Manual' dan isi data yang kosong.")
            else:
                st.warning("Tidak ada data yang berhasil diekstrak dari CV. Silakan coba paste dengan format yang lebih lengkap.")

def parse_cv_text(text: str) -> dict:
    """Parse CV text sederhana dengan regex"""
    result = {
        "nama": "",
        "email": "",
        "nomor_hp": "",
        "universitas": "",
        "jurusan": "",
        "ipk": "",
        "tahun_lulus": "",
        "domisili": "",
        "jenjang": "",
        "last_position": "",
        "last_company": "",
    }
    
    # Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        result["email"] = email_match.group()
    
    # Phone (Indonesia)
    phone_match = re.search(r'(\+62|0)8[1-9][0-9]{6,11}', text)
    if phone_match:
        result["nomor_hp"] = phone_match.group()
    
    # Nama (cari label Nama: atau baris pertama)
    name_match = re.search(r'(?:Nama|Name|Nama Kandidat)\s*[:;]\s*([^\n]+)', text, re.IGNORECASE)
    if name_match:
        result["nama"] = name_match.group(1).strip()
    else:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            result["nama"] = lines[0][:60]  # ambil baris pertama
    
    # Universitas
    univ_match = re.search(r'(?:Universitas|University|Univ)\s*[:;]\s*([^\n]+)', text, re.IGNORECASE)
    if univ_match:
        result["universitas"] = univ_match.group(1).strip()
    
    # Jurusan
    major_match = re.search(r'(?:Jurusan|Major)\s*[:;]\s*([^\n]+)', text, re.IGNORECASE)
    if major_match:
        result["jurusan"] = major_match.group(1).strip()
    
    # IPK / GPA
    ipk_match = re.search(r'(?:IPK|GPA)\s*[:;]\s*([\d.,]+)', text, re.IGNORECASE)
    if ipk_match:
        result["ipk"] = ipk_match.group(1).replace(',', '.')
    
    # Tahun Lulus
    year_match = re.search(r'(?:Tahun Lulus|Lulus|Graduated|Class of)\s*[:;]?\s*(20[0-9]{2})', text, re.IGNORECASE)
    if year_match:
        result["tahun_lulus"] = year_match.group(1)
    
    # Domisili
    dom_match = re.search(r'(?:Domisili|Location|Kota)\s*[:;]\s*([^\n]+)', text, re.IGNORECASE)
    if dom_match:
        result["domisili"] = dom_match.group(1).strip()
    
    # Jenjang Pendidikan
    if "S1" in text or "Bachelor" in text:
        result["jenjang"] = "S1"
    elif "S2" in text or "Master" in text:
        result["jenjang"] = "S2"
    elif "D3" in text or "Diploma" in text:
        result["jenjang"] = "D3"
    elif "SMA" in text or "SMK" in text:
        result["jenjang"] = "SMA/SMK"
    
    # Last Position / Company
    pos_match = re.search(r'(?:Last Position|Posisi Terakhir|Jabatan)\s*[:;]\s*([^\n]+)', text, re.IGNORECASE)
    if pos_match:
        result["last_position"] = pos_match.group(1).strip()
    
    comp_match = re.search(r'(?:Last Company|Company Terakhir|Perusahaan Terakhir)\s*[:;]\s*([^\n]+)', text, re.IGNORECASE)
    if comp_match:
        result["last_company"] = comp_match.group(1).strip()
    
    return result
