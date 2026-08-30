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
    st.markdown("Laporan pipeline sourcing dari awal hingga Day 1")
    
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
    # 📊 METRIC CARDS - TOTAL PER TAHAP
    # ============================================================
    st.markdown("### 📊 Total Kandidat per Tahap")
    
    # Hitung total per stage (hanya yang statusnya "V")
    funnel_data = {}
    for stage in pipeline_stages:
        field = stage["field"]
        if field in df.columns:
            # Hitung yang statusnya "V" (Lolos)
            count = len(df[df[field] == "V"])
        else:
            count = 0
        funnel_data[stage["funnel_label"]] = count
    
    # Tampilkan metrics dalam beberapa baris
    stage_labels = list(funnel_data.keys())
    stage_counts = list(funnel_data.values())
    
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
    funnel_data_chart = {k: v for k, v in funnel_data.items() if v > 0}
    
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
            title="Pipeline Sourcing Funnel",
            font=dict(size=14)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Tidak ada data untuk funnel chart.")
    
    st.markdown("---")
    
    # ============================================================
    # 🔥🔥🔥 DETAIL TABLE (SEMUA KOLOM YANG DIMINTA) 🔥🔥🔥
    # ============================================================
    st.markdown("### 📋 Detail Data Sourcing")
    st.caption(f"Total: {total} kandidat")
    
    # ============================================================
    # JOIN DENGAN FPTK UNTUK MENDAPATKAN DATA FPTK
    # ============================================================
    # Ambil data FPTK berdasarkan kode_unik
    fptk_df = pd.DataFrame()
    if 'kode_unik' in df.columns:
        kode_unik_list = df['kode_unik'].dropna().unique().tolist()
        if kode_unik_list:
            fptk_query = db.query(FPTK).filter(FPTK.kode_unik.in_(kode_unik_list))
            fptk_df = pd.read_sql(fptk_query.statement, db.bind)
    
    # ============================================================
    # BUILD TABLE DENGAN SEMUA KOLOM
    # ============================================================
    
    # Kolom dari DBSourcing
    sourcing_cols = {
        'nama': 'Nama Kandidat',
        'posisi': 'Posisi',
        'kode_unik': 'Kode Unik',
        'rekruter': 'PIC Recruiter',
        'sourcing_date': 'Sourcing Date'
    }
    
    # Kolom dari FPTK
    fptk_cols = {
        'fptk_date_real': 'FPTK Date Real',
        'business_unit': 'Business Unit',
        'direktorat': 'Direktorat',
        'divisi': 'Divisi',
        'department': 'Department',
        'level_fptk': 'Level FPTK',
        'level_number': 'Level Number',
        'category_fptk': 'Category FPTK',
        'filter_kategorisasi_fptk': 'Filter Kategorisasi FPTK'
    }
    
    # Kolom pipeline
    pipeline_cols = {}
    for stage in pipeline_stages:
        pipeline_cols[stage["field"]] = stage["label"]
    
    # Gabungkan semua kolom
    all_columns = {**sourcing_cols, **pipeline_cols}
    
    # Buat dataframe dengan semua kolom
    display_data = []
    
    for _, row in df.iterrows():
        row_data = {}
        
        # Ambil data dari DBSourcing
        for col, label in sourcing_cols.items():
            row_data[label] = row.get(col, '-')
            if pd.isna(row_data[label]):
                row_data[label] = '-'
        
        # Ambil data pipeline
        for col, label in pipeline_cols.items():
            val = row.get(col, '-')
            if pd.isna(val):
                val = '-'
            row_data[label] = val
        
        # Ambil data dari FPTK (join berdasarkan kode_unik)
        kode_unik = row.get('kode_unik')
        if kode_unik and not fptk_df.empty:
            fptk_row = fptk_df[fptk_df['kode_unik'] == kode_unik]
            if not fptk_row.empty:
                for col, label in fptk_cols.items():
                    val = fptk_row.iloc[0].get(col, '-')
                    if pd.isna(val):
                        val = '-'
                    # Format tanggal
                    if col == 'fptk_date_real' and val != '-':
                        try:
                            val = pd.to_datetime(val).strftime('%d/%m/%Y')
                        except:
                            pass
                    row_data[label] = val
        
        display_data.append(row_data)
    
    # Buat dataframe final
    display_df = pd.DataFrame(display_data)
    
    # Urutkan kolom sesuai yang diminta
    desired_order = [
        'FPTK Date Real',
        'Posisi',
        'Business Unit',
        'Direktorat',
        'Divisi',
        'Department',
        'Level FPTK',
        'Level Number',
        'Category FPTK',
        'Filter Kategorisasi FPTK',
        'PIC Recruiter',
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
    
    # Filter kolom yang ada
    available_cols = [col for col in desired_order if col in display_df.columns]
    
    # Tambahkan kolom yang mungkin hilang
    for col in desired_order:
        if col not in display_df.columns:
            display_df[col] = '-'
    
    # Urutkan
    display_df = display_df[desired_order]
    
    # Tampilkan dataframe dengan styling
    st.dataframe(
        display_df,
        use_container_width=True,
        height=500,
        column_config={
            "FPTK Date Real": st.column_config.TextColumn("FPTK Date Real", width="small"),
            "Posisi": st.column_config.TextColumn("Posisi", width="medium"),
            "Business Unit": st.column_config.TextColumn("Business Unit", width="small"),
            "Direktorat": st.column_config.TextColumn("Direktorat", width="small"),
            "Divisi": st.column_config.TextColumn("Divisi", width="medium"),
            "Department": st.column_config.TextColumn("Department", width="medium"),
            "Level FPTK": st.column_config.TextColumn("Level", width="small"),
            "Level Number": st.column_config.TextColumn("Level Number", width="small"),
            "Category FPTK": st.column_config.TextColumn("Category", width="small"),
            "Filter Kategorisasi FPTK": st.column_config.TextColumn("Filter Kategorisasi", width="small"),
            "PIC Recruiter": st.column_config.TextColumn("PIC Recruiter", width="small"),
            "Sourcing FL": st.column_config.TextColumn("Sourcing FL", width="small"),
            "Lolos Sourcing HR": st.column_config.TextColumn("Sourcing HR", width="small"),
            "Shortlisted User": st.column_config.TextColumn("Shortlist", width="small"),
            "Lulus Psikotes": st.column_config.TextColumn("Psikotes", width="small"),
            "Lulus HR Interview": st.column_config.TextColumn("HR Interview", width="small"),
            "Lulus Technical Case": st.column_config.TextColumn("Technical Case", width="small"),
            "Lulus Market Visit": st.column_config.TextColumn("Market Visit", width="small"),
            "Lulus User Interview": st.column_config.TextColumn("User Interview", width="small"),
            "Lulus Panel Interview": st.column_config.TextColumn("Panel Interview", width="small"),
            "Reference Check": st.column_config.TextColumn("Reference Check", width="small"),
            "Lolos MCU": st.column_config.TextColumn("MCU", width="small"),
            "Lolos Offering": st.column_config.TextColumn("Offering", width="small"),
            "Day One": st.column_config.TextColumn("Day 1", width="small")
        }
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
    
    # Hitung conversion rate
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_candidates = len(df)
        st.metric("Total Kandidat", total_candidates)
    
    with col2:
        # Hitung yang lolos sampai Offering
        offering_count = len(df[df['offering'] == "V"]) if 'offering' in df.columns else 0
        st.metric("Lolos Offering", offering_count)
    
    with col3:
        # Hitung yang lolos sampai Day 1
        day1_count = len(df[df['day1'] == "V"]) if 'day1' in df.columns else 0
        st.metric("Day 1", day1_count)
    
    # Conversion rate
    st.markdown("---")
    st.markdown("### 📈 Conversion Rate")
    
    conversion_data = []
    prev_count = total_candidates
    
    for stage in pipeline_stages:
        field = stage["field"]
        label = stage["label"]
        count = len(df[df[field] == "V"]) if field in df.columns else 0
        
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
