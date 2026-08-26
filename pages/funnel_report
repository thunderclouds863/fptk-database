import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.database import get_db
from core.models import DBSourcing
from core.auth import get_current_user

def show_funnel_report():
    st.title("🔍 Funnel Report")
    
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
    
    # Hitung funnel
    funnel_data = {
        "Sourcing HR": total,
        "Shortlist": len(df[df['shortlist_cv'].notna()]) if 'shortlist_cv' in df else 0,
        "Psikotes": len(df[df['psikotes'].notna()]) if 'psikotes' in df else 0,
        "HR Interview": len(df[df['hr_interview'].notna()]) if 'hr_interview' in df else 0,
        "Offering": len(df[df['offering'].notna()]) if 'offering' in df else 0,
        "Day 1": len(df[df['day1'].notna()]) if 'day1' in df else 0,
    }
    
    # Metrics
    cols = st.columns(len(funnel_data))
    for i, (name, val) in enumerate(funnel_data.items()):
        cols[i].metric(name, val)
    
    # Funnel chart
    df_funnel = pd.DataFrame(list(funnel_data.items()), columns=["Stage", "Count"])
    fig = go.Figure(go.Funnel(y=df_funnel['Stage'], x=df_funnel['Count']))
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Data table
    st.dataframe(df[['nama', 'posisi', 'kode_unik', 'rekruter']].head(50), use_container_width=True)
