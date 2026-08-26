import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import Evidence, FPTK
from core.auth import is_admin, get_current_user

def show_evidence_dashboard():
    st.title("📊 Dashboard Evidence")
    st.markdown("Monitoring evidence per PIC, per FPTK, per periode")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user or not is_admin(db):
        st.warning("Hanya untuk Admin.")
        return
    
    # Query
    query = db.query(Evidence)
    df = pd.read_sql(query.statement, db.bind)
    
    if len(df) == 0:
        st.info("Belum ada evidence.")
        return
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Evidence", len(df))
    col2.metric("Unique PIC", df['pic_recruiter'].nunique())
    col3.metric("Unique Kode Unik", df['kode_unik'].nunique())
    
    # Chart per PIC
    st.subheader("📊 Evidence per PIC")
    pic_counts = df['pic_recruiter'].value_counts().reset_index()
    pic_counts.columns = ['PIC', 'Jumlah']
    fig = px.bar(pic_counts, x='PIC', y='Jumlah', title='Evidence per PIC')
    st.plotly_chart(fig, use_container_width=True)
    
    # Data table
    st.dataframe(df, use_container_width=True, height=400)
