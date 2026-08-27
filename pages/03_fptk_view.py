import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import FPTK, User, MasterDropdown
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import plotly.express as px
import re

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
    # LOAD MASTER DATA UNTUK DROPDOWN
    # ============================================================
    master_records = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
    bu_options = sorted(set([m.bu for m in master_records if m.bu]))
    alasan_options = sorted(set([m.alasan for m in master_records if m.alasan]))
    category_options = sorted(set([m.category_fptk for m in master_records if m.category_fptk]))
    filter_options = sorted(set([m.filter_fptk for m in master_records if m.filter_fptk]))
    status_options = ["OP", "Closed", "Cancel"]
    lokasi_onboarding_options = sorted(set([m.lokasi_onboarding for m in master_records if m.lokasi_onboarding]))
    direktorat_options = sorted(set([m.nama_direktorat for m in master_records if m.nama_direktorat]))
    pic_options_all = sorted(set([m.pic_recruiter for m in master_records if m.pic_recruiter]))
    kode_pic_options = sorted(set([m.kode_pic for m in master_records if m.kode_pic]))
    
    # Level options
    LEVEL_OPTIONS = []
    for num in range(1, 6):
        for letter in ['A', 'B']:
            LEVEL_OPTIONS.append(f"{num}{letter}")
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter FPTK")
        
        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
        status_filter = st.selectbox("Status", ["Semua"] + status_options)
        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + pic_options_all)
        bu_filter = st.selectbox("Business Unit", ["Semua"] + bu_options)
        dir_filter = st.selectbox("Direktorat", ["Semua"] + direktorat_options)
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
    
    # ============================================================
    # PILIH DATA UNTUK EDIT - PAKAI KODE UNIK / POSISI
    # ============================================================
    st.markdown("### 📋 Pilih Data untuk Diedit")
    
    # Buat list pilihan dengan format "Kode Unik | Posisi"
    select_options = {}
    for _, row in df.iterrows():
        kode = row.get('kode_unik', '')
        posisi = row.get('posisi', '')
        display = f"{kode} | {posisi[:50]}..." if len(posisi) > 50 else f"{kode} | {posisi}"
        select_options[display] = row.get('id')
    
    selected_display = st.selectbox(
        "Pilih FPTK (Kode Unik | Posisi)",
        list(select_options.keys())
    )
    
    if selected_display:
        selected_id = select_options[selected_display]
    else:
        selected_id = None
    
    if not selected_id:
        st.info("Pilih data dari daftar di atas.")
        return
    
    # ============================================================
    # LOAD DETAIL DATA
    # ============================================================
    detail = db.query(FPTK).filter(FPTK.id == selected_id).first()
    if not detail:
        st.error("Data tidak ditemukan")
        return
    
    # Cek akses edit
    can_edit = admin or (detail.pic_recruiter == user.pic_recruiter)
    
    # ============================================================
    # DETAIL VIEW (LENGKAP)
    # ============================================================
    st.markdown("---")
    st.markdown("### 📋 Detail FPTK")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        st.markdown(f"**Posisi:** {detail.posisi}")
        st.markdown(f"**PIC Recruiter:** {detail.pic_recruiter}")
        st.markdown(f"**Kode PIC:** {detail.kode_pic or '-'}")
        st.markdown(f"**Business Unit:** {detail.business_unit}")
        st.markdown(f"**Direktorat:** {detail.direktorat}")
        st.markdown(f"**Divisi:** {detail.divisi or '-'}")
        st.markdown(f"**Department:** {detail.department or '-'}")
        st.markdown(f"**Level FPTK:** {detail.level_fptk} (Level {detail.level_number})")
        st.markdown(f"**Alasan Permintaan FPTK:** {detail.alasan_permintaan_fptk or '-'}")
        st.markdown(f"**Category FPTK:** {detail.category_fptk or '-'}")
    
    with col2:
        st.markdown(f"**Status:** {detail.status}")
        st.markdown(f"**Filter Kategorisasi:** {detail.filter_kategorisasi_fptk}")
        st.markdown(f"**Tanggal FPTK (Real):** {detail.fptk_date_real.strftime('%d/%m/%Y') if detail.fptk_date_real else '-'}")
        st.markdown(f"**Tanggal FPTK (Kode):** {detail.fptk_date_kode.strftime('%d/%m/%Y') if detail.fptk_date_kode else '-'}")
        st.markdown(f"**Vacancy:** {detail.vacancy}")
        st.markdown(f"**Jumlah SLA:** {detail.jumlah_sla} hari")
        st.markdown(f"**Deadline SLA:** {detail.deadline_sla.strftime('%d/%m/%Y') if detail.deadline_sla else '-'}")
        st.markdown(f"**Detail SLA:** {detail.detail_sla or '-'}")
        st.markdown(f"**FPTK Cancel Date:** {detail.fptk_cancel_date.strftime('%d/%m/%Y') if detail.fptk_cancel_date else '-'}")
        st.markdown(f"**Offering Date:** {detail.offering_date.strftime('%d/%m/%Y') if detail.offering_date else '-'}")
        st.markdown(f"**Week FPTK:** {detail.week_fptk_date or '-'}")
        st.markdown(f"**Month FPTK:** {detail.month_fptk_date or '-'}")
    
    # Row 3: Data Tambahan
    st.markdown("---")
    st.markdown("### 📝 Data Tambahan")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nama Kandidat:** {detail.nama_kandidat or '-'}")
        st.markdown(f"**Lokasi Kerja:** {detail.lokasi_kerja or '-'}")
        st.markdown(f"**Lokasi HR:** {detail.lokasi_hr or '-'}")
        st.markdown(f"**User (Manager):** {detail.user_manager or '-'}")
        st.markdown(f"**Indirect User:** {detail.indirect_user or '-'}")
        st.markdown(f"**Status Karyawan:** {detail.status_karyawan or '-'}")
    with col2:
        st.markdown(f"**Estimasi Join:** {detail.estimasi_join.strftime('%d/%m/%Y') if detail.estimasi_join else '-'}")
        st.markdown(f"**Kebutuhan Laptop:** {detail.kebutuhan_laptop or '-'}")
        st.markdown(f"**Lokasi Onboarding:** {detail.lokasi_onboarding or '-'}")
        st.markdown(f"**Kode BU:** {detail.kode_bu or '-'}")
        st.markdown(f"**FPTK Availability:** {detail.fptk_availability or '-'}")
        st.markdown(f"**Remark:** {detail.remark or '-'}")
    
    # Audit
    st.markdown("---")
    st.markdown("### 📋 Audit")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Created At:** {detail.created_at.strftime('%d/%m/%Y %H:%M') if detail.created_at else '-'}")
        st.markdown(f"**Last Updated:** {detail.last_updated_at.strftime('%d/%m/%Y %H:%M') if detail.last_updated_at else '-'}")
    with col2:
        st.markdown(f"**Source File:** {detail.source_file or '-'}")
        st.markdown(f"**Last Compile Action:** {detail.last_compile_action or '-'}")
    
    # ============================================================
    # EDIT FORM (LENGKAP)
    # ============================================================
    if not can_edit:
        st.warning("⚠️ Anda hanya bisa mengedit data FPTK milik PIC Anda sendiri.")
    else:
        st.markdown("---")
        st.markdown("### ✏️ Edit Data FPTK")
        st.caption(f"{'Admin - Anda bisa mengedit semua field' if admin else 'Edit data milik PIC Anda'}")
        
        with st.form("edit_fptk_form"):
            st.markdown("#### Data Utama")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Kode Unik - Admin bisa edit, user biasa readonly
                if admin:
                    new_kode_unik = st.text_input("Kode Unik", value=detail.kode_unik or "")
                else:
                    new_kode_unik = st.text_input("Kode Unik", value=detail.kode_unik or "", disabled=True)
                
                new_posisi = st.text_input("Posisi", value=detail.posisi or "")
                new_pic_recruiter = st.selectbox("PIC Recruiter", pic_options_all, 
                                                 index=pic_options_all.index(detail.pic_recruiter) if detail.pic_recruiter in pic_options_all else 0)
                new_kode_pic = st.selectbox("Kode PIC", [""] + kode_pic_options,
                                            index=(kode_pic_options.index(detail.kode_pic) + 1) if detail.kode_pic in kode_pic_options else 0)
            
            with col2:
                new_business_unit = st.selectbox("Business Unit", [""] + bu_options,
                                                 index=(bu_options.index(detail.business_unit) + 1) if detail.business_unit in bu_options else 0)
                new_direktorat = st.selectbox("Direktorat", [""] + direktorat_options,
                                              index=(direktorat_options.index(detail.direktorat) + 1) if detail.direktorat in direktorat_options else 0)
                new_divisi = st.text_input("Divisi", value=detail.divisi or "")
                new_department = st.text_input("Department", value=detail.department or "")
            
            with col3:
                new_status = st.selectbox("Status", status_options,
                                          index=status_options.index(detail.status) if detail.status in status_options else 0)
                
                # Level dropdown
                default_level = detail.level_fptk or "1A"
                new_level_fptk = st.selectbox("Level FPTK", LEVEL_OPTIONS,
                                              index=LEVEL_OPTIONS.index(default_level) if default_level in LEVEL_OPTIONS else 0)
                
                # Auto level number dari level
                if new_level_fptk:
                    match = re.search(r'(\d+)', new_level_fptk)
                    new_level_number = int(match.group(1)) if match else 1
                else:
                    new_level_number = detail.level_number or 1
                st.text_input("Level Number (auto)", value=str(new_level_number), disabled=True)
                
                new_vacancy = st.number_input("Vacancy", min_value=1, value=detail.vacancy or 1)
            
            st.markdown("---")
            st.markdown("#### Alasan & Category")
            col1, col2 = st.columns(2)
            with col1:
                new_alasan = st.selectbox("Alasan Permintaan FPTK", [""] + alasan_options,
                                          index=(alasan_options.index(detail.alasan_permintaan_fptk) + 1) if detail.alasan_permintaan_fptk in alasan_options else 0)
            with col2:
                new_category = st.selectbox("Category FPTK", [""] + category_options,
                                            index=(category_options.index(detail.category_fptk) + 1) if detail.category_fptk in category_options else 0)
            
            st.markdown("---")
            st.markdown("#### Tanggal")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_fptk_date_real = st.date_input("FPTK Date Real", 
                                                   value=detail.fptk_date_real if detail.fptk_date_real else datetime.now().date())
                new_fptk_date_kode = st.date_input("FPTK Date Kode",
                                                   value=detail.fptk_date_kode if detail.fptk_date_kode else datetime.now().date())
            with col2:
                new_fptk_cancel_date = st.date_input("FPTK Cancel Date",
                                                     value=detail.fptk_cancel_date if detail.fptk_cancel_date else None)
                new_offering_date = st.date_input("Offering Date",
                                                  value=detail.offering_date if detail.offering_date else None)
            with col3:
                new_estimasi_join = st.date_input("Estimasi Join",
                                                  value=detail.estimasi_join if detail.estimasi_join else None)
            
            st.markdown("---")
            st.markdown("#### Data Tambahan")
            col1, col2 = st.columns(2)
            with col1:
                new_nama_kandidat = st.text_input("Nama Kandidat", value=detail.nama_kandidat or "")
                new_lokasi_kerja = st.text_input("Lokasi Kerja", value=detail.lokasi_kerja or "")
                new_lokasi_hr = st.text_input("Lokasi HR", value=detail.lokasi_hr or "")
                new_user_manager = st.text_input("User (Manager)", value=detail.user_manager or "")
                new_indirect_user = st.text_input("Indirect User", value=detail.indirect_user or "")
            with col2:
                new_status_karyawan = st.text_input("Status Karyawan", value=detail.status_karyawan or "")
                new_kebutuhan_laptop = st.selectbox("Kebutuhan Laptop", ["", "Ya", "Tidak"],
                                                    index=["", "Ya", "Tidak"].index(detail.kebutuhan_laptop) if detail.kebutuhan_laptop in ["", "Ya", "Tidak"] else 0)
                new_lokasi_onboarding = st.selectbox("Lokasi Onboarding", [""] + lokasi_onboarding_options,
                                                     index=(lokasi_onboarding_options.index(detail.lokasi_onboarding) + 1) if detail.lokasi_onboarding in lokasi_onboarding_options else 0)
                new_fptk_availability = st.selectbox("FPTK Availability", ["", "Y", "N"],
                                                     index=["", "Y", "N"].index(detail.fptk_availability) if detail.fptk_availability in ["", "Y", "N"] else 0)
                new_remark = st.text_area("Remark", value=detail.remark or "")
            
            st.markdown("---")
            submitted = st.form_submit_button("💾 Update FPTK", type="primary")
        
        # ============================================================
        # PROSES UPDATE
        # ============================================================
        if submitted:
            try:
                # Update semua field
                if admin and new_kode_unik:
                    detail.kode_unik = new_kode_unik
                    detail.posisi = new_posisi
                    detail.pic_recruiter = new_pic_recruiter
                    detail.kode_pic = new_kode_pic
                    detail.business_unit = new_business_unit
                    detail.direktorat = new_direktorat
                    detail.divisi = new_divisi
                    detail.department = new_department
                    detail.status = new_status
                    detail.level_fptk = new_level_fptk
                    detail.level_number = new_level_number
                    detail.vacancy = new_vacancy
                    detail.alasan_permintaan_fptk = new_alasan
                    detail.category_fptk = new_category
                    detail.fptk_date_real = new_fptk_date_real
                    detail.fptk_date_kode = new_fptk_date_kode
                    detail.fptk_cancel_date = new_fptk_cancel_date
                    detail.offering_date = new_offering_date
                    detail.estimasi_join = new_estimasi_join
                    detail.nama_kandidat = new_nama_kandidat
                    detail.lokasi_kerja = new_lokasi_kerja
                    detail.lokasi_hr = new_lokasi_hr
                    detail.user_manager = new_user_manager
                    detail.indirect_user = new_indirect_user
                    detail.status_karyawan = new_status_karyawan
                    detail.kebutuhan_laptop = new_kebutuhan_laptop
                    detail.lokasi_onboarding = new_lokasi_onboarding
                    detail.fptk_availability = new_fptk_availability
                    detail.remark = new_remark
                
                # Hitung ulang SLA jika level berubah
                if new_level_number <= 3:
                    sla_days = 30
                elif new_level_number == 4:
                    sla_days = 45
                else:
                    sla_days = 60
                detail.jumlah_sla = sla_days
                
                if detail.fptk_date_real and sla_days:
                    detail.deadline_sla = detail.fptk_date_real + timedelta(days=sla_days)
                
                detail.last_updated_at = datetime.now()
                detail.last_compile_action = "MANUAL_EDIT"
                
                db.commit()
                st.success("✅ Data FPTK berhasil diupdate!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
