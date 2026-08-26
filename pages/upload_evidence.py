import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import Evidence, FPTK, User
from core.auth import get_current_user, is_admin

def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    if not is_admin(db):
        st.error("⛔ Halaman ini hanya untuk Admin.")
        return
    
    # Dropdown Kode Unik
    fptk_list = db.query(FPTK.kode_unik, FPTK.posisi, FPTK.pic_recruiter).distinct().all()
    kode_unik_options = [""] + [f[0] for f in fptk_list if f[0]]
    
    with st.form("evidence_upload_form"):
        st.markdown("### Upload Evidence")
        
        col1, col2 = st.columns(2)
        with col1:
            kode_unik = st.selectbox("Kode Unik FPTK *", kode_unik_options)
            evidence_date = st.date_input("Tanggal Evidence *", datetime.now())
            total_cv = st.number_input("Total CV", min_value=0, value=0)
        with col2:
            if kode_unik:
                fptk = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
                if fptk:
                    st.text_input("Posisi", value=fptk.posisi or "", disabled=True)
                    st.text_input("PIC", value=fptk.pic_recruiter or "", disabled=True)
            else:
                st.text_input("Posisi", disabled=True, placeholder="Pilih Kode Unik dulu")
                st.text_input("PIC", disabled=True, placeholder="Pilih Kode Unik dulu")
        
        notes = st.text_area("Catatan")
        uploaded_file = st.file_uploader("Upload File", type=["pdf", "jpg", "jpeg", "png"])
        
        submitted = st.form_submit_button("💾 Upload", type="primary")
    
    if submitted:
        if not kode_unik or not evidence_date or not uploaded_file:
            st.error("❌ Semua field wajib diisi!")
        else:
            try:
                new_ev = Evidence(
                    kode_unik=kode_unik,
                    evidence_date=evidence_date,
                    file_name=uploaded_file.name,
                    file_size=len(uploaded_file.read()),
                    total_cv=total_cv,
                    notes=notes,
                    uploaded_by=user.id,
                    created_at=datetime.now()
                )
                db.add(new_ev)
                db.commit()
                st.success("✅ Evidence berhasil diupload!")
                st.balloons()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
    
    # Daftar Evidence
    st.markdown("---")
    st.subheader("📋 Daftar Evidence")
    
    evidences = db.query(Evidence).order_by(Evidence.created_at.desc()).limit(100).all()
    
    if evidences:
        data = []
        for ev in evidences:
            fptk = db.query(FPTK).filter(FPTK.kode_unik == ev.kode_unik).first()
            data.append({
                "Kode Unik": ev.kode_unik,
                "Posisi": fptk.posisi if fptk else "-",
                "PIC": fptk.pic_recruiter if fptk else "-",
                "Tanggal": ev.evidence_date.strftime("%d/%m/%Y") if ev.evidence_date else "-",
                "File": ev.file_name,
                "Total CV": ev.total_cv,
                "Uploader": ev.uploader.display_name if ev.uploader else "-",
                "Created": ev.created_at.strftime("%d/%m/%Y %H:%M") if ev.created_at else "-"
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada evidence.")
