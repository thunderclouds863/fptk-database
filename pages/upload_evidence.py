import streamlit as st
import pandas as pd
import base64
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, Evidence, User
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
            search_fptk = st.text_input("Cari Kode Unik / Posisi", placeholder="Ketik Kode Unik atau Posisi...")
            
            if search_fptk:
                fptk_results = db.query(FPTK).filter(
                    (FPTK.kode_unik.ilike(f"%{search_fptk}%")) |
                    (FPTK.posisi.ilike(f"%{search_fptk}%"))
                ).limit(10).all()
                
                if fptk_results:
                    fptk_options = {f"{r.kode_unik} - {r.posisi}": r.kode_unik for r in fptk_results}
                    selected_fptk = st.selectbox("Pilih FPTK", list(fptk_options.keys()))
                    kode_unik = fptk_options[selected_fptk] if selected_fptk else ""
                else:
                    st.warning("FPTK tidak ditemukan")
                    kode_unik = ""
            else:
                kode_unik = st.text_input("Kode Unik (manual)", placeholder="Masukkan Kode Unik...")
        
        with col2:
            tanggal_evidence = st.date_input("Tanggal Evidence", datetime.now())
            pic_recruiter = st.text_input("PIC Recruiter", value=user.pic_recruiter or "")
        
        # Upload file
        st.markdown("### File Evidence")
        uploaded_file = st.file_uploader(
            "Pilih file evidence (PDF, JPG, PNG, dll)",
            type=["pdf", "jpg", "jpeg", "png", "gif", "bmp", "xlsx", "xlsm", "doc", "docx"],
            help="Upload file bukti sourcing (CV, screenshot, dokumen, dll)"
        )
        
        evidence_notes = st.text_area("Catatan Evidence", placeholder="Tambahkan catatan jika diperlukan...")
        
        st.markdown("---")
        submitted = st.form_submit_button("📤 Upload Evidence", type="primary")
        
        if submitted:
            errors = []
            
            if not kode_unik:
                errors.append("Kode Unik wajib diisi")
            if not uploaded_file:
                errors.append("File evidence wajib diupload")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                try:
                    # Baca file dan convert ke base64
                    file_bytes = uploaded_file.read()
                    file_base64 = base64.b64encode(file_bytes).decode('utf-8')
                    file_size = len(file_bytes)
                    file_name = uploaded_file.name
                    file_type = uploaded_file.type or "application/octet-stream"
                    
                    # Simpan ke database
                    new_evidence = Evidence(
                        kode_unik=kode_unik,
                        pic_recruiter=pic_recruiter or user.pic_recruiter,
                        file_name=file_name,
                        file_size_bytes=file_size,
                        file_type=file_type,
                        file_data=file_base64,
                        evidence_date=tanggal_evidence,
                        notes=evidence_notes,
                        source_user_id=user.id,
                        source_user_name=user.display_name or user.username,
                        created_at=datetime.now()
                    )
                    db.add(new_evidence)
                    db.commit()
                    
                    st.success(f"✅ Evidence berhasil diupload!")
                    st.info(f"📋 Kode Unik: {kode_unik}")
                    st.info(f"📋 File: {file_name} ({file_size/1024:.1f} KB)")
                    st.info(f"📋 Tanggal: {tanggal_evidence.strftime('%d/%m/%Y')}")
                    
                    # Tampilkan preview jika gambar
                    if uploaded_file.type and uploaded_file.type.startswith('image/'):
                        st.image(uploaded_file, caption=file_name, width=400)
                    
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Error upload: {str(e)}")
                    db.rollback()
    
    # ============================================================
    # RIWAYAT EVIDENCE
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Riwayat Evidence")
    
    # Ambil data evidence
    evidences = db.query(Evidence).order_by(Evidence.created_at.desc()).limit(50).all()
    
    if evidences:
        data = []
        for ev in evidences:
            # Tampilkan preview kecil
            preview = "📄"
            if ev.file_type and ev.file_type.startswith('image/'):
                preview = "🖼️"
            elif ev.file_type and 'pdf' in ev.file_type.lower():
                preview = "📕"
            elif ev.file_type and ('excel' in ev.file_type.lower() or 'spreadsheet' in ev.file_type.lower()):
                preview = "📊"
            
            data.append({
                "ID": ev.id,
                "Preview": preview,
                "Kode Unik": ev.kode_unik,
                "File": ev.file_name,
                "PIC": ev.pic_recruiter,
                "Tanggal": ev.evidence_date.strftime("%d/%m/%Y") if ev.evidence_date else "-",
                "Upload": ev.created_at.strftime("%d/%m/%Y %H:%M") if ev.created_at else "-",
                "Notes": ev.notes[:50] + "..." if ev.notes and len(ev.notes) > 50 else ev.notes
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)
        
        # Detail evidence (klik untuk lihat)
        st.subheader("🔍 Detail Evidence")
        ev_ids = [ev.id for ev in evidences]
        selected_id = st.selectbox("Pilih ID untuk lihat detail", ev_ids)
        
        if selected_id:
            detail = db.query(Evidence).filter(Evidence.id == selected_id).first()
            if detail:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**File:** {detail.file_name}")
                    st.markdown(f"**Ukuran:** {detail.file_size_bytes/1024:.1f} KB")
                    st.markdown(f"**Tanggal Evidence:** {detail.evidence_date.strftime('%d/%m/%Y') if detail.evidence_date else '-'}")
                with col2:
                    st.markdown(f"**PIC:** {detail.pic_recruiter}")
                    st.markdown(f"**Upload By:** {detail.source_user_name}")
                    st.markdown(f"**Upload At:** {detail.created_at.strftime('%d/%m/%Y %H:%M') if detail.created_at else '-'}")
                    st.markdown(f"**Notes:** {detail.notes or '-'}")
                
                # Tampilkan file jika bisa
                if detail.file_type and detail.file_type.startswith('image/'):
                    st.image(base64.b64decode(detail.file_data), caption=detail.file_name, width=400)
                elif detail.file_type and 'pdf' in detail.file_type.lower():
                    st.info("📕 PDF file. Klik tombol download di bawah untuk melihat.")
                
                # Download button
                if detail.file_data:
                    file_bytes = base64.b64decode(detail.file_data)
                    st.download_button(
                        "📥 Download File",
                        file_bytes,
                        detail.file_name,
                        detail.file_type or "application/octet-stream"
                    )
                
                # Delete button (Admin only)
                if is_admin(db):
                    if st.button("🗑️ Hapus Evidence", type="secondary"):
                        if st.button("✅ Konfirmasi Hapus", type="primary"):
                            db.delete(detail)
                            db.commit()
                            st.success("Evidence berhasil dihapus!")
                            st.rerun()
    else:
        st.info("Belum ada evidence yang diupload.")
