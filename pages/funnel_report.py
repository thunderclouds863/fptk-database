import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.database import get_db
from core.models import DBSourcing, FPTK
from core.auth import get_current_user
from datetime import datetime
import time

# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_data(ttl=3600)
def get_funnel_pipeline_stages():
    """Pipeline stages untuk funnel - cache 1 jam"""
    return [
        {"field": "sourcing_freelance", "label": "Sourcing FL", "funnel_label": "Sourcing FL"},
        {"field": "sourcing_hr", "label": "Lolos Sourcing HR", "funnel_label": "Lolos Sourcing HR"},
        {"field": "shortlist_cv", "label": "Shortlisted User", "funnel_label": "Shortlisted User"},
        {"field": "psikotes", "label": "Lulus Psikotes", "funnel_label": "Lulus Psikotes"},
        {"field": "hr_interview", "label": "Lulus HR Interview", "funnel_label": "Lulus HR Interview"},
        {"field": "technical_test_case_study", "label": "Lulus Technical Case", "funnel_label": "Lulus Technical Case"},
        {"field": "market_visit", "label": "Lulus Market Visit", "funnel_label": "Lulus Market Visit"},
        {"field": "user_interview", "label": "Lulus User Interview", "funnel_label": "Lulus User Interview"},
        {"field": "panel_interview", "label": "Lulus Panel Interview", "funnel_label": "Lulus Panel Interview"},
        {"field": "reference_check", "label": "Reference Check", "funnel_label": "Reference Check"},
        {"field": "mcu", "label": "Lolos MCU", "funnel_label": "Lolos MCU"},
        {"field": "offering", "label": "Lolos Offering", "funnel_label": "Lolos Offering"},
        {"field": "day1", "label": "Day One", "funnel_label": "Day One"}
    ]


