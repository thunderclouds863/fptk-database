import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DBSourcing, FPTK, User, MasterDropdown
from core.auth import get_current_user
from core.utils import normalize_key, parse_date_dmy, safe_int, parse_phone, is_valid_email
from core.cv_parser import parse_cv_text
import io
import base64
import webbrowser

# Copilot Agent URL (sama dengan yang di VBA)
COPILOT_AGENT_URL = (
    "https://m365.cloud.microsoft/chat/"
    "?titleId=T_e0524666-839c-757c-7ef5-d5e72311417d"
    "&source=embedded-builder"
)

def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input kandidat baru ke DB Sourcing")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # Load master data
    master = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
    model_options = sorted(set([m.model for m in master if m.model])) or ["Model 1", "Model 2", "Model 3", "Model 4"]
    sumber_options = sorted(set([m.sumber_sourcing for m in master if m.sumber_sourcing])) or ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance"]
    jenjang_options = sorted(set([m.jenjang_pendidikan for m in master if m.jenjang_pendidikan])) or ["SMA/SMK", "D3", "D4", "S1", "S2"]
    univ_options = sorted(set([m.nama_universitas_top10 for m in master if m.nama_universitas_top10])) + ["Lainnya"]
    jurusan_options = sorted(set([m.jurusan for m in master if m.jurusan])) or ["Manajemen", "Akuntansi", "Teknik Industri", "Teknik Informatika", "Sistem Informasi", "Lainnya"]
    univ_tier_options = ["Top 3 PTN", "Top 10 PTN", "Top 20 PTN", "Top 10 PTS", "Lainnya"]
    ipk_tier_options = ["Lebih dari 3,5", "3,2 < IPK <= 3,5", "Kurang dari 3,2"]
    fmcg_options = ["", "Ya", "Tidak"]
    
    # Tab: Manual Input / Upload CV / Paste Text / Batch
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Manual Input", "📄 Upload CV", "📋 Paste Text", "📦 Batch CV"])
    
    # ============================================================
    # TAB 1: MANUAL INPUT
    # ============================================================
    with tab1:
        st.subheader("Manual Input Kandidat")
        with st.form("sourcing_manual_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nama = st.text_input("Nama Kandidat *")
                posisi = st.text_input("Posisi")
                kode_unik = st.text_input("Kode Unik (copy dari FPTK)", placeholder="Isi atau cari FPTK")
                
                # Button cari FPTK
                if st.button("🔍 Cari FPTK", key="search_fptk_manual"):
                    if kode_unik:
                        fptk = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
                        if fptk:
                            st.info(f"✅ FPTK ditemukan: {fptk.posisi} - {fptk.pic_recruiter}")
                            st.session_state['fptk_posisi'] = fptk.posisi
                            st.session_state['fptk_pic'] = fptk.pic_recruiter
                        else:
                            st.warning(f"❌ Kode Unik '{kode_unik}' tidak ditemukan!")
                
                # Auto-fill dari FPTK
                if st.session_state.get('fptk_posisi'):
                    posisi = st.text_input("Posisi (auto-fill)", value=st.session_state['fptk_posisi'], disabled=True)
                    pic_recruiter = st.text_input("PIC (auto-fill)", value=st.session_state['fptk_pic'], disabled=True)
                else:
                    posisi = st.text_input("Posisi")
                    pic_recruiter = st.selectbox("PIC Recruiter *", [""] + pic_options)
                
                hp = st.text_input("Nomor HP")
                email = st.text_input("Email")
                domisili = st.text_input("Domisili")
                sumber = st.selectbox("Sumber Sourcing *", [""] + sumber_options)
                model = st.selectbox("Model Rekrutmen", [""] + model_options)
            
            with col2:
                jenjang = st.selectbox("Jenjang Pendidikan", [""] + jenjang_options)
                univ_top = st.selectbox("Universitas (TOP 10)", [""] + univ_options)
                if univ_top == "Lainnya":
                    univ_lain = st.text_input("Universitas Lainnya")
                else:
                    univ_lain = ""
                jurusan = st.selectbox("Jurusan", [""] + jurusan_options)
                tahun_lulus = st.number_input("Tahun Lulus", min_value=1990, max_value=datetime.now().year + 5, step=1, value=None)
                ipk = st.text_input("IPK", placeholder="Contoh: 3.50")
                skor_inggris = st.text_input("Skor Bahasa Inggris")
                univ_tier = st.selectbox("University Tier", [""] + univ_tier_options)
                ipk_tier = st.selectbox("IPK Tier", [""] + ipk_tier_options)
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
            sourcing_hr = st.selectbox("Sourcing HR", ["", "V", "X"])
            tanggal_sourcing = st.date_input("Tanggal Sourcing", datetime.now())
            
            submitted = st.form_submit_button("💾 Simpan Kandidat", type="primary")
        
        if submitted:
            errors = []
            if not nama:
                errors.append("Nama Kandidat wajib diisi")
            if not sumber:
                errors.append("Sumber Sourcing wajib diisi")
            if not pic_recruiter:
                errors.append("PIC Recruiter wajib diisi")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                try:
                    # Cek duplikat nama
                    existing = db.query(DBSourcing).filter(DBSourcing.nama == nama).first()
                    if existing:
                        st.warning(f"⚠️ Nama '{nama}' sudah ada di database!")
                        if not st.button("Tetap simpan (force)"):
                            st.stop()
                    
                    # Hitung No urut
                    last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                    next_no = (last_no.no + 1) if last_no and last_no.no else 1
                    
                    new_sourcing = DBSourcing(
                        no=next_no,
                        nama=nama,
                        posisi=posisi or st.session_state.get('fptk_posisi', ''),
                        kode_unik=kode_unik,
                        rekruter=pic_recruiter,
                        sumber_sourcing=sumber,
                        model_rekrutmen=model,
                        jenjang_pendidikan=jenjang,
                        nama_universitas_top10=univ_top if univ_top != "Lainnya" else "",
                        nama_universitas_lainnya=univ_lain if univ_top == "Lainnya" else "",
                        jurusan=jurusan,
                        tahun_lulus=tahun_lulus if tahun_lulus and tahun_lulus > 0 else None,
                        ipk=safe_int(ipk.replace(',', '.')) if ipk else None,
                        skor_bahasa_inggris=skor_inggris,
                        university_tier=univ_tier,
                        ipk_tier=ipk_tier,
                        nomor_hp=parse_phone(hp),
                        email=email if is_valid_email(email) else "",
                        domisili=domisili,
                        last_position=last_position,
                        last_company=last_company,
                        last_tenure=last_tenure,
                        total_tenure=total_tenure,
                        pernah_di_fmcg=fmcg,
                        sourcing_hr=sourcing_hr if sourcing_hr else None,
                        tanggal_sourcing=tanggal_sourcing if sourcing_hr else None,
                        sourcing_date=datetime.now().date(),
                        source_user_id=user.id,
                        created_at=datetime.now(),
                        last_compile_action="MANUAL_INPUT"
                    )
                    db.add(new_sourcing)
                    db.commit()
                    st.success(f"✅ Kandidat '{nama}' berhasil disimpan!")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
    
    # ============================================================
    # TAB 2: UPLOAD CV
    # ============================================================
    with tab2:
        st.subheader("Upload File CV (PDF / Image)")
        uploaded_file = st.file_uploader("Pilih file CV", type=["pdf", "jpg", "jpeg", "png", "bmp", "gif"])
        
        if uploaded_file:
            st.info(f"📄 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")
            
            col1, col2 = st.columns([1, 4])
            with col1:
                parse_btn = st.button("🔍 Parse CV", use_container_width=True)
            
            if parse_btn:
                with st.spinner("Memproses CV..."):
                    try:
                        file_bytes = uploaded_file.read()
                        
                        from core.cv_parser import parse_cv_text
                        text = ""
                        if uploaded_file.type == "application/pdf":
                            import pdfplumber
                            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                        else:
                            # Image -> OCR
                            try:
                                import pytesseract
                                from PIL import Image
                                img = Image.open(io.BytesIO(file_bytes))
                                text = pytesseract.image_to_string(img, lang='ind')
                            except:
                                st.warning("⚠️ OCR tidak tersedia. Silakan gunakan Paste Text.")
                                text = ""
                        
                        if text and len(text.strip()) > 50:
                            parsed = parse_cv_text(text)
                            st.success("✅ CV berhasil diparse!")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text_input("Nama", value=parsed.get('nama', ''))
                                st.text_input("Email", value=parsed.get('email', ''))
                                st.text_input("Nomor HP", value=parsed.get('nomor_hp', ''))
                                st.text_input("Domisili", value=parsed.get('domisili', ''))
                            with col2:
                                st.text_input("Universitas", value=parsed.get('universitas', ''))
                                st.text_input("Jurusan", value=parsed.get('jurusan', ''))
                                st.text_input("IPK", value=parsed.get('ipk', ''))
                                st.text_input("Tahun Lulus", value=parsed.get('tahun_lulus', ''))
                            
                            if st.button("💾 Simpan Kandidat", key="save_from_upload"):
                                st.success("Data siap disimpan ke form manual!")
                        else:
                            st.warning("Tidak ada text yang terbaca. Silakan gunakan Paste Text.")
                    except Exception as e:
                        st.error(f"❌ Error parsing CV: {str(e)}")
    
    # ============================================================
    # TAB 3: PASTE TEXT (DENGAN COPILOT AGENT)
    # ============================================================
    with tab3:
        st.subheader("Paste Text CV (dari Jobstreet / LinkedIn / PDF text)")
        st.caption("Copy teks CV lalu paste di box di bawah. Sistem akan otomatis mengekstrak informasi.")
        
        # ========================================================
        # COPILOT AGENT BUTTON (seperti di VBA frmPasteCVText)
        # ========================================================
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("**💡 Tips:** Untuk CV gambar/PDF scan, gunakan Copilot Agent untuk parsing.")
        with col2:
            if st.button("🤖 Buka Copilot Agent", use_container_width=True, type="secondary"):
                webbrowser.open(COPILOT_AGENT_URL)
                st.success("✅ Copilot Agent dibuka di tab baru!")
                st.info("1. Upload CV ke Copilot Agent")
                st.info("2. Copy hasil parsing")
                st.info("3. Paste di box di bawah")
        
        st.markdown("---")
        
        raw_text = st.text_area("Paste teks CV di sini", height=200, key="paste_text_area")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if raw_text and st.button("🔍 Parse Text", key="parse_text", use_container_width=True):
                from core.cv_parser import parse_cv_text
                parsed = parse_cv_text(raw_text)
                
                if any(parsed.values()):
                    st.success("✅ Text berhasil diparse!")
                    
                    # Auto-fill form
                    with st.form("auto_fill_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            nama = st.text_input("Nama", value=parsed.get('nama', ''))
                            email = st.text_input("Email", value=parsed.get('email', ''))
                            hp = st.text_input("Nomor HP", value=parsed.get('nomor_hp', ''))
                            domisili = st.text_input("Domisili", value=parsed.get('domisili', ''))
                            universitas = st.text_input("Universitas", value=parsed.get('universitas', ''))
                            jurusan = st.text_input("Jurusan", value=parsed.get('jurusan', ''))
                        with col2:
                            ipk = st.text_input("IPK", value=parsed.get('ipk', ''))
                            tahun_lulus = st.text_input("Tahun Lulus", value=parsed.get('tahun_lulus', ''))
                            jenjang = st.selectbox("Jenjang Pendidikan", [""] + jenjang_options, index=0)
                            last_position = st.text_input("Last Position", value=parsed.get('last_position', ''))
                            last_company = st.text_input("Last Company", value=parsed.get('last_company', ''))
                            fmcg = st.selectbox("Pernah di FMCG?", [""] + fmcg_options, index=0)
                        
                        if st.form_submit_button("💾 Simpan Kandidat", type="primary"):
                            # Proses simpan
                            errors = []
                            if not nama:
                                errors.append("Nama wajib diisi")
                            if errors:
                                for err in errors:
                                    st.error(f"❌ {err}")
                            else:
                                try:
                                    last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                                    next_no = (last_no.no + 1) if last_no and last_no.no else 1
                                    
                                    new_sourcing = DBSourcing(
                                        no=next_no,
                                        nama=nama,
                                        email=email,
                                        nomor_hp=parse_phone(hp),
                                        domisili=domisili,
                                        nama_universitas_top10=universitas,
                                        jurusan=jurusan,
                                        ipk=safe_int(ipk.replace(',', '.')) if ipk else None,
                                        tahun_lulus=tahun_lulus if tahun_lulus and str(tahun_lulus).isdigit() else None,
                                        rekruter=user.pic_recruiter,
                                        sourcing_date=datetime.now().date(),
                                        source_user_id=user.id,
                                        created_at=datetime.now()
                                    )
                                    db.add(new_sourcing)
                                    db.commit()
                                    st.success(f"✅ Kandidat '{nama}' berhasil disimpan!")
                                    st.balloons()
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                                    db.rollback()
                else:
                    st.warning("Tidak ada data yang terdeteksi. Coba paste ulang.")
    
    # ============================================================
    # TAB 4: BATCH CV (DENGAN COPILOT AGENT)
    # ============================================================
    with tab4:
        st.subheader("Batch Paste CV (Banyak Kandidat)")
        st.caption("Paste teks dari Copilot Agent atau hasil parse multiple CV. Pisahkan dengan separator.")
        
        # ========================================================
        # COPILOT AGENT BUTTON (seperti di VBA frmBatchPasteCV)
        # ========================================================
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("**💡 Tips:** Gunakan Copilot Agent untuk parsing CV gambar/PDF scan secara batch.")
        with col2:
            if st.button("🤖 Copilot Agent", key="copilot_batch", use_container_width=True, type="secondary"):
                webbrowser.open(COPILOT_AGENT_URL)
                st.success("✅ Copilot Agent dibuka di tab baru!")
                st.info("1. Upload CV ke Copilot Agent (bisa multiple)")
                st.info("2. Copy hasil parsing")
                st.info("3. Paste di box di bawah")
        
        st.markdown("---")
        
        separator = st.text_input("Separator kandidat", value="=== CV ===")
        batch_text = st.text_area("Paste batch CV di sini", height=300, key="batch_text_area")
        
        if batch_text and st.button("🚀 Proses Batch", key="process_batch", type="primary"):
            # Split berdasarkan separator
            candidates = batch_text.split(separator)
            candidates = [c.strip() for c in candidates if c.strip()]
            
            st.info(f"📋 Ditemukan {len(candidates)} kandidat")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = {"success": 0, "failed": 0}
            
            from core.cv_parser import parse_cv_text
            
            for i, text in enumerate(candidates):
                status_text.text(f"Memproses kandidat {i+1}/{len(candidates)}")
                parsed = parse_cv_text(text)
                
                if parsed.get('nama'):
                    try:
                        last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                        next_no = (last_no.no + 1) if last_no and last_no.no else 1
                        
                        new_sourcing = DBSourcing(
                            no=next_no,
                            nama=parsed.get('nama', ''),
                            email=parsed.get('email', ''),
                            nomor_hp=parse_phone(parsed.get('nomor_hp', '')),
                            domisili=parsed.get('domisili', ''),
                            nama_universitas_top10=parsed.get('universitas', ''),
                            jurusan=parsed.get('jurusan', ''),
                            ipk=safe_int(parsed.get('ipk', '').replace(',', '.')),
                            tahun_lulus=parsed.get('tahun_lulus') if parsed.get('tahun_lulus') else None,
                            rekruter=user.pic_recruiter,
                            sourcing_date=datetime.now().date(),
                            source_user_id=user.id,
                            created_at=datetime.now()
                        )
                        db.add(new_sourcing)
                        db.commit()
                        results["success"] += 1
                    except Exception as e:
                        results["failed"] += 1
                        st.warning(f"❌ Gagal simpan: {parsed.get('nama')} - {str(e)}")
                        db.rollback()
                else:
                    results["failed"] += 1
                
                progress_bar.progress((i + 1) / len(candidates))
            
            status_text.text("Selesai!")
            st.success(f"✅ Batch selesai! Berhasil: {results['success']}, Gagal: {results['failed']}")
