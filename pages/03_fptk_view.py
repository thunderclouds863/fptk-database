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
        
        # Show all columns except audit columns and blacklisted_by
        exclude_cols = [
            'created_at', 'last_updated_at', 'last_compile_action', 
            'source_file', 'source_file_hash', 'source_user_id', 'source_cycle_id',
            'blacklisted_by'  # Tambahkan ini
        ]
        display_cols = [c for c in df.columns if c not in exclude_cols]
        
        # Map column names to more readable format
        column_config = {
            "id": "ID",
            "no": "No",
            "sourcing_date": "Tgl Sourcing",
            "kode_unik": "Kode Unik",
            "posisi": "Posisi",
            "model_rekrutmen": "Model Rekrutmen",
            "rekruter": "PIC Recruiter",
            "sumber_sourcing": "Sumber Sourcing",
            "nama": "Nama Kandidat",
            "nama_universitas_top10": "Universitas Top 10",
            "nama_universitas_lainnya": "Universitas Lainnya",
            "jenjang_pendidikan": "Jenjang Pendidikan",
            "jurusan": "Jurusan",
            "tahun_lulus": "Tahun Lulus",
            "ipk": "IPK",
            "skor_bahasa_inggris": "Skor Bahasa Inggris",
            "university_tier": "University Tier",
            "ipk_tier": "IPK Tier",
            "nomor_hp": "No HP",
            "email": "Email",
            "domisili": "Domisili",
            "last_position": "Posisi Terakhir",
            "last_tenure": "Masa Kerja Terakhir",
            "last_company": "Perusahaan Terakhir",
            "total_tenure": "Total Masa Kerja",
            "pernah_di_fmcg": "Pernah di FMCG",
            "sourcing_freelance": "Sourcing Freelance",
            "tanggal_sourcing_freelance": "Tgl Sourcing Freelance",
            "sourcing_hr": "Sourcing HR",
            "detail_keterangan_sourcing_hr": "Keterangan Sourcing HR",
            "tanggal_sourcing": "Tgl Sourcing",
            "shortlist_cv": "Shortlist CV",
            "detail_keterangan_shortlist_cv": "Keterangan Shortlist",
            "tanggal_shortlist_cv": "Tgl Shortlist",
            "psikotes": "Psikotes",
            "kode_psikotes": "Kode Psikotes",
            "detail_keterangan_psikotes": "Keterangan Psikotes",
            "tanggal_psikotes": "Tgl Psikotes",
            "nilai_logika": "Nilai Logika",
            "nilai_iq": "Nilai IQ",
            "nilai_daya_tangkap": "Nilai Daya Tangkap",
            "nilai_ra": "Nilai RA",
            "disc": "DISC",
            "hr_interview": "HR Interview",
            "detail_keterangan_hr_interview": "Keterangan HR Interview",
            "tanggal_hr_interview": "Tgl HR Interview",
            "technical_test_case_study": "Technical Test",
            "detail_keterangan_technical_test": "Keterangan Technical Test",
            "tanggal_technical_test": "Tgl Technical Test",
            "market_visit": "Market Visit",
            "detail_market_visit": "Keterangan Market Visit",
            "tanggal_market_visit": "Tgl Market Visit",
            "user_interview": "User Interview",
            "detail_keterangan_user_interview": "Keterangan User Interview",
            "tanggal_user_interview": "Tgl User Interview",
            "panel_interview": "Panel Interview",
            "detail_keterangan_panel_interview": "Keterangan Panel Interview",
            "tanggal_panel_interview": "Tgl Panel Interview",
            "reference_check": "Reference Check",
            "detail_keterangan_reference_check": "Keterangan Reference Check",
            "tanggal_reference_check": "Tgl Reference Check",
            "mcu": "MCU",
            "detail_keterangan_mcu": "Keterangan MCU",
            "tanggal_mcu": "Tgl MCU",
            "offering": "Offering",
            "detail_keterangan_offering": "Keterangan Offering",
            "tanggal_offering": "Tgl Offering",
            "notes": "Catatan",
            "day1": "Day 1",
            "detail_keterangan_day1": "Keterangan Day 1",
            "tanggal_day1": "Tgl Day 1",
            "is_blacklisted": "Blacklist",
            "blacklisted_at": "Tgl Blacklist",
            "blacklist_reason": "Alasan Blacklist"
        }
        
        # Create display dataframe
        display_df = df[display_cols].copy()
        
        # Rename columns safely WITHOUT duplicates
        new_columns = []
        seen_names = set()
        
        for col in display_df.columns:
            new_name = column_config.get(col, col)
            
            # If this name already exists, use original column name
            if new_name in seen_names:
                new_columns.append(col)  # Keep original name
            else:
                new_columns.append(new_name)
                seen_names.add(new_name)
        
        display_df.columns = new_columns
        
        # Display the dataframe
        st.dataframe(
            display_df,
            use_container_width=True,
            height=500
        )
        
        # Detail and Edit view
        st.markdown("---")
        st.subheader("✏️ Detail & Edit Kandidat")
        
        # Select candidate to edit
        selected_id = st.selectbox("Pilih ID untuk lihat/detail", df['id'].tolist())
        
        if selected_id:
            detail = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
            if detail:
                # Display all fields in expandable sections
                with st.expander("📋 Data Pribadi & Pendidikan", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**ID:** {detail.id}")
                        st.markdown(f"**No:** {detail.no or '-'}")
                        st.markdown(f"**Nama:** {detail.nama}")
                        st.markdown(f"**Posisi:** {detail.posisi or '-'}")
                        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    with col2:
                        st.markdown(f"**Email:** {detail.email or '-'}")
                        st.markdown(f"**No HP:** {detail.nomor_hp or '-'}")
                        st.markdown(f"**Domisili:** {detail.domisili or '-'}")
                        st.markdown(f"**Sumber Sourcing:** {detail.sumber_sourcing or '-'}")
                    with col3:
                        st.markdown(f"**Universitas Top 10:** {detail.nama_universitas_top10 or '-'}")
                        st.markdown(f"**Universitas Lainnya:** {detail.nama_universitas_lainnya or '-'}")
                        st.markdown(f"**Jurusan:** {detail.jurusan or '-'}")
                        st.markdown(f"**IPK:** {detail.ipk or '-'}")
                
                with st.expander("💼 Pengalaman Kerja"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Posisi Terakhir:** {detail.last_position or '-'}")
                        st.markdown(f"**Perusahaan Terakhir:** {detail.last_company or '-'}")
                    with col2:
                        st.markdown(f"**Masa Kerja Terakhir:** {detail.last_tenure or '-'}")
                        st.markdown(f"**Total Masa Kerja:** {detail.total_tenure or '-'}")
                        st.markdown(f"**Pernah di FMCG:** {detail.pernah_di_fmcg or '-'}")
                
                with st.expander("📊 Pipeline Status"):
                    pipeline = [
                        ("Sourcing HR", detail.sourcing_hr, detail.tanggal_sourcing, detail.detail_keterangan_sourcing_hr),
                        ("Shortlist CV", detail.shortlist_cv, detail.tanggal_shortlist_cv, detail.detail_keterangan_shortlist_cv),
                        ("Psikotes", detail.psikotes, detail.tanggal_psikotes, detail.detail_keterangan_psikotes),
                        ("HR Interview", detail.hr_interview, detail.tanggal_hr_interview, detail.detail_keterangan_hr_interview),
                        ("Technical Test", detail.technical_test_case_study, detail.tanggal_technical_test, detail.detail_keterangan_technical_test),
                        ("Market Visit", detail.market_visit, detail.tanggal_market_visit, detail.detail_market_visit),
                        ("User Interview", detail.user_interview, detail.tanggal_user_interview, detail.detail_keterangan_user_interview),
                        ("Panel Interview", detail.panel_interview, detail.tanggal_panel_interview, detail.detail_keterangan_panel_interview),
                        ("Reference Check", detail.reference_check, detail.tanggal_reference_check, detail.detail_keterangan_reference_check),
                        ("MCU", detail.mcu, detail.tanggal_mcu, detail.detail_keterangan_mcu),
                        ("Offering", detail.offering, detail.tanggal_offering, detail.detail_keterangan_offering),
                        ("Day 1", detail.day1, detail.tanggal_day1, detail.detail_keterangan_day1),
                    ]
                    pipeline_df = pd.DataFrame(pipeline, columns=["Tahap", "Status", "Tanggal", "Keterangan"])
                    st.dataframe(pipeline_df, use_container_width=True)
                
                with st.expander("📝 Catatan & Blacklist"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Catatan:** {detail.notes or '-'}")
                    with col2:
                        st.markdown(f"**Blacklist:** {'Ya' if detail.is_blacklisted else 'Tidak'}")
                        if detail.is_blacklisted:
                            st.markdown(f"**Tgl Blacklist:** {detail.blacklisted_at.strftime('%d/%m/%Y %H:%M') if detail.blacklisted_at else '-'}")
                            st.markdown(f"**Alasan:** {detail.blacklist_reason or '-'}")
                
                # Edit Section
                st.markdown("---")
                st.subheader("✏️ Edit Data Kandidat")
                
                # Check if user is admin or the owner
                is_owner = detail.rekruter == user.pic_recruiter
                can_edit = is_admin(db) or is_owner
                
                if not can_edit:
                    st.warning("⚠️ Anda hanya bisa mengedit data yang Anda input sendiri. Hubungi admin untuk mengedit data ini.")
                else:
                    with st.form("edit_sourcing_full", clear_on_submit=False):
                        st.markdown("### 📋 Data Pribadi & Pendidikan")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            nama = st.text_input("Nama Kandidat *", value=detail.nama or "")
                            posisi = st.text_input("Posisi *", value=detail.posisi or "")
                            kode_unik = st.text_input("Kode Unik *", value=detail.kode_unik or "")
                            sourcing_date = st.date_input("Tanggal Sourcing", value=detail.sourcing_date if detail.sourcing_date else datetime.now().date())
                        
                        with col2:
                            email = st.text_input("Email", value=detail.email or "")
                            nomor_hp = st.text_input("No HP", value=detail.nomor_hp or "")
                            domisili = st.text_input("Domisili", value=detail.domisili or "")
                            rekruter = st.text_input("PIC Recruiter", value=detail.rekruter or "")
                        
                        with col3:
                            sumber_sourcing = st.text_input("Sumber Sourcing", value=detail.sumber_sourcing or "")
                            model_rekrutmen = st.text_input("Model Rekrutmen", value=detail.model_rekrutmen or "")
                            no = st.number_input("No", value=detail.no or 0, step=1)
                            pernah_di_fmcg = st.selectbox("Pernah di FMCG", options=["", "Ya", "Tidak"], 
                                                        index=0 if not detail.pernah_di_fmcg else (1 if detail.pernah_di_fmcg == "Ya" else 2))
                        
                        st.markdown("---")
                        st.markdown("### 🎓 Pendidikan")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            jenjang_pendidikan = st.text_input("Jenjang Pendidikan", value=detail.jenjang_pendidikan or "")
                            nama_universitas_top10 = st.text_input("Nama Universitas Top 10", value=detail.nama_universitas_top10 or "")
                            nama_universitas_lainnya = st.text_input("Nama Universitas Lainnya", value=detail.nama_universitas_lainnya or "")
                        
                        with col2:
                            jurusan = st.text_input("Jurusan", value=detail.jurusan or "")
                            tahun_lulus = st.number_input("Tahun Lulus", value=detail.tahun_lulus or 0, step=1)
                            ipk = st.text_input("IPK", value=str(detail.ipk) if detail.ipk else "")
                        
                        with col3:
                            skor_bahasa_inggris = st.text_input("Skor Bahasa Inggris", value=detail.skor_bahasa_inggris or "")
                            university_tier = st.text_input("University Tier", value=detail.university_tier or "")
                            ipk_tier = st.text_input("IPK Tier", value=detail.ipk_tier or "")
                        
                        st.markdown("---")
                        st.markdown("### 💼 Pengalaman Kerja")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            last_position = st.text_input("Posisi Terakhir", value=detail.last_position or "")
                            last_company = st.text_input("Perusahaan Terakhir", value=detail.last_company or "")
                        
                        with col2:
                            last_tenure = st.text_input("Masa Kerja Terakhir", value=detail.last_tenure or "")
                            total_tenure = st.text_input("Total Masa Kerja", value=detail.total_tenure or "")
                        
                        st.markdown("---")
                        st.markdown("### 📊 Pipeline Stages")
                        
                        # Pipeline fields in grid
                        pipeline_fields = [
                            ("sourcing_hr", "Sourcing HR", "tanggal_sourcing", "detail_keterangan_sourcing_hr"),
                            ("shortlist_cv", "Shortlist CV", "tanggal_shortlist_cv", "detail_keterangan_shortlist_cv"),
                            ("psikotes", "Psikotes", "tanggal_psikotes", "detail_keterangan_psikotes"),
                            ("hr_interview", "HR Interview", "tanggal_hr_interview", "detail_keterangan_hr_interview"),
                            ("technical_test_case_study", "Technical Test", "tanggal_technical_test", "detail_keterangan_technical_test"),
                            ("market_visit", "Market Visit", "tanggal_market_visit", "detail_market_visit"),
                            ("user_interview", "User Interview", "tanggal_user_interview", "detail_keterangan_user_interview"),
                            ("panel_interview", "Panel Interview", "tanggal_panel_interview", "detail_keterangan_panel_interview"),
                            ("reference_check", "Reference Check", "tanggal_reference_check", "detail_keterangan_reference_check"),
                            ("mcu", "MCU", "tanggal_mcu", "detail_keterangan_mcu"),
                            ("offering", "Offering", "tanggal_offering", "detail_keterangan_offering"),
                            ("day1", "Day 1", "tanggal_day1", "detail_keterangan_day1"),
                        ]
                        
                        for i, (status_field, label, date_field, detail_field) in enumerate(pipeline_fields):
                            if i % 3 == 0:
                                cols = st.columns(3)
                            
                            status_value = getattr(detail, status_field)
                            date_value = getattr(detail, date_field)
                            detail_value = getattr(detail, detail_field)
                            
                            with cols[i % 3]:
                                st.markdown(f"**{label}**")
                                new_status = st.text_input(f"Status {label}", value=status_value or "", key=f"status_{status_field}")
                                new_date = st.date_input(f"Tgl {label}", value=date_value if date_value else None, key=f"date_{date_field}")
                                new_detail = st.text_area(f"Keterangan {label}", value=detail_value or "", key=f"detail_{detail_field}", height=50)
                                
                                # Update values
                                setattr(detail, status_field, new_status if new_status else None)
                                setattr(detail, date_field, new_date)
                                setattr(detail, detail_field, new_detail if new_detail else None)
                        
                        st.markdown("---")
                        st.markdown("### 📝 Catatan & Blacklist")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            notes = st.text_area("Catatan", value=detail.notes or "", height=100)
                        
                        with col2:
                            is_blacklisted = st.checkbox("Blacklist", value=detail.is_blacklisted or False)
                            blacklist_reason = st.text_area("Alasan Blacklist", value=detail.blacklist_reason or "", height=100)
                        
                        st.markdown("---")
                        st.markdown("### 🔧 Audit Info")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Created At:** {detail.created_at.strftime('%d/%m/%Y %H:%M') if detail.created_at else '-'}")
                        with col2:
                            st.markdown(f"**Last Updated:** {detail.last_updated_at.strftime('%d/%m/%Y %H:%M') if detail.last_updated_at else '-'}")
                        
                        # Submit button
                        submitted = st.form_submit_button("💾 Simpan Perubahan")
                        
                        if submitted:
                            try:
                                # Update all fields
                                detail.nama = nama
                                detail.posisi = posisi
                                detail.kode_unik = kode_unik
                                detail.sourcing_date = sourcing_date
                                detail.email = email if email else None
                                detail.nomor_hp = nomor_hp if nomor_hp else None
                                detail.domisili = domisili if domisili else None
                                detail.rekruter = rekruter if rekruter else None
                                detail.sumber_sourcing = sumber_sourcing if sumber_sourcing else None
                                detail.model_rekrutmen = model_rekrutmen if model_rekrutmen else None
                                detail.no = no if no else None
                                detail.pernah_di_fmcg = pernah_di_fmcg if pernah_di_fmcg != "" else None
                                
                                # Education
                                detail.jenjang_pendidikan = jenjang_pendidikan if jenjang_pendidikan else None
                                detail.nama_universitas_top10 = nama_universitas_top10 if nama_universitas_top10 else None
                                detail.nama_universitas_lainnya = nama_universitas_lainnya if nama_universitas_lainnya else None
                                detail.jurusan = jurusan if jurusan else None
                                detail.tahun_lulus = tahun_lulus if tahun_lulus else None
                                
                                # Parse IPK
                                try:
                                    if ipk:
                                        detail.ipk = float(ipk)
                                    else:
                                        detail.ipk = None
                                except ValueError:
                                    st.error("IPK harus berupa angka (contoh: 3.5)")
                                    return
                                
                                detail.skor_bahasa_inggris = skor_bahasa_inggris if skor_bahasa_inggris else None
                                detail.university_tier = university_tier if university_tier else None
                                detail.ipk_tier = ipk_tier if ipk_tier else None
                                
                                # Experience
                                detail.last_position = last_position if last_position else None
                                detail.last_company = last_company if last_company else None
                                detail.last_tenure = last_tenure if last_tenure else None
                                detail.total_tenure = total_tenure if total_tenure else None
                                
                                # Notes and blacklist
                                detail.notes = notes if notes else None
                                detail.is_blacklisted = is_blacklisted
                                detail.blacklist_reason = blacklist_reason if blacklist_reason else None
                                if is_blacklisted and not detail.blacklisted_at:
                                    detail.blacklisted_at = datetime.now()
                                elif not is_blacklisted:
                                    detail.blacklisted_at = None
                                
                                # Update timestamp
                                detail.last_updated_at = datetime.now()
                                detail.last_compile_action = "Manual Edit"
                                
                                db.commit()
                                st.success("✅ Data berhasil diupdate!")
                                st.rerun()
                                
                            except Exception as e:
                                db.rollback()
                                st.error(f"❌ Gagal mengupdate data: {str(e)}")
    else:
        st.info("Tidak ada data sourcing dengan filter yang dipilih.")
