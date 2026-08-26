import streamlit as st
import pandas as pd
from datetime import datetime
import base64
import re
from core.database import get_db
from core.models import Evidence, FPTK, User
from core.auth import get_current_user, is_admin

def sanitize_filename(filename: str) -> str:
    """Hapus karakter tidak valid untuk nama file"""
    return re.sub(r'[<>:"/\\|?*]', '', filename).strip()

def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
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
            total_cv = st.number_input("Total CV *", min_value=1, value=1)
        with col2:
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
        st.caption("💡 **Format nama file otomatis:** `Posisi - Tanggal - Total CV`")
        
        # Preview nama file yang akan disimpan
        if kode_unik and uploaded_file:
            fptk_data = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
            if fptk_data:
                posisi = sanitize_filename(fptk_data.posisi or "Unknown")
                date_str = evidence_date.strftime("%d-%m-%Y")
                ext = uploaded_file.name.split('.')[-1] if '.' in uploaded_file.name else 'pdf'
                preview_name = f"{posisi} - {date_str} - {total_cv} CV.{ext}"
                st.info(f"📋 **Nama file akan disimpan sebagai:** {preview_name}")
        
        submitted = st.form_submit_button("💾 Upload Evidence", type="primary")
    
    # ============================================================
    # PROSES UPLOAD (DENGAN RENAME FILE)
    # ============================================================
    if submitted:
        errors = []
        
        if not kode_unik:
            errors.append("Kode Unik FPTK wajib dipilih")
        if not evidence_date:
            errors.append("Tanggal Evidence wajib diisi")
        if total_cv <= 0:
            errors.append("Total CV harus lebih dari 0")
        if not uploaded_file:
            errors.append("File bukti wajib diupload")
        
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            try:
                # Ambil data FPTK
                fptk_data = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
                if not fptk_data:
                    st.error(f"❌ FPTK dengan Kode Unik '{kode_unik}' tidak ditemukan!")
                    db.rollback()
                else:
                    # Buat nama file otomatis: Posisi - Tanggal - Total CV.ext
                    posisi = sanitize_filename(fptk_data.posisi or "Unknown")
                    date_str = evidence_date.strftime("%d-%m-%Y")
                    ext = uploaded_file.name.split('.')[-1] if '.' in uploaded_file.name else 'pdf'
                    new_file_name = f"{posisi} - {date_str} - {total_cv} CV.{ext}"
                    
                    file_bytes = uploaded_file.read()
                    file_size = len(file_bytes)
                    
                    new_evidence = Evidence(
                        kode_unik=kode_unik,
                        evidence_date=evidence_date,
                        file_name=new_file_name,
                        file_data=file_bytes,
                        file_size=file_size,
                        total_cv=total_cv,
                        notes=notes,
                        uploaded_by=user.id,
                        created_at=datetime.now()
                    )
                    db.add(new_evidence)
                    db.commit()
                    
                    st.success(f"✅ Evidence berhasil diupload!")
                    st.info(f"📋 **Nama File:** {new_file_name}")
                    st.info(f"📋 **Kode Unik:** {kode_unik}")
                    st.info(f"📋 **Posisi:** {posisi}")
                    st.info(f"📋 **Total CV:** {total_cv}")
                    st.balloons()
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
    
    # ============================================================
    # DAFTAR EVIDENCE
    # ============================================================
    st.markdown("---")
    
    admin = is_admin(db)
    
    if admin:
        st.subheader("📋 Semua Evidence (Admin View)")
        evidences = db.query(Evidence).order_by(Evidence.created_at.desc()).limit(100).all()
    else:
        st.subheader(f"📋 Riwayat Evidence ")
        evidences = db.query(Evidence).filter(
            Evidence.uploaded_by == user.id
        ).order_by(Evidence.created_at.desc()).limit(100).all()
    
    if evidences:
        data = []
        for ev in evidences:
            uploader_name = "-"
            try:
                if ev.uploader:
                    uploader_name = ev.uploader.display_name or ev.uploader.username or "-"
            except:
                uploader_name = str(ev.uploaded_by) if ev.uploaded_by else "-"
            
            data.append({
                "ID": ev.id,
                "Kode Unik": ev.kode_unik,
                "Tanggal": ev.evidence_date.strftime("%d/%m/%Y") if ev.evidence_date else "-",
                "File": ev.file_name,
                "Total CV": ev.total_cv,
                "Uploader": uploader_name,
                "Size": f"{ev.file_size/1024:.1f} KB" if ev.file_size else "-",
                "Created": ev.created_at.strftime("%d/%m/%Y %H:%M") if ev.created_at else "-"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)
        
        # ============================================================
        # DOWNLOAD / PREVIEW FILE
        # ============================================================
        st.markdown("---")
        st.subheader("📂 Download / Buka File Bukti")
        
        evidence_options = {f"{ev.id} - {ev.file_name}": ev.id for ev in evidences}
        if evidence_options:
            selected = st.selectbox("Pilih file untuk dibuka", list(evidence_options.keys()))
            
            if selected:
                ev_id = evidence_options[selected]
                evidence = db.query(Evidence).filter(Evidence.id == ev_id).first()
                
                if evidence and evidence.file_data:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(f"📄 **{evidence.file_name}**")
                        st.caption(f"Kode Unik: {evidence.kode_unik} | Tanggal: {evidence.evidence_date.strftime('%d/%m/%Y')} | Total CV: {evidence.total_cv}")
                    with col2:
                        b64 = base64.b64encode(evidence.file_data).decode()
                        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{evidence.file_name}" style="text-decoration:none;background-color:#2ecc71;color:white;padding:8px 16px;border-radius:5px;">📥 Download</a>'
                        st.markdown(href, unsafe_allow_html=True)
                    
                    # Preview gambar
                    if evidence.file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                        try:
                            st.image(evidence.file_data, caption=evidence.file_name, use_container_width=True)
                        except:
                            st.warning("Preview gambar tidak tersedia, silakan download.")
                    
                    # Preview PDF
                    elif evidence.file_name.lower().endswith('.pdf'):
                        try:
                            b64_pdf = base64.b64encode(evidence.file_data).decode()
                            pdf_view = f'<embed src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500" type="application/pdf">'
                            st.markdown(pdf_view, unsafe_allow_html=True)
                        except:
                            st.warning("Preview PDF tidak tersedia, silakan download.")
                else:
                    st.warning("File tidak ditemukan atau sudah terhapus.")
        
        # Export CSV
        if st.button("📥 Export CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, f"evidence_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    else:
        if admin:
            st.info("Belum ada evidence yang diupload.")
        else:
            st.info("Anda belum upload evidence.")
