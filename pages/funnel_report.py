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
        {"field": "sourcing_freelance", "label": "Sourcing FL"},
        {"field": "sourcing_hr", "label": "Lolos Sourcing HR"},
        {"field": "shortlist_cv", "label": "Shortlisted User"},
        {"field": "psikotes", "label": "Lulus Psikotes"},
        {"field": "hr_interview", "label": "Lulus HR Interview"},
        {"field": "technical_test_case_study", "label": "Lulus Technical Case"},
        {"field": "market_visit", "label": "Lulus Market Visit"},
        {"field": "user_interview", "label": "Lulus User Interview"},
        {"field": "panel_interview", "label": "Lulus Panel Interview"},
        {"field": "reference_check", "label": "Reference Check"},
        {"field": "mcu", "label": "Lolos MCU"},
        {"field": "offering", "label": "Lolos Offering"},
        {"field": "day1", "label": "Day One"}
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
    # QUERY DATA SOURCING
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
    # 🔥🔥🔥 HITUNG TOTAL PER TAHAP (HANYA YANG V) 🔥🔥🔥
    # ============================================================
    funnel_data = {}
    for stage in pipeline_stages:
        field = stage["field"]
        if field in df.columns:
            # Hitung yang statusnya "V" (Lolos)
            count = len(df[df[field] == "V"])
        else:
            count = 0
        funnel_data[stage["label"]] = count
    
    # ============================================================
    # 📊 METRIC CARDS - TOTAL PER TAHAP
    # ============================================================
    st.markdown("### 📊 Total Kandidat Lolos per Tahap")
    st.caption("Menampilkan jumlah kandidat yang LOLOS (V) di setiap tahap pipeline")
    
    # Tampilkan metrics dalam beberapa baris (4 kolom per baris)
    stage_labels = list(funnel_data.keys())
    stage_counts = list(funnel_data.values())
    
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
            title="Pipeline Sourcing Funnel (Kandidat yang Lolos / V)",
            font=dict(size=14)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Tidak ada data untuk funnel chart.")
    
    st.markdown("---")
    
    # ============================================================
    # 🔥🔥🔥 DETAIL TABLE - PER KODE UNIK DENGAN CHECKLIST 🔥🔥🔥
    # ============================================================
    st.markdown("### 📋 Detail Data Sourcing per Kode Unik")
    st.caption(f"Total: {total} kandidat | V = Lolos, X = Tidak Lolos, - = Belum diproses")
    
    # ============================================================
    # BUILD TABLE PER KODE UNIK
    # ============================================================
    
    display_data = []
    
    for _, row in df.iterrows():
        kode_unik = row.get('kode_unik', '-')
        if pd.isna(kode_unik) or kode_unik == '':
            kode_unik = '-'
        
        row_data = {
            'Kode Unik': kode_unik,
            'Nama Kandidat': row.get('nama', '-'),
            'Posisi': row.get('posisi', '-'),
            'PIC Recruiter': row.get('rekruter', '-'),
        }
        
        # Ambil data dari FPTK (join berdasarkan kode_unik)
        fptk_row = None
        if kode_unik != '-' and not fptk_df.empty:
            fptk_rows = fptk_df[fptk_df['kode_unik'] == kode_unik]
            if not fptk_rows.empty:
                fptk_row = fptk_rows.iloc[0]
        
        # Data dari FPTK
        if fptk_row is not None:
            row_data['FPTK Date Real'] = fptk_row.get('fptk_date_real', '-')
            if row_data['FPTK Date Real'] != '-' and not pd.isna(row_data['FPTK Date Real']):
                try:
                    row_data['FPTK Date Real'] = pd.to_datetime(row_data['FPTK Date Real']).strftime('%d/%m/%Y')
                except:
                    pass
            
            row_data['Business Unit'] = fptk_row.get('business_unit', '-') or '-'
            row_data['Direktorat'] = fptk_row.get('direktorat', '-') or '-'
            row_data['Divisi'] = fptk_row.get('divisi', '-') or '-'
            row_data['Department'] = fptk_row.get('department', '-') or '-'
            row_data['Level FPTK'] = fptk_row.get('level_fptk', '-') or '-'
            row_data['Level Number'] = fptk_row.get('level_number', '-') or '-'
            row_data['Category FPTK'] = fptk_row.get('category_fptk', '-') or '-'
            row_data['Filter Kategorisasi FPTK'] = fptk_row.get('filter_kategorisasi_fptk', '-') or '-'
        else:
            row_data['FPTK Date Real'] = '-'
            row_data['Business Unit'] = '-'
            row_data['Direktorat'] = '-'
            row_data['Divisi'] = '-'
            row_data['Department'] = '-'
            row_data['Level FPTK'] = '-'
            row_data['Level Number'] = '-'
            row_data['Category FPTK'] = '-'
            row_data['Filter Kategorisasi FPTK'] = '-'
        
        # 🔥🔥🔥 PIPELINE STAGES - CHECKLIST PER KODE UNIK 🔥🔥🔥
        for stage in pipeline_stages:
            field = stage["field"]
            val = row.get(field, '-')
            if pd.isna(val):
                val = '-'
            row_data[stage["label"]] = val
        
        display_data.append(row_data)
    
    # Buat dataframe
    display_df = pd.DataFrame(display_data)
    
    # Urutkan kolom sesuai yang diminta
    desired_order = [
        'Kode Unik',
        'Nama Kandidat',
        'Posisi',
        'PIC Recruiter',
        'FPTK Date Real',
        'Business Unit',
        'Direktorat',
        'Divisi',
        'Department',
        'Level FPTK',
        'Level Number',
        'Category FPTK',
        'Filter Kategorisasi FPTK',
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
    
    # ============================================================
    # STYLING - WARNA UNTUK V, X, -
    # ============================================================
    def color_status(val):
        if val == 'V':
            return 'background-color: #d4edda; color: #155724; font-weight: bold;'  # Hijau
        elif val == 'X':
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'  # Merah
        else:
            return 'background-color: #e9ecef; color: #6c757d;'  # Abu-abu
    
    # Apply styling hanya ke kolom pipeline
    pipeline_columns = [
        'Sourcing FL', 'Lolos Sourcing HR', 'Shortlisted User', 'Lulus Psikotes',
        'Lulus HR Interview', 'Lulus Technical Case', 'Lulus Market Visit',
        'Lulus User Interview', 'Lulus Panel Interview', 'Reference Check',
        'Lolos MCU', 'Lolos Offering', 'Day One'
    ]
    
    # Buat styler
    styled_df = display_df.style.applymap(
        color_status,
        subset=[col for col in pipeline_columns if col in display_df.columns]
    )
    
    # Tampilkan dataframe dengan styling
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=500
    )
    
    # ============================================================
    # 📊 SUMMARY PER TAHAP DARI DETAIL DATA
    # ============================================================
    st.markdown("---")
    st.markdown("### 📊 Summary Pipeline per Tahap")
    
    summary_data = []
    for stage in pipeline_stages:
        label = stage["label"]
        field = stage["field"]
        
        # Total kandidat yang masuk stage ini (V + X)
        total_in_stage = len(df[df[field].notna()]) if field in df.columns else 0
        
        # Total yang lolos (V)
        total_v = len(df[df[field] == "V"]) if field in df.columns else 0
        
        # Total yang tidak lolos (X)
        total_x = len(df[df[field] == "X"]) if field in df.columns else 0
        
        # Total yang belum diproses (-)
        total_empty = len(df[df[field].isna() | (df[field] == "")]) if field in df.columns else 0
        
        # Conversion rate dari total kandidat
        if total > 0:
            conversion_rate = (total_v / total) * 100
        else:
            conversion_rate = 0
        
        # Conversion rate dari yang masuk stage
        if total_in_stage > 0:
            pass_rate = (total_v / total_in_stage) * 100
        else:
            pass_rate = 0
        
        summary_data.append({
            "Tahap": label,
            "Total Masuk": total_in_stage,
            "✅ Lolos (V)": total_v,
            "❌ Tidak Lolos (X)": total_x,
            "⏳ Belum Diproses": total_empty,
            "Conversion Rate (dari Total)": f"{conversion_rate:.1f}%",
            "Pass Rate (dari yang Masuk)": f"{pass_rate:.1f}%"
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
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
