import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing, FPTK, Evidence, User
from core.auth import get_current_user, is_admin
from datetime import datetime
import hashlib

def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing dan lihat histori upload.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # UPLOAD EVIDENCE
    # ============================================================
    st.subheader("📤 Upload Evidence Baru")
    
    # Ambil daftar kode_unik dari DB Sourcing
    sourcing_data = db.query(DBSourcing.kode_unik, DBSourcing.posisi).filter(
        DBSourcing.kode_unik.isnot(None)
    ).distinct().all()
    
    if not sourcing_data:
        st.warning("Belum ada data sourcing dengan Kode Unik.")
        return
    
    posisi_options = {}
    for s in sourcing_data:
        if s.posisi:
            key = f"{s.posisi[:50]} | {s.kode_unik}"
            posisi_options[key] = s.kode_unik
    
    selected = st.selectbox("Pilih Posisi / Kode Unik", list(posisi_options.keys()))
    kode_unik = posisi_options[selected]
    posisi_text = selected.split(" | ")[0]
    
    # Tanggal evidence
    tanggal = st.date_input("Tanggal Evidence", datetime.now())
    
    # Cek jumlah CV
    total_cv = db.query(DBSourcing).filter(
        DBSourcing.kode_unik == kode_unik,
        DBSourcing.sourcing_date == tanggal
    ).count()
    
    st.metric("📊 Jumlah CV", total_cv)
    
    # Upload file
    uploaded_file = st.file_uploader(
        "Pilih file bukti evidence (PDF, Image, Excel)",
        type=["pdf", "jpg", "jpeg", "png", "xlsx", "xlsm"]
    )
    
    if uploaded_file:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")
        
        if st.button("💾 Upload Evidence", type="primary"):
            file_bytes = uploaded_file.getvalue()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            file_name = uploaded_file.name
            
            clean_posisi = posisi_text.replace(" ", "_").replace("/", "_")[:40]
            safe_name = f"{tanggal.strftime('%Y-%m-%d')}_{clean_posisi}_{total_cv}_CV.{file_name.split('.')[-1]}"
            
            try:
                new_evidence = Evidence(
                    kode_unik=kode_unik,
                    posisi=posisi_text,
                    tanggal=tanggal,
                    file_name=safe_name,
                    file_path=f"evidence/{safe_name}",
                    file_size=len(file_bytes),
                    total_cv=total_cv,
                    pic_recruiter=user.pic_recruiter or user.username,
                    user_id=user.id,
                    created_at=datetime.now()
                )
                db.add(new_evidence)
                db.commit()
                
                st.success("✅ Evidence berhasil direkam!")
                st.info(f"📋 Nama file: {safe_name}")
                st.info(f"📋 Total CV: {total_cv}")
                
                st.download_button(
                    "📥 Download File",
                    file_bytes,
                    safe_name,
                    uploaded_file.type
                )
                
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
    
    # ============================================================
    # HISTORI EVIDENCE - PAKAI user_id BUKAN uploaded_by
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Histori Evidence")
    
    # Filter
    col1, col2 = st.columns(2)
    with col1:
        pic_filter = st.selectbox(
            "Filter PIC",
            ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        )
    with col2:
        search_filter = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
    
    # Query evidence - PAKAI user_id
    query = db.query(Evidence)
    if pic_filter != "Semua":
        query = query.filter(Evidence.pic_recruiter == pic_filter)
    if search_filter:
        query = query.filter(
            (Evidence.kode_unik.ilike(f"%{search_filter}%")) |
            (Evidence.posisi.ilike(f"%{search_filter}%"))
        )
    
    evidences = query.order_by(Evidence.created_at.desc()).limit(100).all()
    
    if evidences:
        data = []
        for e in evidences:
            data.append({
                "ID": e.id,
                "Kode Unik": e.kode_unik,
                "Posisi": e.posisi[:40] + "..." if len(e.posisi or "") > 40 else e.posisi,
                "Tanggal": e.tanggal.strftime("%d/%m/%Y") if e.tanggal else "-",
                "File": e.file_name,
                "CV": e.total_cv,
                "PIC": e.pic_recruiter,
                "Upload": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "-"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)
        
        # Export
        if st.button("📥 Export CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Download", csv, f"evidence_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        
        # Detail evidence
        st.markdown("---")
        st.subheader("🔍 Detail Evidence")
        
        selected_id = st.selectbox("Pilih ID untuk lihat detail", [e.id for e in evidences])
        if selected_id:
            detail = db.query(Evidence).filter(Evidence.id == selected_id).first()
            if detail:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**Posisi:** {detail.posisi}")
                with col2:
                    st.markdown(f"**Tanggal:** {detail.tanggal.strftime('%d/%m/%Y') if detail.tanggal else '-'}")
                    st.markdown(f"**Total CV:** {detail.total_cv}")
                with col3:
                    st.markdown(f"**File:** {detail.file_name}")
                    st.markdown(f"**PIC:** {detail.pic_recruiter}")
                
                # Admin hapus
                if admin:
                    if st.button("🗑️ Hapus Evidence", type="secondary"):
                        db.delete(detail)
                        db.commit()
                        st.success("Data berhasil dihapus!")
                        st.rerun()
    else:
        st.info("Belum ada evidence yang diupload.")
