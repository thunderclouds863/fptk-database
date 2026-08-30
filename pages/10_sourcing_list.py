import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DBSourcing, User, FPTK, MasterDropdown
from core.auth import get_current_user, is_admin
from datetime import datetime
import time

# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_data(ttl=3600)
def get_sourcing_list_options(_db):
    """Mengambil semua opsi untuk sourcing list - cache 1 jam"""
    try:
        master = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
        
        # Ambil dari data existing
        sourcing_data = _db.query(DBSourcing).all()
        sumber_options = sorted(set([s.sumber_sourcing for s in sourcing_data if s.sumber_sourcing]))
        model_options = sorted(set([s.model_rekrutmen for s in sourcing_data if s.model_rekrutmen]))
        
        return {
            'pic_options': pic_options,
            'sumber_options': sumber_options,
            'model_options': model_options
        }
    except Exception as e:
        return {
            'pic_options': [],
            'sumber_options': [],
            'model_options': []
        }


@st.cache_data(ttl=3600)
def get_sourcing_list_static_options():
    """Opsi statis - cache 1 jam"""
    return {
        'pipeline_status_options': ["", "V", "X"],
        'pipeline_stages': [
            "Sourcing HR", "Shortlist CV", "Psikotes", "HR Interview",
            "Technical Test", "Market Visit", "User Interview",
            "Panel Interview", "Reference Check", "MCU", "Offering", "Day 1"
        ]
    }


def show_sourcing_list():
    st.title("📋 Database Sourcing")
    st.markdown("Lihat, filter, edit, dan hapus data kandidat.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # 🔥🔥🔥 LOAD FROM CACHE 🔥🔥🔥
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        options = get_sourcing_list_options(db)
        static_options = get_sourcing_list_static_options()
    
    pic_options = options['pic_options']
    sumber_options = options['sumber_options']
    model_options = options['model_options']
    pipeline_status_options = static_options['pipeline_status_options']
    pipeline_stages = static_options['pipeline_stages']
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter")
        
        search = st.text_input("🔎 Cari (Nama / Posisi / Kode Unik)", placeholder="Ketik keyword...")
        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + pic_options)
        sumber_filter = st.selectbox("Sumber Sourcing", ["Semua"] + sumber_options)
        model_filter = st.selectbox("Model Rekrutmen", ["Semua"] + model_options)
        
        stage_filter = st.selectbox("Tahap Pipeline", ["Semua"] + pipeline_stages)
        
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now().replace(year=2020))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())
        
        show_mine = st.checkbox("Hanya data saya", value=False) if not admin else False
        
        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()
    
    # ============================================================
    # BUILD QUERY
    # ============================================================
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
    if sumber_filter != "Semua":
        query = query.filter(DBSourcing.sumber_sourcing == sumber_filter)
    if model_filter != "Semua":
        query = query.filter(DBSourcing.model_rekrutmen == model_filter)
    
    if show_mine and not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)
    
    if date_from:
        query = query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        query = query.filter(DBSourcing.sourcing_date <= date_to)
    
    # Stage filter - mapping ke field
    stage_field_map = {
        "Sourcing HR": DBSourcing.sourcing_hr,
        "Shortlist CV": DBSourcing.shortlist_cv,
        "Psikotes": DBSourcing.psikotes,
        "HR Interview": DBSourcing.hr_interview,
        "Technical Test": DBSourcing.technical_test_case_study,
        "Market Visit": DBSourcing.market_visit,
        "User Interview": DBSourcing.user_interview,
        "Panel Interview": DBSourcing.panel_interview,
        "Reference Check": DBSourcing.reference_check,
        "MCU": DBSourcing.mcu,
        "Offering": DBSourcing.offering,
        "Day 1": DBSourcing.day1,
    }
    
    if stage_filter != "Semua" and stage_filter in stage_field_map:
        query = query.filter(stage_field_map[stage_filter].isnot(None))
    
    total = query.count()
    st.markdown(f"**Total Kandidat: {total}**")
    
    if total > 0:
        page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
        page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
        offset = (page - 1) * page_size
        
        df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)
        
        st.dataframe(
            df,
            use_container_width=True,
            height=500,
            column_config={
                "id": "ID",
                "no": "No",
                "nama": "Nama Kandidat",
                "posisi": "Posisi",
                "kode_unik": "Kode Unik",
                "rekruter": "PIC",
                "sumber_sourcing": "Sumber",
                "sourcing_hr": "Sourcing HR",
                "shortlist_cv": "Shortlist",
                "psikotes": "Psikotes",
                "hr_interview": "HR Interview",
                "offering": "Offering",
                "day1": "Day 1",
                "sourcing_date": "Tgl Sourcing"
            }
        )
        
        # ============================================================
        # ACTION BUTTONS
        # ============================================================
        st.markdown("---")
        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
        
        selected_id = st.selectbox("Pilih ID untuk aksi", df['id'].tolist())
        
        with col1:
            if st.button("📋 Detail", use_container_width=True):
                st.session_state['detail_id'] = selected_id
                st.session_state['page'] = "sourcing_detail"
                st.rerun()
        
        with col2:
            if st.button("✏️ Edit", use_container_width=True):
                st.session_state['edit_id'] = selected_id
                st.session_state['page'] = "sourcing_edit"
                st.rerun()
        
        with col3:
            if st.button("🗑️ Hapus", use_container_width=True):
                if admin or pic_filter == user.pic_recruiter:
                    confirm = st.warning(f"Yakin ingin menghapus ID {selected_id}?")
                    if st.button("Ya, Hapus", key="confirm_delete"):
                        record = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
                        if record:
                            db.delete(record)
                            db.commit()
                            st.success("Data berhasil dihapus!")
                            st.rerun()
                else:
                    st.error("Anda tidak punya akses untuk menghapus data ini.")
        
        with col4:
            if st.button("📥 Export CSV", use_container_width=True):
                csv = df.to_csv(index=False)
                st.download_button("Download", csv, f"sourcing_export_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    else:
        st.info("Tidak ada data sourcing dengan filter yang dipilih.")