@st.cache_data(ttl=3600)
def get_funnel_status_options():
    """Status options untuk funnel - cache 1 jam"""
    return ["V", "X"]


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show_funnel_report():
    st.title("🔍 Funnel Report")
    st.markdown("Laporan pipeline sourcing per Kode Unik (agregasi)")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # ============================================================
    # 🔥🔥🔥 LOAD FROM CACHE 🔥🔥🔥
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        pipeline_stages = get_funnel_pipeline_stages()
        status_options = get_funnel_status_options()
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter Funnel")
        
        # Date filter
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now().replace(year=2020))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())
        
        # PIC filter
        pic_options = ["Semua"] + [u[0] for u in db.query(DBSourcing.rekruter).distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_options)
        
        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()
    
    # ============================================================
    # QUERY DATA
    # ============================================================
    query = db.query(DBSourcing)
    
    if date_from:
        query = query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        query = query.filter(DBSourcing.sourcing_date <= date_to)
    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)
    
    df = pd.read_sql(query.statement, db.bind)
    total = len(df)
    
    if total == 0:
        st.info("Belum ada data sourcing dengan filter yang dipilih.")
        return
    
    # ============================================================
    # 🔥🔥🔥 JOIN DENGAN FPTK 🔥🔥🔥
    # ============================================================
    fptk_df = pd.DataFrame()
    if 'kode_unik' in df.columns:
        kode_unik_list = df['kode_unik'].dropna().unique().tolist()
        if kode_unik_list:
            fptk_query = db.query(FPTK).filter(FPTK.kode_unik.in_(kode_unik_list))
            fptk_df = pd.read_sql(fptk_query.statement, db.bind)
    
    # ============================================================
    # 🔥🔥🔥 AGREGASI PER KODE UNIK 🔥🔥🔥
    # ============================================================
    
    # Group by kode_unik
    grouped = df.groupby('kode_unik')
    
    # Siapkan data agregasi
    aggregated_data = []
    
    for kode_unik, group in grouped:
        row_data = {
            'kode_unik': kode_unik,
            'total_kandidat': len(group)
        }
        
        # Ambil data dari FPTK (1 baris per kode unik)
        if not fptk_df.empty:
            fptk_row = fptk_df[fptk_df['kode_unik'] == kode_unik]
            if not fptk_row.empty:
                row_data['fptk_date_real'] = fptk_row.iloc[0].get('fptk_date_real', None)
                row_data['posisi'] = fptk_row.iloc[0].get('posisi', '-')
                row_data['business_unit'] = fptk_row.iloc[0].get('business_unit', '-')
                row_data['direktorat'] = fptk_row.iloc[0].get('direktorat', '-')
                row_data['divisi'] = fptk_row.iloc[0].get('divisi', '-')
                row_data['department'] = fptk_row.iloc[0].get('department', '-')
                row_data['level_fptk'] = fptk_row.iloc[0].get('level_fptk', '-')
                row_data['level_number'] = fptk_row.iloc[0].get('level_number', '-')
                row_data['category_fptk'] = fptk_row.iloc[0].get('category_fptk', '-')
                row_data['filter_kategorisasi_fptk'] = fptk_row.iloc[0].get('filter_kategorisasi_fptk', '-')
                row_data['pic_recruiter'] = fptk_row.iloc[0].get('pic_recruiter', '-')
            else:
                # Jika tidak ada di FPTK, ambil dari DBSourcing
                row_data['posisi'] = group.iloc[0].get('posisi', '-')
                row_data['pic_recruiter'] = group.iloc[0].get('rekruter', '-')
                # Kolom lain kosong
                for col in ['fptk_date_real', 'business_unit', 'direktorat', 'divisi', 'department', 
                           'level_fptk', 'level_number', 'category_fptk', 'filter_kategorisasi_fptk']:
                    row_data[col] = '-'
        else:
            # Jika tidak ada FPTK, ambil dari DBSourcing
            row_data['posisi'] = group.iloc[0].get('posisi', '-')
            row_data['pic_recruiter'] = group.iloc[0].get('rekruter', '-')
            for col in ['fptk_date_real', 'business_unit', 'direktorat', 'divisi', 'department', 
                       'level_fptk', 'level_number', 'category_fptk', 'filter_kategorisasi_fptk']:
                row_data[col] = '-'
        
        # 🔥🔥🔥 HITUNG JUMLAH PER TAHAP (V) 🔥🔥🔥
        for stage in pipeline_stages:
            field = stage["field"]
            if field in group.columns:
                # Hitung berapa yang statusnya "V" di stage ini
                count_v = len(group[group[field] == "V"])
            else:
                count_v = 0
            row_data[stage["label"]] = count_v
        
        aggregated_data.append(row_data)
    
    # Buat dataframe agregasi
    agg_df = pd.DataFrame(aggregated_data)
    
    # ============================================================
    # 📊 METRIC CARDS - TOTAL PER TAHAP
    # ============================================================
    st.markdown("### 📊 Total Kandidat per Tahap")
    
    # Hitung total per stage dari data agregasi
    funnel_totals = {}
    for stage in pipeline_stages:
        label = stage["label"]
        if label in agg_df.columns:
            funnel_totals[label] = agg_df[label].sum()
        else:
            funnel_totals[label] = 0
    
    # Tambahkan total kandidat
    funnel_totals["Total Kandidat"] = len(agg_df)
    
    # Tampilkan metrics
    stage_labels = list(funnel_totals.keys())
    stage_counts = list(funnel_totals.values())
    
    # Tampilkan 4 kolom per baris
    cols_per_row = 4
    for i in range(0, len(stage_labels), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < len(stage_labels):
                cols[j].metric(stage_labels[idx], stage_counts[idx])
    
    st.markdown("---")
    
    # ============================================================
    # 🔥🔥🔥 FUNNEL CHART 🔥🔥🔥
    # ============================================================
    st.markdown("### 📈 Funnel Chart")
    
    # Buat data untuk funnel chart (hanya yang punya nilai > 0)
    funnel_data_chart = {k: v for k, v in funnel_totals.items() if v > 0 and k != "Total Kandidat"}
    
    if funnel_data_chart:
        df_funnel = pd.DataFrame(list(funnel_data_chart.items()), columns=["Stage", "Count"])
        
        # Warna untuk funnel
        colors = ['#2ecc71' if i % 2 == 0 else '#3498db' for i in range(len(df_funnel))]
        
        fig = go.Figure(go.Funnel(
            y=df_funnel['Stage'],
            x=df_funnel['Count'],
            textposition="inside",
            textinfo="value+percent initial",
            marker=dict(color=colors),
            connector=dict(line=dict(color="grey", width=2))
        ))
        fig.update_layout(
            height=500,
            title="Pipeline Sourcing Funnel (per Kode Unik)",
            font=dict(size=14)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Tidak ada data untuk funnel chart.")
    
    st.markdown("---")
    
    # ============================================================
    # 🔥🔥🔥 DETAIL TABLE PER KODE UNIK 🔥🔥🔥
    # ============================================================
    st.markdown("### 📋 Detail Data per Kode Unik")
    st.caption(f"Total: {len(agg_df)} Kode Unik unik")
    
    # Urutkan kolom sesuai yang diminta
    desired_order = [
        'fptk_date_real',
        'posisi',
        'business_unit',
        'direktorat',
        'divisi',
        'department',
        'level_fptk',
        'level_number',
        'category_fptk',
        'filter_kategorisasi_fptk',
        'pic_recruiter',
        'Sourcing FL',
        'Lolos Sourcing HR',
        'Shortlisted User',
        'Lulus Psikotes',
        'Lulus HR Interview',
        'Lulus Technical Case',
        'Lulus Market Visit',
        'Lulus User Interview',
        'Lulus Panel Interview',
        'Reference Check',
        'Lolos MCU',
        'Lolos Offering',
        'Day One'
    ]
    
    # Mapping nama kolom untuk display
    col_display_map = {
        'fptk_date_real': 'FPTK Date Real',
        'posisi': 'Posisi',
        'business_unit': 'Business Unit',
        'direktorat': 'Direktorat',
        'divisi': 'Divisi',
        'department': 'Department',
        'level_fptk': 'Level FPTK',
        'level_number': 'Level Number',
        'category_fptk': 'Category FPTK',
        'filter_kategorisasi_fptk': 'Filter Kategorisasi FPTK',
        'pic_recruiter': 'PIC Recruiter'
    }
    
    # Tambahkan kolom pipeline
    for stage in pipeline_stages:
        col_display_map[stage["label"]] = stage["label"]
    
    # Buat display dataframe
    display_df = agg_df.copy()
    
    # Format tanggal
    if 'fptk_date_real' in display_df.columns:
        display_df['fptk_date_real'] = display_df['fptk_date_real'].apply(
            lambda x: x.strftime('%d/%m/%y') if pd.notna(x) and isinstance(x, pd.Timestamp) else (x if x != '-' else '-')
        )
    
    # Filter kolom yang ada
    available_cols = [col for col in desired_order if col in display_df.columns]
    
    # Tambahkan kolom yang mungkin hilang
    for col in desired_order:
        if col not in display_df.columns:
            display_df[col] = 0 if col in [s["label"] for s in pipeline_stages] else '-'
    
    # Urutkan
    display_df = display_df[desired_order]
    
    # Rename kolom untuk display
    display_df = display_df.rename(columns=col_display_map)
    
    # Tampilkan dataframe dengan styling
    st.dataframe(
        display_df,
        use_container_width=True,
        height=500
    )
    
    # ============================================================
    # 🔥🔥🔥 EXPORT BUTTON 🔥🔥🔥
    # ============================================================
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 3])
    
    with col1:
        if st.button("📥 Export CSV", use_container_width=True, type="primary"):
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"funnel_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ============================================================
    # 📊 SUMMARY STATISTICS
    # ============================================================
    st.markdown("---")
    st.markdown("### 📊 Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_kode_unik = len(agg_df)
        st.metric("Total Kode Unik", total_kode_unik)
    
    with col2:
        total_kandidat = len(df)
        st.metric("Total Kandidat", total_kandidat)
    
    with col3:
        offering_count = agg_df['Lolos Offering'].sum() if 'Lolos Offering' in agg_df.columns else 0
        st.metric("Total Lolos Offering", offering_count)
    
    with col4:
        day1_count = agg_df['Day One'].sum() if 'Day One' in agg_df.columns else 0
        st.metric("Total Day One", day1_count)
    
    # ============================================================
    # 📈 CONVERSION RATE
    # ============================================================
    st.markdown("---")
    st.markdown("### 📈 Conversion Rate (per Kode Unik)")
    
    conversion_data = []
    prev_count = len(agg_df)  # Total kode unik
    
    for stage in pipeline_stages:
        label = stage["label"]
        count = agg_df[label].sum() if label in agg_df.columns else 0
        
        if prev_count > 0:
            rate = (count / prev_count) * 100
        else:
            rate = 0
        
        conversion_data.append({
            "Tahap": label,
            "Jumlah": count,
            "Conversion Rate": f"{rate:.1f}%"
        })
        
        prev_count = count if count > 0 else prev_count
    
    st.dataframe(pd.DataFrame(conversion_data), use_container_width=True, hide_index=True)
