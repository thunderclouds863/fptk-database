import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import FPTK, User, MasterDropdown
from core.auth import get_current_user, is_admin
from datetime import datetime
import plotly.express as px

def show_fptk_view():
    st.title("📋 FPTK Database")
    st.markdown("Lihat semua data FPTK. Edit hanya untuk data milik PIC Anda (Admin bisa semua).")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter FPTK")
        
        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
        status_filter = st.selectbox("Status", ["Semua", "OP", "Closed", "Cancel"])
        
        pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_options)
        
        bu_options = ["Semua"] + [b[0] for b in db.query(FPTK.business_unit).distinct().all() if b[0]]
        bu_filter = st.selectbox("Business Unit", bu_options)
        
        dir_options = ["Semua"] + [d[0] for d in db.query(FPTK.direktorat).distinct().all() if d[0]]
        dir_filter = st.selectbox("Direktorat", dir_options)
        
        filter_kat_options = ["Semua", "CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]
        filter_kat = st.selectbox("Filter Kategorisasi", filter_kat_options)
        
        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()
    
    # ============================================================
    # BUILD QUERY
    # ============================================================
    query = db.query(FPTK)
    
    if search:
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{search}%")) |
            (FPTK.posisi.ilike(f"%{search}%"))
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
    
    total = query.count()
    st.markdown(f"**Total FPTK: {total}**")
    
    if total == 0:
        st.info("Tidak ada data FPTK dengan filter yang dipilih.")
        return
    
    # ============================================================
    # PAGINATION & DISPLAY
    # ============================================================
    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
    offset = (page - 1) * page_size
    
    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)
    
    # Kolom yang ditampilkan
    display_cols = ['id', 'kode_unik', 'posisi', 'pic_recruiter', 'business_unit', 
                    'direktorat', 'status', 'filter_kategorisasi_fptk', 'fptk_date_real', 'vacancy']
    
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        height=400,
        column_config={
            "id": "ID",
            "kode_unik": "Kode Unik",
            "posisi": "Posisi",
            "pic_recruiter": "PIC",
            "business_unit": "BU",
            "direktorat": "Direktorat",
            "status": "Status",
            "filter_kategorisasi_fptk": "Filter Kategorisasi",
            "fptk_date_real": "Tanggal FPTK",
            "vacancy": "Vacancy"
        }
    )
    
    # ============================================================
    # DETAIL & EDIT
    # ============================================================
    st.markdown("---")
    st.subheader("🔍 Detail / Edit FPTK")
    
    selected_id = st.selectbox("Pilih ID untuk lihat/edit", df['id'].tolist())
    
    if selected_id:
        detail = db.query(FPTK).filter(FPTK.id == selected_id).first()
        if not detail:
            st.error("Data tidak ditemukan")
            return
        
        # Cek akses edit
        can_edit = admin or (detail.pic_recruiter == user.pic_recruiter)
        
        # Tampilkan detail
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Kode Unik:** {detail.kode_unik}")
            st.markdown(f"**Posisi:** {detail.posisi}")
            st.markdown(f"**PIC Recruiter:** {detail.pic_recruiter}")
            st.markdown(f"**Business Unit:** {detail.business_unit}")
            st.markdown(f"**Direktorat:** {detail.direktorat}")
            st.markdown(f"**Divisi:** {detail.divisi or '-'}")
            st.markdown(f"**Department:** {detail.department or '-'}")
        
        with col2:
            st.markdown(f"**Status:** {detail.status}")
            st.markdown(f"**Filter Kategorisasi:** {detail.filter_kategorisasi_fptk}")
            st.markdown(f"**Tanggal FPTK:** {detail.fptk_date_real.strftime('%d/%m/%Y') if detail.fptk_date_real else '-'}")
            st.markdown(f"**Level:** {detail.level_fptk} (Level {detail.level_number})")
            st.markdown(f"**SLA:** {detail.jumlah_sla} hari")
            st.markdown(f"**Deadline SLA:** {detail.deadline_sla.strftime('%d/%m/%Y') if detail.deadline_sla else '-'}")
            st.markdown(f"**Vacancy:** {detail.vacancy}")
        
        # Jika bukan admin dan bukan punya PIC ini, tampilkan pesan
        if not can_edit:
            st.warning("⚠️ Anda hanya bisa mengedit data FPTK milik PIC Anda sendiri.")
        else:
            st.markdown("---")
            st.subheader("✏️ Edit Data (Untuk PIC ini)")
            
            with st.form("edit_fptk_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_status = st.selectbox("Status", ["OP", "Closed", "Cancel"], 
                                             index=["OP", "Closed", "Cancel"].index(detail.status or "OP"))
                    new_filter = st.text_input("Filter Kategorisasi", value=detail.filter_kategorisasi_fptk or "")
                with col2:
                    new_pic = st.selectbox("PIC Recruiter", [p[0] for p in db.query(MasterDropdown.pic_recrucher).distinct().all() if p[0]], 
                                          index=0)
                    new_vacancy = st.number_input("Vacancy", min_value=1, value=detail.vacancy or 1)
                with col3:
                    new_remark = st.text_area("Remark", value=detail.remark or "")
                
                if st.form_submit_button("💾 Update FPTK", type="primary"):
                    detail.status = new_status
                    detail.filter_kategorisasi_fptk = new_filter
                    detail.pic_recruiter = new_pic
                    detail.vacancy = new_vacancy
                    detail.remark = new_remark
                    detail.last_updated_at = datetime.now()
                    detail.last_compile_action = "MANUAL_EDIT"
                    db.commit()
                    st.success("✅ Data FPTK berhasil diupdate!")
                    st.rerun()
