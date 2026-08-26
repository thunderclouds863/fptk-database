import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import FPTK, User
from core.auth import get_current_user, is_admin
from datetime import datetime

def show_transfer_fptk():
    st.title("🔄 Transfer FPTK")
    st.markdown("Transfer FPTK dari satu PIC ke PIC lain.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # SELECT FPTK
    # ============================================================
    st.subheader("Pilih FPTK yang akan ditransfer")
    
    # Filter FPTK by PIC
    pic_options = ["Semua"] + [p[0] for p in db.query(FPTK.pic_recruiter).distinct().all() if p[0]]
    pic_filter = st.selectbox("PIC Saat Ini", pic_options)
    
    search = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
    
    query = db.query(FPTK)
    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)
    if search:
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{search}%")) |
            (FPTK.posisi.ilike(f"%{search}%"))
        )
    query = query.limit(100)
    
    df = pd.read_sql(query.statement, db.bind)
    
    if df.empty:
        st.warning("Tidak ada data FPTK.")
        return
    
    st.dataframe(df[['id', 'kode_unik', 'posisi', 'pic_recruiter', 'status']], use_container_width=True)
    
    # ============================================================
    # TRANSFER
    # ============================================================
    st.markdown("---")
    st.subheader("Transfer")
    
    selected_id = st.selectbox("Pilih ID FPTK yang akan ditransfer", df['id'].tolist())
    
    if selected_id:
        fptk = db.query(FPTK).filter(FPTK.id == selected_id).first()
        if fptk:
            st.info(f"📋 Data: {fptk.kode_unik} | {fptk.posisi} | PIC: {fptk.pic_recruiter}")
            
            # Pilih PIC tujuan
            target_pic = st.selectbox(
                "PIC Tujuan", 
                [p[0] for p in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if p[0] and p[0] != fptk.pic_recruiter]
            )
            
            reason = st.text_area("Alasan Transfer", placeholder="Isi alasan transfer...")
            
            if st.button("🔄 Transfer FPTK", type="primary"):
                if target_pic and reason:
                    old_pic = fptk.pic_recruiter
                    fptk.pic_recruiter = target_pic
                    fptk.last_updated_at = datetime.now()
                    fptk.last_compile_action = "TRANSFER"
                    db.commit()
                    
                    st.success(f"✅ FPTK berhasil ditransfer!")
                    st.info(f"📋 {fptk.kode_unik} | {old_pic} → {target_pic}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Pilih PIC tujuan dan isi alasan transfer!")
