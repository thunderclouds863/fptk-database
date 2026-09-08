import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DBSourcing, User, FPTK, MasterDropdown, UploadLog
from core.auth import get_current_user, is_admin
from datetime import datetime
import time

# ============================================================
#  CACHE FUNCTIONS 
# ============================================================

@st.cache_data(ttl=3600)
def get_master_options_sourcing_view(_db):
    """Mengambil semua opsi dari MasterDropdown - cache 1 jam"""
    try:
        master = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        
        pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
        bu_options = sorted(set([m.bu for m in master if m.bu]))
        
        return {
            'pic_options': pic_options,
            'bu_options': bu_options
        }
    except Exception as e:
        return {
            'pic_options': [],
            'bu_options': []
        }


@st.cache_data(ttl=3600)
def get_sourcing_options_view():
    """Mengembalikan opsi statis - cache 1 jam"""
    return {
        'sumber_options': ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance", "Lainnya"],
        'model_options': ["Model 1", "Model 2", "Model 3", "Model 4"],  # PERBAIKAN: Sesuai data
        'pipeline_status_options': ["V", "X"],
        'fmcg_options': ["Ya", "Tidak"],
        'jenjang_options': ["SMA/SMK", "D3", "D4", "S1", "S2", "S3"],
        'univ_tier_options': ["Tier 1", "Tier 2", "Tier 3", "Lainnya"],
        'ipk_tier_options': ["> 3.5", "3.0 - 3.5", "2.5 - 3.0", "< 2.5"]
    }


@st.cache_data(ttl=3600)
def get_pipeline_stages_view():
    """Pipeline stages lengkap - cache 1 jam"""
    return [
        {"field": "sourcing_freelance", "label": "Sourcing Freelance", "has_detail": False},
        {"field": "sourcing_hr", "label": "Sourcing HR", "has_detail": True},
        {"field": "shortlist_cv", "label": "Shortlist CV", "has_detail": True},
        {"field": "psikotes", "label": "Psikotes", "has_detail": True},
        {"field": "hr_interview", "label": "HR Interview", "has_detail": True},
        {"field": "technical_test_case_study", "label": "Technical Test", "has_detail": True},
        {"field": "market_visit", "label": "Market Visit", "has_detail": True},
        {"field": "user_interview", "label": "User Interview", "has_detail": True},
        {"field": "panel_interview", "label": "Panel Interview", "has_detail": True},
        {"field": "reference_check", "label": "Reference Check", "has_detail": True},
        {"field": "mcu", "label": "MCU", "has_detail": True},
        {"field": "offering", "label": "Offering", "has_detail": True},
        {"field": "day1", "label": "Day 1", "has_detail": True}
    ]


# ============================================================
# FUNGSI UNTUK DETEKSI WARNING
# ============================================================

