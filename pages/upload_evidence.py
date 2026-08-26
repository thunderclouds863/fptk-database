import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK
from core.auth import get_current_user

def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing ke folder OneDrive/Cloud.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # FORM UPLOAD EVIDENCE
    # ============================================================
    with st.form("evidence_form"):
        st.markdown("### Data Evidence")
        
        col1, col2 = st.columns(2)
        with col1:
            # Pilih Kode Unik dari FPTK
            fptk_list = db.query(FPTK.kode_unik, FPTK.posisi).limit(100).all()
            fptk_options = [f"{f[0]} - {f[1]}" for f in fptk_list] if fptk_list else []
            selected_fptk = st.selectbox("Pilih FPTK", [""] + fptk_options)
            
            # Tanggal evidence
            evidence_date = st.date_input("Tanggal Evidence", datetime.now())
            
            # Jumlah CV
            total_cv = st.number_input("Jumlah CV", min_value=0, value=0)
        
        with col2:
            # Upload file
            uploaded_file = st.file_uploader(
                "Upload File Bukti (PDF/Image)",
                type=["pdf", "png", "jpg", "jpeg", "xlsx", "xlsm"]
            )
            
            # Nama file custom
            file_name_custom = st.text_input(
                "Nama File (opsional)", 
                placeholder=f"Evidence_{datetime.now().strftime('%Y%m%d')}"
            )
        
        # Notes
        notes = st.text_area("Notes / Keterangan", placeholder="Tambahkan keterangan jika perlu...")
        
        submitted = st.form_submit_button("📤 Upload Evidence", type="primary")
        
        if submitted:
            if not selected_fptk:
                st.error("❌ Silakan pilih FPTK terlebih dahulu.")
            elif not uploaded_file:
                st.error("❌ Silakan upload file bukti.")
            else:
                # Parse FPTK
                kode_unik = selected_fptk.split(" - ")[0] if selected_fptk else ""
                
                # Tampilkan preview data
                st.success("✅ Evidence berhasil diupload!")
                st.info(f"📋 Kode Unik: {kode_unik}")
                st.info(f"📋 Tanggal: {evidence_date.strftime('%d/%m/%Y')}")
                st.info(f"📋 Jumlah CV: {total_cv}")
                st.info(f"📋 File: {uploaded_file.name}")
                
                # Simulasi simpan ke database (belum ada tabel evidence)
                st.warning("⚠️ Fitur ini masih dalam pengembangan. Evidence belum tersimpan ke database.")
                
                # Preview file
                if uploaded_file.type.startswith('image'):
                    st.image(uploaded_file, caption=uploaded_file.name, width=300)
                else:
                    st.download_button(
                        "📥 Download File",
                        uploaded_file,
                        file_name=uploaded_file.name
                    )
    
    # ============================================================
    # DAFTAR EVIDENCE (belum ada, placeholder)
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Daftar Evidence (Coming Soon)")
    st.info("Fitur daftar evidence akan segera hadir.")
