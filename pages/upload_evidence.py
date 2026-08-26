import streamlit as st
import pandas as pd
import os
import shutil
from datetime import datetime
from core.database import get_db
from core.models import FPTK, DBSourcing, User
from core.auth import get_current_user, is_admin

def show():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing ke folder yang sudah ditentukan.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # EVIDENCE FOLDER SETTING (di Settings)
    # ============================================================
    
    # Default folder (bisa diubah di Settings nanti)
    EVIDENCE_BASE_FOLDER = "evidence/"
    
    # Buat folder jika belum ada
    if not os.path.exists(EVIDENCE_BASE_FOLDER):
        os.makedirs(EVIDENCE_BASE_FOLDER)
    
    # ============================================================
    # PILIH POSISI DARI FPTK
    # ============================================================
    
    st.subheader("📋 Pilih Data FPTK")
    
    # Query FPTK yang aktif (status OP/Closed)
    fptk_list = db.query(FPTK).filter(
        FPTK.status.in_(["OP", "Closed"])
    ).order_by(FPTK.kode_unik).all()
    
    if not fptk_list:
        st.warning("Belum ada data FPTK. Silakan upload file terlebih dahulu.")
        return
    
    # Dropdown pilih FPTK
    fptk_options = {
        f"{f.kode_unik} - {f.posisi} ({f.pic_recruiter})": f.id 
        for f in fptk_list
    }
    
    selected_label = st.selectbox("Pilih FPTK", list(fptk_options.keys()))
    selected_fptk_id = fptk_options[selected_label]
    
    # Ambil detail FPTK
    fptk = db.query(FPTK).filter(FPTK.id == selected_fptk_id).first()
    
    if fptk:
        st.info(f"""
        **Kode Unik:** {fptk.kode_unik}  
        **Posisi:** {fptk.posisi}  
        **PIC:** {fptk.pic_recruiter}  
        **Status:** {fptk.status}  
        **Business Unit:** {fptk.business_unit}
        """)
    
    # ============================================================
    # UPLOAD EVIDENCE
    # ============================================================
    
    st.markdown("---")
    st.subheader("📁 Upload File Evidence")
    
    uploaded_file = st.file_uploader(
        "Pilih file bukti (PDF, JPG, PNG, DOC, DOCX, XLS, XLSX)",
        type=["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"]
    )
    
    # Tanggal evidence
    evidence_date = st.date_input("Tanggal Evidence", datetime.now())
    
    # Keterangan
    evidence_note = st.text_area("Keterangan / Catatan", placeholder="Contoh: Screenshot approval, CV kandidat, dll")
    
    if st.button("📤 Upload Evidence", type="primary"):
        if not uploaded_file:
            st.error("Pilih file terlebih dahulu!")
        else:
            try:
                # Buat folder per FPTK
                fptk_folder = os.path.join(
                    EVIDENCE_BASE_FOLDER, 
                    f"{fptk.kode_unik}_{fptk.posisi[:30].replace('/', '_')}"
                )
                if not os.path.exists(fptk_folder):
                    os.makedirs(fptk_folder)
                
                # Format nama file
                date_str = evidence_date.strftime("%Y%m%d")
                file_ext = uploaded_file.name.split('.')[-1]
                file_name = f"{date_str}_{uploaded_file.name}"
                file_path = os.path.join(fptk_folder, file_name)
                
                # Simpan file
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Simpan log evidence ke database (opsional)
                # Bisa dibuat tabel EvidenceLog nanti
                
                st.success(f"✅ Evidence berhasil diupload!")
                st.info(f"📁 Lokasi: {file_path}")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Error upload evidence: {str(e)}")
    
    # ============================================================
    # LIHAT EVIDENCE YANG SUDAH ADA
    # ============================================================
    
    st.markdown("---")
    st.subheader("📂 Evidence Tersimpan")
    
    # Cek folder FPTK
    fptk_folder = os.path.join(
        EVIDENCE_BASE_FOLDER, 
        f"{fptk.kode_unik}_{fptk.posisi[:30].replace('/', '_')}"
    )
    
    if os.path.exists(fptk_folder):
        files = os.listdir(fptk_folder)
        if files:
            data = []
            for f in files:
                file_path = os.path.join(fptk_folder, f)
                stat = os.stat(file_path)
                data.append({
                    "Nama File": f,
                    "Ukuran": f"{stat.st_size / 1024:.1f} KB",
                    "Tanggal": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
                    "Path": file_path
                })
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            
            # Download button
            for row in data:
                with open(row["Path"], "rb") as f:
                    st.download_button(
                        f"📥 Download {row['Nama File']}",
                        f.read(),
                        file_name=row["Nama File"],
                        key=row["Path"]
                    )
        else:
            st.info("Belum ada evidence untuk FPTK ini.")
    else:
        st.info("Belum ada evidence untuk FPTK ini.")
