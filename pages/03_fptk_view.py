import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import FPTK, User, MasterDropdown
from core.auth import get_current_user, is_admin
from core.utils import normalize_key
from datetime import datetime

def show_fptk_view():
    st.title("📋 FPTK Database")
    st.markdown("Lihat, filter, dan edit data FPTK.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔍 Filter FPTK")
        
        # Search by Kode Unik / Posisi
        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
        
        # Status filter
        status_options = ["Semua", "OP", "Closed", "Cancel"]
        status_filter = st.selectbox("Status", status_options)
        
        # PIC filter
        pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_options)
        
        # BU filter
        bu_options = ["Semua"] + [b[0] for b in db.query(FPTK.business_unit).distinct().all() if b[0]]
        bu_filter = st.selectbox("Business Unit", bu_options)
        
        # Direktorat filter
        dir_options = ["Semua"] + [d[0] for d in db.query(FPTK.direktorat).distinct().all() if d[0]]
        dir_filter = st.selectbox("Direktorat", dir_options)
        
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now().replace(year=2020))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())
        
        # Filter Kategorisasi
        filter_kat_options = ["Semua", "CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]
        filter_kat = st.selectbox("Filter Kategorisasi", filter_kat_options)
        
        # Show only my data
        show_mine = st.checkbox("Hanya data saya", value=False)
        
        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.session_state['fptk_filters'] = {}
            st.rerun()
    
    # Build query
    query = db.query(FPTK)
    
    if search:
        search_term = search.strip()
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{search_term}%")) |
            (FPTK.posisi.ilike(f"%{search_term}%"))
        )
    
    if status_filter != "Semua":
        query = query.filter(FPTK.status == status_filter)
    
    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)
    
    if bu_filter != "Semua":
        query = query.filter(FPTK.business_unit == bu_filter)
    
    if dir_filter != "Semua":
        query = query.filter(FPTK.direktorat == dir_filter)
    
    if filter_kat != "Semua":
        query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)
    
    if show_mine and not is_admin(db):
        query = query.filter(FPTK.pic_recruiter == user.pic_recruiter)
    
    if date_from:
        query = query.filter(FPTK.fptk_date_real >= date_from)
    if date_to:
        query = query.filter(FPTK.fptk_date_real <= date_to)
    
    # Total count
    total = query.count()
    st.markdown(f"**Total FPTK: {total}**")
    
    # Data display
    if total > 0:
        # Pagination
        page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
        page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
        offset = (page - 1) * page_size
        
        df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)
        
        # Columns to display
        columns = ['id', 'kode_unik', 'posisi', 'pic_recruiter', 'business_unit', 
                   'direktorat', 'status', 'filter_kategorisasi_fptk', 'fptk_date_real']
        display_cols = [c for c in columns if c in df.columns]
        
        st.dataframe(
            df[display_cols],
            use_container_width=True,
            height=500,
            column_config={
                "id": "ID",
                "kode_unik": "Kode Unik",
                "posisi": "Posisi",
                "pic_recruiter": "PIC",
                "business_unit": "BU",
                "direktorat": "Direktorat",
                "status": "Status",
                "filter_kategorisasi_fptk": "Filter Kategorisasi",
                "fptk_date_real": "Tanggal FPTK"
            }
        )
        
        # Export
        if st.button("📥 Export CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, "fptk_export.csv", "text/csv")
        
        # Detail view
        st.markdown("---")
        st.subheader("🔍 Detail FPTK")
        selected_id = st.selectbox("Pilih ID untuk lihat detail", df['id'].tolist())
        
        if selected_id:
            detail = db.query(FPTK).filter(FPTK.id == selected_id).first()
            if detail:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**Posisi:** {detail.posisi}")
                    st.markdown(f"**PIC:** {detail.pic_recruiter}")
                    st.markdown(f"**BU:** {detail.business_unit}")
                    st.markdown(f"**Direktorat:** {detail.direktorat}")
                    st.markdown(f"**Status:** {detail.status}")
                with col2:
                    st.markdown(f"**Filter Kategorisasi:** {detail.filter_kategorisasi_fptk}")
                    st.markdown(f"**Tanggal FPTK:** {detail.fptk_date_real.strftime('%d/%m/%Y') if detail.fptk_date_real else '-'}")
                    st.markdown(f"**Level:** {detail.level_fptk} (Level {detail.level_number})")
                    st.markdown(f"**SLA:** {detail.jumlah_sla} hari")
                    st.markdown(f"**Deadline SLA:** {detail.deadline_sla.strftime('%d/%m/%Y') if detail.deadline_sla else '-'}")
                
                # Admin: Edit button
                if is_admin(db):
                    st.markdown("---")
                    st.subheader("✏️ Edit (Admin)")
                    with st.form("edit_fptk"):
                        new_status = st.selectbox("Status", ["OP", "Closed", "Cancel"], index=["OP", "Closed", "Cancel"].index(detail.status or "OP"))
                        new_pic = st.selectbox("PIC Recruiter", [p[0] for p in db.query(MasterDropdown.pic_recruiter).distinct().all() if p[0]], index=0)
                        new_filter = st.text_input("Filter Kategorisasi", value=detail.filter_kategorisasi_fptk or "")
                        notes = st.text_area("Remark", value=detail.remark or "")
                        
                        if st.form_submit_button("Update"):
                            detail.status = new_status
                            detail.pic_recruiter = new_pic
                            detail.filter_kategorisasi_fptk = new_filter
                            detail.remark = notes
                            detail.last_updated_at = datetime.now()
                            db.commit()
                            st.success("Data berhasil diupdate!")
                            st.rerun()
    else:
        st.info("Tidak ada data FPTK dengan filter yang dipilih.")