import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing
from core.auth import get_current_user
from datetime import datetime, timedelta

def show():
    st.title("📈 Monitoring Sourcing")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # Query data sourcing
    query = db.query(DBSourcing)
    df = pd.read_sql(query.statement, db.bind)
    total = len(df)
    
    if total == 0:
        st.info("Belum ada data sourcing.")
        return
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total CV", total)
    col2.metric("Unique Kode", df['kode_unik'].nunique() if 'kode_unik' in df else 0)
    col3.metric("Unique Posisi", df['posisi'].nunique() if 'posisi' in df else 0)
    
    # Daily chart
    if 'sourcing_date' in df:
        df['date'] = pd.to_datetime(df['sourcing_date'])
        daily = df.groupby(df['date'].dt.date).size().reset_index()
        daily.columns = ['Tanggal', 'Jumlah']
        fig = px.bar(daily, x='Tanggal', y='Jumlah', title='CV per Hari')
        st.plotly_chart(fig, use_container_width=True)
    
    # Data table
    st.dataframe(df[['nama', 'posisi', 'kode_unik', 'rekruter', 'sourcing_date']].head(50), use_container_width=True)