def check_sourcing_warnings(record):
    """
    Cek warning pada data sourcing.
    Returns: list of warning messages
    """
    warnings = []
    
    # 1. Cek Model Rekrutmen - Harus Model 1-4
    if record.model_rekrutmen:
        valid_models = ["Model 1", "Model 2", "Model 3", "Model 4"]
        if record.model_rekrutmen not in valid_models:
            warnings.append(f"Model Rekrutmen '{record.model_rekrutmen}' tidak standar (harus Model 1-4)")
    
    # 2. Cek Sumber Sourcing
    if record.sumber_sourcing:
        valid_sumber = ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", 
                       "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", 
                       "Database Internal", "Freelance", "Lainnya"]
        if record.sumber_sourcing not in valid_sumber:
            warnings.append(f"Sumber Sourcing '{record.sumber_sourcing}' tidak standar")
    
    # 3. Cek Kode Unik - Harus ada di FPTK
    if record.kode_unik:
        # Cek di FPTK
        db = next(get_db())
        fptk_exists = db.query(FPTK).filter(FPTK.kode_unik == record.kode_unik).first()
        if not fptk_exists:
            warnings.append(f"Kode Unik '{record.kode_unik}' tidak ditemukan di tabel FPTK")
    
    # 4. Cek Email - Format valid
    if record.email:
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, str(record.email).strip()):
            warnings.append(f"Format email '{record.email}' tidak valid")
    
    # 5. Cek IPK - Range 0-4
    if record.ipk is not None:
        try:
            ipk_val = float(record.ipk)
            if ipk_val < 0 or ipk_val > 4:
                warnings.append(f"IPK '{record.ipk}' di luar range (0-4)")
        except:
            warnings.append(f"IPK '{record.ipk}' bukan angka valid")
    
    # 6. Cek Pipeline Status - Harus V atau X
    pipeline_stages = get_pipeline_stages_view()
    for stage in pipeline_stages:
        status = getattr(record, stage["field"])
        if status and status not in ["V", "X"]:
            warnings.append(f"Status '{stage['label']}' = '{status}' (harus V atau X)")
    
    return warnings


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show_sourcing_view():
    st.title("👤 Sourcing Database")
    st.markdown("Lihat dan filter data kandidat sourcing.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    #  LOAD FROM CACHE 
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        master_options = get_master_options_sourcing_view(db)
        sourcing_options = get_sourcing_options_view()
        pipeline_stages = get_pipeline_stages_view()
    
    pic_options = master_options['pic_options']
    sumber_options = sourcing_options['sumber_options']
    model_options = sourcing_options['model_options']
    pipeline_status_options = sourcing_options['pipeline_status_options']
    
    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔍 Filter Sourcing")
        
        # Search
        search = st.text_input("🔎 Cari (Nama / Posisi / Kode Unik)", placeholder="Ketik keyword...")
        
        # PIC filter
        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + pic_options)
        
        # Sumber filter
        sumber_filter = st.selectbox("Sumber Sourcing", ["Semua"] + sumber_options)
        
        # Model filter
        model_filter = st.selectbox("Model Rekrutmen", ["Semua"] + model_options)
        
        # Status pipeline filter
        stage_labels = ["Semua"] + [s["label"] for s in pipeline_stages]
        stage_filter = st.selectbox("Tahap Pipeline", stage_labels)
        
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari Sourcing", datetime.now().replace(year=2020))
        with col2:
            date_to = st.date_input("Sampai Sourcing", datetime.now())
        
        # Show only my data
        show_mine = st.checkbox("Hanya data saya", value=False)
        
        # Tampilkan hanya yang ada warning
        show_warning_only = st.checkbox("⚠️ Tampilkan hanya data dengan warning", value=False)
        
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
    
    if sumber_filter != "Semua":
        query = query.filter(DBSourcing.sumber_sourcing == sumber_filter)
    
    if model_filter != "Semua":
        query = query.filter(DBSourcing.model_rekrutmen == model_filter)
    
    if show_mine and not is_admin(db):
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)
    
    if date_from:
        query = query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        query = query.filter(DBSourcing.sourcing_date <= date_to)
    
    # Stage filter
    if stage_filter != "Semua":
        for stage in pipeline_stages:
            if stage["label"] == stage_filter:
                field = getattr(DBSourcing, stage["field"])
                query = query.filter(field.isnot(None))
                break
    
    # Ambil semua data untuk dianalisis
    all_data = query.all()
    total = len(all_data)
    
    # Cek warning untuk setiap data
    data_with_warnings = []
    for record in all_data:
        warnings = check_sourcing_warnings(record)
        if warnings:
            data_with_warnings.append({
                'record': record,
                'warnings': warnings
            })
    
    # Filter jika hanya mau lihat warning
    if show_warning_only:
        display_data = data_with_warnings
    else:
        display_data = [{'record': r, 'warnings': check_sourcing_warnings(r)} for r in all_data]
    
    st.markdown(f"**Total Kandidat: {total}**")
    
    # Tampilkan summary warning
    if data_with_warnings:
        st.warning(f"⚠️ **{len(data_with_warnings)}** dari {total} data memiliki warning. Perbaiki data untuk akurasi lebih baik.")
        with st.expander(f"📋 Detail Warning ({len(data_with_warnings)} data)", expanded=False):
            for item in data_with_warnings[:10]:  # Tampilkan 10 pertama
                rec = item['record']
                st.markdown(f"**{rec.nama}** (Kode: {rec.kode_unik})")
                for warn in item['warnings']:
                    st.markdown(f"- ⚠️ {warn}")
                st.markdown("---")
            if len(data_with_warnings) > 10:
                st.info(f"... dan {len(data_with_warnings) - 10} data lainnya")
    else:
        st.success("✅ Semua data valid!")
    
    if total > 0:
        # Pagination
        page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
        page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
        offset = (page - 1) * page_size
        
        # Paginate display_data
        paginated_data = display_data[offset:offset + page_size]
        records = [item['record'] for item in paginated_data]
        
        # Convert to dataframe
        if records:
            df = pd.DataFrame([{
                'id': r.id,
                'no': r.no,
                'nama': r.nama,
                'posisi': r.posisi,
                'kode_unik': r.kode_unik,
                'sourcing_date': r.sourcing_date,
                'model_rekrutmen': r.model_rekrutmen,
                'sumber_sourcing': r.sumber_sourcing,
                'rekruter': r.rekruter,
                'email': r.email,
                'nomor_hp': r.nomor_hp,
                'domisili': r.domisili,
                'nama_universitas_top10': r.nama_universitas_top10,
                'nama_universitas_lainnya': r.nama_universitas_lainnya,
                'jenjang_pendidikan': r.jenjang_pendidikan,
                'jurusan': r.jurusan,
                'tahun_lulus': r.tahun_lulus,
                'ipk': r.ipk,
                'university_tier': r.university_tier,
                'ipk_tier': r.ipk_tier,
                'last_position': r.last_position,
                'last_company': r.last_company,
                'last_tenure': r.last_tenure,
                'total_tenure': r.total_tenure,
                'pernah_di_fmcg': r.pernah_di_fmcg,
                'notes': r.notes,
                'is_blacklisted': r.is_blacklisted,
                # Tambahkan kolom warning
                'warning_count': len([item for item in display_data if item['record'].id == r.id][0]['warnings']) if any(item['record'].id == r.id for item in display_data) else 0
            } for r in records])
            
            # Show all columns except audit columns
            exclude_cols = ['created_at', 'last_updated_at', 'last_compile_action', 
                           'source_file', 'source_file_hash', 'source_user_id', 'source_cycle_id',
                           'blacklisted_by', 'blacklisted_at', 'blacklist_reason']
            display_cols = [c for c in df.columns if c not in exclude_cols]
            
            # Column config
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
                "notes": "Catatan",
                "is_blacklisted": "Blacklist",
                "warning_count": "⚠️ Warning"
            }
            
            # Create display dataframe
            display_df = df[display_cols].copy()
            
            # Rename columns safely
            new_columns = []
            used_names = set()
            for col in display_df.columns:
                new_name = column_config.get(col, col)
                if new_name in used_names:
                    new_columns.append(col)
                else:
                    new_columns.append(new_name)
                    used_names.add(new_name)
            display_df.columns = new_columns
            
            # Highlight rows with warnings
            def highlight_warnings(row):
                if row.get('⚠️ Warning', 0) > 0:
                    return ['background-color: #fff3cd'] * len(row)
                return [''] * len(row)
            
            # Apply styling
            styled_df = display_df.style.apply(highlight_warnings, axis=1)
            
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=500
            )
            
            # ============================================================
            #  SEARCH/EDIT BY KODE UNIK / NAMA / POSISI 
            # ============================================================
            st.markdown("---")
            st.subheader("✏️ Detail & Edit Kandidat")
            st.caption("🔍 Cari berdasarkan Kode Unik, Nama, atau Posisi")
            
            # Buat list pilihan dengan format "Kode Unik | Nama | Posisi"
            df_all = pd.DataFrame([{
                'id': r.id,
                'kode_unik': r.kode_unik,
                'nama': r.nama,
                'posisi': r.posisi
            } for r in all_data])
            
            if not df_all.empty:
                search_options = {}
                for _, row in df_all.iterrows():
                    kode = row.get('kode_unik', '')
                    nama = row.get('nama', '')
                    posisi = row.get('posisi', '')
                    display = f"{kode} | {nama[:30]}..." if len(nama) > 30 else f"{kode} | {nama}"
                    if posisi:
                        display += f" | {posisi[:20]}..." if len(posisi) > 20 else f" | {posisi}"
                    search_options[display] = row.get('id')
                
                selected_display = st.selectbox(
                    "Pilih Kandidat (Kode Unik | Nama | Posisi)",
                    list(search_options.keys())
                )
                
                if selected_display:
                    selected_id = search_options[selected_display]
                else:
                    selected_id = None
            else:
                selected_id = None
                st.info("Tidak ada data untuk diedit.")
                return
            
            if not selected_id:
                st.info("Pilih data dari daftar di atas untuk diedit.")
                return
            
            detail = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
            if not detail:
                st.error("Data tidak ditemukan")
                return
            
            # TAMPILKAN WARNING UNTUK DATA INI
            detail_warnings = check_sourcing_warnings(detail)
            if detail_warnings:
                st.warning(f"⚠️ Data ini memiliki {len(detail_warnings)} warning:")
                for warn in detail_warnings:
                    st.markdown(f"- {warn}")
            
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
                pipeline_data = []
                for stage in pipeline_stages:
                    field = getattr(detail, stage["field"])
                    
                    date_field_name = f"tanggal_{stage['field']}"
                    detail_field_name = f"detail_keterangan_{stage['field']}"
                    
                    date_value = getattr(detail, date_field_name) if hasattr(detail, date_field_name) else None
                    detail_value = getattr(detail, detail_field_name) if hasattr(detail, detail_field_name) else None
                    
                    # Warn if status not V or X
                    status_display = field or "-"
                    if field and field not in ["V", "X"]:
                        status_display = f"⚠️ {field}"
                    
                    pipeline_data.append({
                        "Tahap": stage["label"],
                        "Status": status_display,
                        "Tanggal": date_value.strftime('%d/%m/%Y') if date_value else "-",
                        "Keterangan": detail_value or "-"
                    })
                
                pipeline_df = pd.DataFrame(pipeline_data)
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
                        sumber_sourcing = st.selectbox("Sumber Sourcing", [""] + sourcing_options['sumber_options'], 
                                                      index=([""] + sourcing_options['sumber_options']).index(detail.sumber_sourcing) if detail.sumber_sourcing in sourcing_options['sumber_options'] else 0)
                        # PERBAIKAN: Model options sesuai data
                        model_rekrutmen = st.selectbox("Model Rekrutmen", [""] + sourcing_options['model_options'],
                                                      index=([""] + sourcing_options['model_options']).index(detail.model_rekrutmen) if detail.model_rekrutmen in sourcing_options['model_options'] else 0)
                        no = st.number_input("No", value=detail.no or 0, step=1)
                        pernah_di_fmcg = st.selectbox("Pernah di FMCG", [""] + sourcing_options['fmcg_options'],
                                                     index=([""] + sourcing_options['fmcg_options']).index(detail.pernah_di_fmcg) if detail.pernah_di_fmcg in sourcing_options['fmcg_options'] else 0)
                    
                    st.markdown("---")
                    st.markdown("### 🎓 Pendidikan")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        jenjang_pendidikan = st.selectbox("Jenjang Pendidikan", [""] + sourcing_options['jenjang_options'],
                                                         index=([""] + sourcing_options['jenjang_options']).index(detail.jenjang_pendidikan) if detail.jenjang_pendidikan in sourcing_options['jenjang_options'] else 0)
                        nama_universitas_top10 = st.text_input("Nama Universitas Top 10", value=detail.nama_universitas_top10 or "")
                        nama_universitas_lainnya = st.text_input("Nama Universitas Lainnya", value=detail.nama_universitas_lainnya or "")
                    
                    with col2:
                        jurusan = st.text_input("Jurusan", value=detail.jurusan or "")
                        tahun_lulus = st.number_input("Tahun Lulus", value=detail.tahun_lulus or 0, step=1)
                        ipk = st.text_input("IPK", value=str(detail.ipk) if detail.ipk else "")
                    
                    with col3:
                        skor_bahasa_inggris = st.text_input("Skor Bahasa Inggris", value=detail.skor_bahasa_inggris or "")
                        university_tier = st.selectbox("University Tier", [""] + sourcing_options['univ_tier_options'],
                                                      index=([""] + sourcing_options['univ_tier_options']).index(detail.university_tier) if detail.university_tier in sourcing_options['univ_tier_options'] else 0)
                        ipk_tier = st.selectbox("IPK Tier", [""] + sourcing_options['ipk_tier_options'],
                                               index=([""] + sourcing_options['ipk_tier_options']).index(detail.ipk_tier) if detail.ipk_tier in sourcing_options['ipk_tier_options'] else 0)
                    
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
                    st.markdown("### 📊 Pipeline Stages (V = Lolos, X = Tidak Lolos)")
                    
                    for i, stage in enumerate(pipeline_stages):
                        if i % 3 == 0:
                            cols = st.columns(3)
                        
                        status_field = stage["field"]
                        label = stage["label"]
                        date_field = f"tanggal_{status_field}"
                        detail_field = f"detail_keterangan_{status_field}"
                        
                        status_value = getattr(detail, status_field)
                        date_value = getattr(detail, date_field) if hasattr(detail, date_field) else None
                        detail_value = getattr(detail, detail_field) if hasattr(detail, detail_field) else None
                        
                        with cols[i % 3]:
                            st.markdown(f"**{label}**")
                            
                            new_status = st.selectbox(
                                f"Status {label}",
                                [""] + pipeline_status_options,
                                index=([""] + pipeline_status_options).index(status_value) if status_value in pipeline_status_options else 0,
                                key=f"status_{status_field}"
                            )
                            
                            new_date = st.date_input(
                                f"Tgl {label}",
                                value=date_value if date_value else None,
                                key=f"date_{date_field}"
                            )
                            
                            if hasattr(detail, detail_field):
                                new_detail = st.text_area(
                                    f"Keterangan {label}",
                                    value=detail_value or "",
                                    key=f"detail_{detail_field}",
                                    height=50
                                )
                                setattr(detail, detail_field, new_detail if new_detail else None)
                            
                            setattr(detail, status_field, new_status if new_status else None)
                            setattr(detail, date_field, new_date)
                    
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
