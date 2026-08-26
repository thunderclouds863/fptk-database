import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, User
from core.auth import get_current_user
from datetime import datetime, timedelta

def show_monitoring_report():
    st.title("📈 Monitoring Sourcing")
    st.markdown("Monitoring sourcing per minggu (Senin-Minggu)")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        
        # Pilih minggu
        week_options = []
        today = datetime.now()
        for i in range(12):
            week_start = today - timedelta(days=today.weekday() + i*7)
            week_end = week_start + timedelta(days=6)
            week_options.append((week_start, week_end))
        
        selected_week = st.selectbox(
            "Minggu",
            range(len(week_options)),
            format_func=lambda x: f"{week_options[x][0].strftime('%d/%m/%Y')} - {week_options[x][1].strftime('%d/%m/%Y')}"
        )
        
        pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_options)
        
        st.markdown("---")
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # ============================================================
    # QUERY
    # ============================================================
    week_start, week_end = week_options[selected_week]
    
    query = db.query(DBSourcing).filter(
        DBSourcing.sourcing_date >= week_start,
        DBSourcing.sourcing_date <= week_end
    )
    
    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)
    
    df = pd.read_sql(query.statement, db.bind)
    total = len(df)
    
    # ============================================================
    # HEADER
    # ============================================================
    st.subheader(f"📅 Minggu: {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total CV", total)
    col2.metric("Unique Kode Unik", df['kode_unik'].nunique() if 'kode_unik' in df else 0)
    col3.metric("Unique Posisi", df['posisi'].nunique() if 'posisi' in df else 0)
    
    st.markdown("---")
    
    # ============================================================
    # DAILY DISTRIBUTION
    # ============================================================
    if total > 0 and 'sourcing_date' in df:
        df['date'] = pd.to_datetime(df['sourcing_date'])
        daily = df.groupby(df['date'].dt.date).size().reset_index()
        daily.columns = ['Tanggal', 'Jumlah']
        
        # Tambahkan hari yang kosong
        all_dates = pd.date_range(week_start, week_end)
        daily_full = pd.DataFrame({'Tanggal': all_dates})
        daily_full['Tanggal'] = daily_full['Tanggal'].dt.date
        daily_full = daily_full.merge(daily, on='Tanggal', how='left').fillna(0)
        daily_full['Jumlah'] = daily_full['Jumlah'].astype(int)
        
        fig = px.bar(daily_full, x='Tanggal', y='Jumlah', title='CV per Hari', text='Jumlah')
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    # ============================================================
    # DETAIL DATA
    # ============================================================
    if total > 0:
        st.subheader("📋 Detail Data")
        
        display_cols = ['id', 'nama', 'posisi', 'kode_unik', 'rekruter', 'sourcing_date']
        display_df = df[[c for c in display_cols if c in df.columns]].copy()
        
        rename_map = {
            'id': 'ID', 'nama': 'Nama', 'posisi': 'Posisi', 'kode_unik': 'Kode Unik',
            'rekruter': 'PIC', 'sourcing_date': 'Tgl Sourcing'
        }
        display_df = display_df.rename(columns=rename_map)
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Export
        if st.button("📥 Export CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, f"monitoring_{week_start.strftime('%Y%m%d')}.csv", "text/csv")
    else:
        st.info("Tidak ada data untuk minggu ini.")
