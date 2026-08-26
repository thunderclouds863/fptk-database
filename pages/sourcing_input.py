import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user
from core.utils import safe_int, parse_phone, is_valid_email
import webbrowser

COPILOT_AGENT_URL = "https://m365.cloud.microsoft/chat/?titleId=T_e0524666-839c-757c-7ef5-d5e72311417d&source=embedded-builder"

def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # Load master data
    master = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
    pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
    sumber_options = ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance"]
    jenjang_options = ["SMA/SMK", "D3", "D4", "S1", "S2"]
    univ_options = ["Universitas Indonesia", "Universitas Gadjah Mada", "Institut Teknologi Bandung", "Universitas Airlangga", "Universitas Padjadjaran", "Universitas Diponegoro", "Universitas Brawijaya", "Institut Pertanian Bogor", "Universitas Sebelas Maret", "Telkom University", "Lainnya"]
    jurusan_options = ["Manajemen", "Akuntansi", "Teknik Industri", "Teknik Informatika", "Sistem Informasi", "Psikologi", "Ilmu Komunikasi", "Lainnya"]
    fmcg_options = ["", "Ya", "Tidak"]
    
    tab1, tab2, tab3 = st.tabs(["📝 Manual Input", "📋 Paste Text", "📦 Batch CV"])
    
    # ============================================================
    # TAB 1: MANUAL INPUT
    # ============================================================
    with tab1:
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
                
            with col2:
                jenjang = st.selectbox("Jenjang", [""] + jenjang_options)
                univ = st.selectbox("Universitas", [""] + univ_options)
                univ_lain = st.text_input("Univ Lainnya") if univ == "Lainnya" else ""
                jurusan = st.selectbox("Jurusan", [""] + jurusan_options)
                ipk = st.text_input("IPK")
                tahun_lulus = st.number_input("Tahun Lulus", min_value=1990, max_value=2030, step=1, value=None)
                fmcg = st.selectbox("Pernah di FMCG?", [""] + fmcg_options)
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                last_position = st.text_input("Last Position")
                last_company = st.text_input("Last Company")
            with col2:
                last_tenure = st.text_input("Last Tenure")
                total_tenure = st.text_input("Total Tenure")
            
            submitted = st.form_submit_button("💾 Simpan", type="primary")
        
        if submitted:
            if not nama:
                st.error("Nama wajib diisi")
            elif not sumber:
                st.error("Sumber wajib diisi")
            elif not pic_recruiter:
                st.error("PIC Recruiter wajib diisi")
            else:
                try:
                    last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                    next_no = (last_no.no + 1) if last_no and last_no.no else 1
                    
                    new = DBSourcing(
                        no=next_no,
                        nama=nama,
                        posisi=posisi,
                        kode_unik=kode_unik,
                        rekruter=pic_recruiter,
                        sumber_sourcing=sumber,
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
                        sourcing_date=datetime.now().date(),
                        source_user_id=user.id,
                        created_at=datetime.now()
                    )
                    db.add(new)
                    db.commit()
                    st.success(f"✅ '{nama}' berhasil disimpan!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    db.rollback()
    
    # ============================================================
    # TAB 2: PASTE TEXT
    # ============================================================
    with tab2:
        st.caption("Paste teks CV dari Jobstreet/LinkedIn/Copilot")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("💡 **Tips:** Untuk CV gambar/PDF scan, gunakan Copilot Agent")
        with col2:
            if st.button("🤖 Copilot", use_container_width=True):
                webbrowser.open(COPILOT_AGENT_URL)
                st.success("Copilot Agent dibuka!")
        
        raw_text = st.text_area("Paste teks CV", height=200)
        
        if raw_text and st.button("🔍 Parse & Simpan", type="primary"):
            # Simple parsing
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
                    elif 'hp' in key or 'phone' in key or 'nomor' in key:
                        parsed['hp'] = val
                    elif 'universitas' in key or 'university' in key:
                        parsed['univ'] = val
                    elif 'jurusan' in key or 'major' in key:
                        parsed['jurusan'] = val
                    elif 'ipk' in key or 'gpa' in key:
                        parsed['ipk'] = val
            
            if parsed.get('nama'):
                st.success(f"✅ Data ditemukan: {parsed.get('nama')}")
                st.json(parsed)
                
                if st.button("💾 Simpan dari Parse"):
                    try:
                        last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                        next_no = (last_no.no + 1) if last_no and last_no.no else 1
                        
                        new = DBSourcing(
                            no=next_no,
                            nama=parsed.get('nama', ''),
                            email=parsed.get('email', ''),
                            nomor_hp=parse_phone(parsed.get('hp', '')),
                            nama_universitas_top10=parsed.get('univ', ''),
                            jurusan=parsed.get('jurusan', ''),
                            ipk=safe_int(parsed.get('ipk', '').replace(',', '.')),
                            rekruter=user.pic_recruiter,
                            sourcing_date=datetime.now().date(),
                            source_user_id=user.id,
                            created_at=datetime.now()
                        )
                        db.add(new)
                        db.commit()
                        st.success("✅ Data tersimpan!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        db.rollback()
            else:
                st.warning("Tidak ada data terdeteksi. Coba format 'Nama: ...'")
    
    # ============================================================
    # TAB 3: BATCH CV
    # ============================================================
    with tab3:
        st.caption("Paste multiple CV, pisahkan dengan '=== CV ==='")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("💡 Gunakan Copilot Agent untuk batch parsing")
        with col2:
            if st.button("🤖 Copilot Batch", use_container_width=True):
                webbrowser.open(COPILOT_AGENT_URL)
                st.success("Copilot Agent dibuka!")
        
        separator = st.text_input("Separator", value="=== CV ===")
        batch_text = st.text_area("Paste batch CV", height=300)
        
        if batch_text and st.button("🚀 Proses Batch", type="primary"):
            candidates = [c.strip() for c in batch_text.split(separator) if c.strip()]
            st.info(f"Ditemukan {len(candidates)} kandidat")
            
            success = 0
            for i, text in enumerate(candidates):
                lines = text.split('\n')
                nama = ""
                for line in lines:
                    if ':' in line:
                        key, val = line.split(':', 1)
                        if 'nama' in key.lower() or 'name' in key.lower():
                            nama = val.strip()
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
                    except:
                        pass
                
                st.progress((i + 1) / len(candidates))
            
            st.success(f"✅ Selesai! {success} dari {len(candidates)} berhasil disimpan")
