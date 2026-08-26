import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing
from core.auth import get_current_user
from core.cv_parser import parse_cv_text
from core.utils import safe_int, parse_phone
from datetime import datetime

def show_paste_cv():
    st.title("📋 Paste CV Text")
    st.markdown("Paste teks CV dari Jobstreet, LinkedIn, atau hasil parsing Copilot.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # ============================================================
    # SINGLE PASTE
    # ============================================================
    st.subheader("Single CV")
    raw_text = st.text_area("Paste teks CV di sini", height=200)
    
    if raw_text and st.button("🔍 Parse & Simpan", type="primary"):
        parsed = parse_cv_text(raw_text)
        
        if any(parsed.values()):
            st.success("✅ CV berhasil diparse!")
            
            # Tampilkan hasil
            col1, col2 = st.columns(2)
            with col1:
                nama = st.text_input("Nama", value=parsed.get('nama', ''))
                email = st.text_input("Email", value=parsed.get('email', ''))
                hp = st.text_input("Nomor HP", value=parsed.get('nomor_hp', ''))
                domisili = st.text_input("Domisili", value=parsed.get('domisili', ''))
            with col2:
                univ = st.text_input("Universitas", value=parsed.get('universitas', ''))
                jurusan = st.text_input("Jurusan", value=parsed.get('jurusan', ''))
                ipk = st.text_input("IPK", value=parsed.get('ipk', ''))
                tahun = st.text_input("Tahun Lulus", value=parsed.get('tahun_lulus', ''))
            
            if st.button("💾 Simpan Kandidat", type="primary"):
                # Simpan ke database
                try:
                    last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                    next_no = (last_no.no + 1) if last_no and last_no.no else 1
                    
                    new = DBSourcing(
                        no=next_no,
                        nama=nama,
                        email=email,
                        nomor_hp=parse_phone(hp),
                        domisili=domisili,
                        nama_universitas_top10=univ if univ else None,
                        jurusan=jurusan,
                        ipk=safe_int(ipk.replace(',', '.')) if ipk else None,
                        tahun_lulus=safe_int(tahun) if tahun else None,
                        rekruter=user.pic_recruiter,
                        sourcing_date=datetime.now().date(),
                        source_user_id=user.id,
                        created_at=datetime.now()
                    )
                    db.add(new)
                    db.commit()
                    st.success(f"✅ Kandidat '{nama}' berhasil disimpan!")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
        else:
            st.warning("Tidak ada data yang terdeteksi.")
    
    # ============================================================
    # BATCH PASTE
    # ============================================================
    st.markdown("---")
    st.subheader("Batch CV (Banyak Kandidat)")
    st.caption("Paste hasil dari Copilot Agent atau multiple CV. Pisahkan dengan separator.")
    
    separator = st.text_input("Separator kandidat", value="=== CV ===")
    batch_text = st.text_area("Paste batch CV di sini", height=300)
    
    if batch_text and st.button("🚀 Proses Batch", key="process_batch"):
        # Split berdasarkan separator
        candidates = batch_text.split(separator)
        candidates = [c.strip() for c in candidates if c.strip()]
        
        st.info(f"📋 Ditemukan {len(candidates)} kandidat")
        
        # Preview
        preview_data = []
        for i, text in enumerate(candidates[:10]):
            parsed = parse_cv_text(text)
            preview_data.append({
                "No": i+1,
                "Nama": parsed.get('nama', ''),
                "Email": parsed.get('email', ''),
                "Universitas": parsed.get('universitas', '')
            })
        
        st.dataframe(pd.DataFrame(preview_data), use_container_width=True)
        
        if len(candidates) > 10:
            st.caption(f"... dan {len(candidates)-10} kandidat lainnya")
        
        if st.button("✅ Simpan Semua", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            success = 0
            failed = 0
            
            for i, text in enumerate(candidates):
                status_text.text(f"Memproses {i+1}/{len(candidates)}")
                parsed = parse_cv_text(text)
                
                if parsed.get('nama'):
                    try:
                        last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                        next_no = (last_no.no + 1) if last_no and last_no.no else 1
                        
                        new = DBSourcing(
                            no=next_no,
                            nama=parsed.get('nama', ''),
                            email=parsed.get('email', ''),
                            nomor_hp=parse_phone(parsed.get('nomor_hp', '')),
                            domisili=parsed.get('domisili', ''),
                            nama_universitas_top10=parsed.get('universitas', ''),
                            jurusan=parsed.get('jurusan', ''),
                            ipk=safe_int(parsed.get('ipk', '').replace(',', '.')),
                            tahun_lulus=parsed.get('tahun_lulus'),
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
                        db.rollback()
                else:
                    failed += 1
                
                progress_bar.progress((i + 1) / len(candidates))
            
            status_text.text("Selesai!")
            st.success(f"✅ Batch selesai! Berhasil: {success}, Gagal: {failed}")
