import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import Evidence, FPTK, User
from core.auth import get_current_user, is_admin
import os

def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing ke sistem.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # CEK ADMIN (Evidence hanya untuk Admin)
    # ============================================================
    if not is_admin(db):
        st.error("⛔ Halaman ini hanya untuk Admin.")
        st.info("Evidence sourcing hanya dapat diupload oleh Admin.")
        return
    
    # ============================================================
    # AMBIL DATA FPTK UNTUK DROPDOWN
    # ============================================================
    fptk_list = db.query(FPTK.kode_unik, FPTK.posisi, FPTK.pic_recruiter).distinct().all()
    kode_unik_options = [""] + [f[0] for f in fptk_list if f[0]]
    
    # ============================================================
    # FORM UPLOAD
    # ============================================================
    with st.form("evidence_upload_form"):
        st.markdown("### Upload Evidence")
        
        col1, col2 = st.columns(2)
        with col1:
            kode_unik = st.selectbox("Kode Unik FPTK *", kode_unik_options)
            evidence_date = st.date_input("Tanggal Evidence *", datetime.now())
            total_cv = st.number_input("Total CV", min_value=0, value=0)
        with col2:
            # Auto-fill posisi & PIC jika kode_unik dipilih
            if kode_unik:
                fptk_data = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
                if fptk_data:
                    st.text_input("Posisi", value=fptk_data.posisi or "", disabled=True)
                    st.text_input("PIC Recruiter", value=fptk_data.pic_recruiter or "", disabled=True)
            else:
                st.text_input("Posisi", disabled=True, placeholder="Pilih Kode Unik dulu")
                st.text_input("PIC Recruiter", disabled=True, placeholder="Pilih Kode Unik dulu")
        
        notes = st.text_area("Catatan")
        
        uploaded_file = st.file_uploader(
            "Upload File Bukti (PDF, JPG, PNG)",
            type=["pdf", "jpg", "jpeg", "png", "gif", "bmp"],
            help="Upload file bukti evidence sourcing"
        )
        
        st.markdown("---")
        submitted = st.form_submit_button("💾 Upload Evidence", type="primary")
    
    # ============================================================
    # PROSES UPLOAD
    # ============================================================
    if submitted:
        errors = []
        
        if not kode_unik:
            errors.append("Kode Unik FPTK wajib dipilih")
        if not evidence_date:
            errors.append("Tanggal Evidence wajib diisi")
        if not uploaded_file:
            errors.append("File bukti wajib diupload")
        
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            try:
                # Baca file
                file_bytes = uploaded_file.read()
                file_name = uploaded_file.name
                file_size = len(file_bytes)
                
                # Simpan ke database
                new_evidence = Evidence(
                    kode_unik=kode_unik,
                    evidence_date=evidence_date,
                    file_name=file_name,
                    file_size=file_size,
                    total_cv=total_cv,
                    notes=notes,
                    uploaded_by=user.id,
                    created_at=datetime.now()
                )
                db.add(new_evidence)
                db.commit()
                
                st.success(f"✅ Evidence berhasil diupload!")
                st.info(f"📋 File: {file_name}")
                st.info(f"📋 Kode Unik: {kode_unik}")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
    
    # ============================================================
    # DAFTAR EVIDENCE
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Daftar Evidence")
    
    # Query evidence
    evidences = db.query(Evidence).order_by(Evidence.created_at.desc()).limit(50).all()
    
    if evidences:
        data = []
        for ev in evidences:
            data.append({
                "ID": ev.id,
                "Kode Unik": ev.kode_unik,
                "Tanggal": ev.evidence_date.strftime("%d/%m/%Y") if ev.evidence_date else "-",
                "File": ev.file_name,
                "Total CV": ev.total_cv,
                "Uploader": ev.uploader.display_name if ev.uploader else "-",
                "Created": ev.created_at.strftime("%d/%m/%Y %H:%M") if ev.created_at else "-"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)
        
        # Download
        if st.button("📥 Export CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, f"evidence_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    else:
        st.info("Belum ada evidence yang diupload.")
