import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, Evidence
from core.auth import get_current_user, is_admin

def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing ke database.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # FORM UPLOAD EVIDENCE
    # ============================================================
    with st.form("evidence_form"):
        st.markdown("### Upload Evidence")
        
        # Pilih FPTK / Kode Unik
        col1, col2 = st.columns(2)
        with col1:
            kode_unik = st.text_input("Kode Unik *", placeholder="Masukkan Kode Unik...")
            pic_recruiter = st.text_input("PIC Recruiter", value=user.pic_recruiter or "")
        
        with col2:
            tanggal_evidence = st.date_input("Tanggal Evidence *", datetime.now())
            evidence_notes = st.text_area("Catatan Evidence", placeholder="Tambahkan catatan jika diperlukan...")
        
        # Upload file
        st.markdown("### File Evidence")
        uploaded_file = st.file_uploader(
            "Pilih file evidence (PDF, JPG, PNG, dll)",
            type=["pdf", "jpg", "jpeg", "png", "gif", "bmp", "xlsx", "xlsm", "doc", "docx"],
            help="Upload file bukti sourcing (CV, screenshot, dokumen, dll)"
        )
        
        st.markdown("---")
        submitted = st.form_submit_button("📤 Upload Evidence", type="primary")
        
        if submitted:
            errors = []
            
            if not kode_unik:
                errors.append("Kode Unik wajib diisi")
            if not uploaded_file:
                errors.append("File evidence wajib diupload")
            if not pic_recruiter:
                errors.append("PIC Recruiter wajib diisi")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                try:
                    # Baca file
                    file_bytes = uploaded_file.getvalue()
                    file_hash = hashlib.sha256(file_bytes).hexdigest()
                    
                    # Simpan ke database
                    new_evidence = Evidence(
                        kode_unik=kode_unik,
                        pic_recruiter=pic_recruiter,
                        tanggal_evidence=tanggal_evidence,
                        file_name=uploaded_file.name,
                        file_size=len(file_bytes),
                        file_type=uploaded_file.type,
                        file_hash=file_hash,
                        evidence_notes=evidence_notes,
                        source_user_id=user.id,
                        source_user_name=user.display_name or user.username,
                        created_at=datetime.now()
                    )
                    db.add(new_evidence)
                    db.commit()
                    
                    st.success(f"✅ Evidence berhasil diupload!")
                    st.info(f"📋 Kode Unik: {kode_unik}")
                    st.info(f"📋 File: {uploaded_file.name} ({len(file_bytes)/1024:.1f} KB)")
                    st.info(f"📋 Tanggal: {tanggal_evidence.strftime('%d/%m/%Y')}")
                    
                    # Tampilkan preview jika gambar
                    if uploaded_file.type and uploaded_file.type.startswith('image/'):
                        st.image(uploaded_file, caption=uploaded_file.name, width=400)
                    
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Error upload: {str(e)}")
                    db.rollback()
    
    # ============================================================
    # RIWAYAT EVIDENCE (USER LIHAT MILIKNYA, ADMIN LIHAT SEMUA)
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Riwayat Evidence")
    
    # Query evidence
    query = db.query(Evidence)
    
    # Jika bukan admin, hanya lihat milik sendiri
    if not is_admin(db):
        query = query.filter(Evidence.source_user_id == user.id)
    
    # Tampilkan data
    df = pd.read_sql(query.order_by(Evidence.created_at.desc()).limit(100).statement, db.bind)
    
    if len(df) > 0:
        # Format display
        display_cols = ['id', 'kode_unik', 'pic_recruiter', 'file_name', 'tanggal_evidence', 'created_at']
        display_df = df[[c for c in display_cols if c in df.columns]].copy()
        
        rename_map = {
            'id': 'ID',
            'kode_unik': 'Kode Unik',
            'pic_recruiter': 'PIC',
            'file_name': 'Nama File',
            'tanggal_evidence': 'Tanggal Evidence',
            'created_at': 'Upload Date'
        }
        display_df = display_df.rename(columns=rename_map)
        
        st.dataframe(display_df, use_container_width=True, height=300)
        
        # Detail evidence
        st.subheader("📄 Detail Evidence")
        selected_id = st.selectbox("Pilih ID untuk lihat detail", df['id'].tolist())
        
        if selected_id:
            detail = db.query(Evidence).filter(Evidence.id == selected_id).first()
            if detail:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**PIC:** {detail.pic_recruiter}")
                    st.markdown(f"**File:** {detail.file_name}")
                    st.markdown(f"**Size:** {detail.file_size/1024:.1f} KB")
                with col2:
                    st.markdown(f"**Tanggal Evidence:** {detail.tanggal_evidence.strftime('%d/%m/%Y') if detail.tanggal_evidence else '-'}")
                    st.markdown(f"**Upload By:** {detail.source_user_name}")
                    st.markdown(f"**Upload Date:** {detail.created_at.strftime('%d/%m/%Y %H:%M') if detail.created_at else '-'}")
                    st.markdown(f"**Notes:** {detail.evidence_notes or '-'}")
                
                # Admin: Hapus
                if is_admin(db):
                    if st.button("🗑️ Hapus Evidence", type="secondary"):
                        if st.warning("Yakin ingin menghapus evidence ini?"):
                            db.delete(detail)
                            db.commit()
                            st.success("Evidence berhasil dihapus!")
                            st.rerun()
    else:
        st.info("Belum ada evidence yang diupload.")
