import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DBSourcing, User, FPTK
from core.auth import get_current_user, is_admin
from datetime import datetime

def show_sourcing_view():
    st.title("👤 Sourcing Database")
    st.markdown("Lihat dan filter data kandidat sourcing.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔍 Filter Sourcing")
        
        # Search
        search = st.text_input("🔎 Cari (Nama / Posisi / Kode Unik)", placeholder="Ketik keyword...")
        
        # PIC filter
        pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_options)
        
        # Status pipeline filter (simplified)
        stage_options = ["Semua", "Sourcing HR", "Shortlist CV", "Psikotes", "HR Interview", 
                         "User Interview", "Offering", "Day 1"]
        stage_filter = st.selectbox("Tahap Pipeline", stage_options)
        
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari Sourcing", datetime.now().replace(year=2020))
        with col2:
            date_to = st.date_input("Sampai Sourcing", datetime.now())
        
        # Show only my data
        show_mine = st.checkbox("Hanya data saya", value=False)
        
        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()
    
    # Build query
    query = db.query(DBSourcing)
    
    if search:
        search_term = search.strip()
        query = query.filter(
            (DBSourcing.nama.ilike(f"%{search_term}%")) |
            (DBSourcing.posisi.ilike(f"%{search_term}%")) |
            (DBSourcing.kode_unik.ilike(f"%{search_term}%"))
        )
    
    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)
    
    if show_mine and not is_admin(db):
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)
    
    if date_from:
        query = query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        query = query.filter(DBSourcing.sourcing_date <= date_to)
    
    # Stage filter (simplified)
    if stage_filter != "Semua":
        stage_map = {
            "Sourcing HR": DBSourcing.sourcing_hr.isnot(None),
            "Shortlist CV": DBSourcing.shortlist_cv.isnot(None),
            "Psikotes": DBSourcing.psikotes.isnot(None),
            "HR Interview": DBSourcing.hr_interview.isnot(None),
            "User Interview": DBSourcing.user_interview.isnot(None),
            "Offering": DBSourcing.offering.isnot(None),
            "Day 1": DBSourcing.day1.isnot(None),
        }
        if stage_filter in stage_map:
            query = query.filter(stage_map[stage_filter])
    
    total = query.count()
    st.markdown(f"**Total Kandidat: {total}**")
    
    if total > 0:
        page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
        page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
        offset = (page - 1) * page_size
        
        df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)
        
        columns = ['id', 'nama', 'posisi', 'kode_unik', 'rekruter', 'sourcing_date', 
                   'sourcing_hr', 'shortlist_cv', 'psikotes', 'hr_interview', 'offering', 'day1']
        display_cols = [c for c in columns if c in df.columns]
        
        st.dataframe(
            df[display_cols],
            use_container_width=True,
            height=500,
            column_config={
                "id": "ID",
                "nama": "Nama Kandidat",
                "posisi": "Posisi",
                "kode_unik": "Kode Unik",
                "rekruter": "PIC",
                "sourcing_date": "Tgl Sourcing",
                "sourcing_hr": "Sourcing HR",
                "shortlist_cv": "Shortlist",
                "psikotes": "Psikotes",
                "hr_interview": "HR Interview",
                "offering": "Offering",
                "day1": "Day 1"
            }
        )
        
        # Detail view
        st.markdown("---")
        st.subheader("🔍 Detail Kandidat")
        selected_id = st.selectbox("Pilih ID untuk lihat detail", df['id'].tolist())
        
        if selected_id:
            detail = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
            if detail:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Nama:** {detail.nama}")
                    st.markdown(f"**Posisi:** {detail.posisi}")
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**PIC:** {detail.rekruter}")
                    st.markdown(f"**Sumber:** {detail.sumber_sourcing}")
                    st.markdown(f"**Email:** {detail.email or '-'}")
                    st.markdown(f"**No HP:** {detail.nomor_hp or '-'}")
                with col2:
                    st.markdown(f"**Domisili:** {detail.domisili or '-'}")
                    st.markdown(f"**Universitas:** {detail.nama_universitas_top10 or detail.nama_universitas_lainnya or '-'}")
                    st.markdown(f"**Jurusan:** {detail.jurusan or '-'}")
                    st.markdown(f"**IPK:** {detail.ipk or '-'}")
                    st.markdown(f"**Sourcing Date:** {detail.sourcing_date.strftime('%d/%m/%Y') if detail.sourcing_date else '-'}")
                
                # Pipeline status
                st.markdown("---")
                st.subheader("📊 Pipeline Status")
                pipeline = [
                    ("Sourcing HR", detail.sourcing_hr, detail.tanggal_sourcing),
                    ("Shortlist CV", detail.shortlist_cv, detail.tanggal_shortlist_cv),
                    ("Psikotes", detail.psikotes, detail.tanggal_psikotes),
                    ("HR Interview", detail.hr_interview, detail.tanggal_hr_interview),
                    ("User Interview", detail.user_interview, detail.tanggal_user_interview),
                    ("Offering", detail.offering, detail.tanggal_offering),
                    ("Day 1", detail.day1, detail.tanggal_day1),
                ]
                pipeline_df = pd.DataFrame(pipeline, columns=["Tahap", "Status", "Tanggal"])
                st.dataframe(pipeline_df, use_container_width=True)
                
                # Admin: Edit
                if is_admin(db):
                    st.markdown("---")
                    st.subheader("✏️ Edit (Admin)")
                    with st.form("edit_sourcing"):
                        new_name = st.text_input("Nama", value=detail.nama)
                        new_posisi = st.text_input("Posisi", value=detail.posisi or "")
                        new_pic = st.text_input("PIC", value=detail.rekruter or "")
                        if st.form_submit_button("Update"):
                            detail.nama = new_name
                            detail.posisi = new_posisi
                            detail.rekruter = new_pic
                            detail.last_updated_at = datetime.now()
                            db.commit()
                            st.success("Data berhasil diupdate!")
                            st.rerun()
    else:
        st.info("Tidak ada data sourcing dengan filter yang dipilih.")