import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.database import get_db
from core.models import FPTK, DBSourcing, User, UploadStatus, UploadCycle
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import time

# ============================================================
# CACHE FUNCTIONS (DIPINDAHKAN KE ATAS AGAR BISA DIIMPORT)
# ============================================================

# 1. CACHE UNTUK FILTER OPTIONS (jarang berubah - 1 jam)
@st.cache_data(ttl=3600)
def get_filter_options():
    """Mendapatkan opsi filter - cache 1 jam"""
    try:
        db = next(get_db())
        pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        bu_options = ["Semua"] + [b[0] for b in db.query(FPTK.business_unit).distinct().all() if b[0]]
        dir_options = ["Semua"] + [d[0] for d in db.query(FPTK.direktorat).distinct().all() if d[0]]
        return pic_options, bu_options, dir_options
    except Exception as e:
        return ["Semua"], ["Semua"], ["Semua"]

# 2. CACHE UNTUK DATA FPTK (5 menit auto refresh)
@st.cache_data(ttl=300)
def load_fptk_data(
    pic_filter=None, 
    status_filter=None, 
    bu_filter=None, 
    dir_filter=None,
    filter_kat=None,
    date_from=None,
    date_to=None
):
    """
    Memuat data FPTK dengan filter - cache 5 menit
    """
    try:
        db = next(get_db())
        query = db.query(FPTK)
        
        if pic_filter and pic_filter != "Semua":
            query = query.filter(FPTK.pic_recruiter == pic_filter)
        if status_filter and status_filter != "Semua":
            query = query.filter(FPTK.status == status_filter)
        if bu_filter and bu_filter != "Semua":
            query = query.filter(FPTK.business_unit == bu_filter)
        if dir_filter and dir_filter != "Semua":
            query = query.filter(FPTK.direktorat == dir_filter)
        if filter_kat and filter_kat != "Semua":
            query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)
        if date_from:
            query = query.filter(FPTK.fptk_date_real >= date_from)
        if date_to:
            query = query.filter(FPTK.fptk_date_real <= date_to)
        
        df = pd.read_sql(query.statement, db.bind)
        
        # Simpan timestamp terakhir query ke session state
        st.session_state['last_fptk_load'] = datetime.now()
        
        return df
    except Exception as e:
        st.error(f"❌ Gagal membaca data FPTK: {str(e)}")
        return pd.DataFrame()

# 3. CACHE UNTUK DATA SOURCING (5 menit auto refresh)
@st.cache_data(ttl=300)
def load_sourcing_data(
    pic_filter=None,
    date_from=None,
    date_to=None
):
    """Memuat data sourcing dengan cache 5 menit"""
    try:
        db = next(get_db())
        query = db.query(DBSourcing)
        
        if pic_filter and pic_filter != "Semua":
            query = query.filter(DBSourcing.rekruter == pic_filter)
        if date_from:
            query = query.filter(DBSourcing.sourcing_date >= date_from)
        if date_to:
            query = query.filter(DBSourcing.sourcing_date <= date_to)
        
        df = pd.read_sql(query.statement, db.bind)
        
        # Simpan timestamp terakhir query ke session state
        st.session_state['last_sourcing_load'] = datetime.now()
        
        return df
    except Exception as e:
        return pd.DataFrame()

# 4. CACHE UNTUK METRIK (tergantung data FPTK)
@st.cache_data(ttl=300)
def calculate_metrics(df):
    """
    Menghitung semua metrik dari DataFrame - cache 5 menit
    """
    if df.empty or 'status' not in df:
        return {
            'total': 0, 'op': 0, 'closed': 0, 'cancel': 0,
            'fulfillment_rate': 0, 'closed_sla_rate': 0, 'total_pic': 0
        }
    
    total = len(df)
    op = len(df[df['status'] == 'OP'])
    closed = len(df[df['status'] == 'Closed'])
    cancel = len(df[df['status'] == 'Cancel'])
    
    # Fulfillment Rate
    denominator = total - cancel
    fulfillment_rate = (closed / denominator * 100) if denominator > 0 else 0
    
    # SLA Rate
    if 'detail_sla' in df.columns:
        closed_df = df[df['status'] == 'Closed']
        closed_lulus = len(closed_df[closed_df['detail_sla'] == 'Closed Lulus SLA'])
        closed_tidak = len(closed_df[closed_df['detail_sla'] == 'Closed Tidak Lulus SLA'])
        total_closed_sla = closed_lulus + closed_tidak
        closed_sla_rate = (closed_lulus / total_closed_sla * 100) if total_closed_sla > 0 else 0
    else:
        closed_sla_rate = 0
    
    total_pic = len(df['pic_recruiter'].unique()) if 'pic_recruiter' in df else 0
    
    return {
        'total': total, 'op': op, 'closed': closed, 'cancel': cancel,
        'fulfillment_rate': fulfillment_rate, 'closed_sla_rate': closed_sla_rate,
        'total_pic': total_pic
    }

# 5. CACHE UNTUK UPLOAD CYCLE (1 menit - lebih dinamis)
@st.cache_data(ttl=60)
def get_upload_cycle_progress():
    """Mendapatkan progress upload cycle - cache 1 menit"""
    try:
        db = next(get_db())
        cycle = db.query(UploadCycle).filter(
            UploadCycle.ended_at.is_(None)
        ).order_by(UploadCycle.created_at.desc()).first()
        
        if cycle:
            statuses = db.query(UploadStatus).filter(
                UploadStatus.cycle_id == cycle.id
            ).all()
            progress_data = []
            for s in statuses:
                user_obj = db.query(User).filter(User.id == s.user_id).first()
                progress_data.append({
                    "User": user_obj.display_name if user_obj else s.user_id,
                    "PIC": user_obj.pic_recruiter if user_obj else "-",
                    "Status": s.status
                })
            return pd.DataFrame(progress_data)
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# 6. CACHE UNTUK ROLE ADMIN (5 menit)
@st.cache_data(ttl=300)
def check_admin_role():
    """Cek apakah user admin - cache 5 menit"""
    try:
        db = next(get_db())
        return is_admin(db)
    except:
        return False


# ============================================================
# FUNGSI UTAMA DASHBOARD
# ============================================================

def show_dashboard():
    st.title("📊 Dashboard FPTK & Sourcing")
    st.markdown("---")
    
    # ============================================================
    # SIDEBAR FILTERS - HANYA FILTER, TANPA CACHE CONTROL
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now() - timedelta(days=90))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())
        
        # Ambil opsi filter dari CACHE
        pic_options, bu_options, dir_options = get_filter_options()
        
        pic_filter = st.sidebar.selectbox("PIC Recruiter", pic_options)
        status_options = ["Semua", "OP", "Closed", "Cancel"]
        status_filter = st.sidebar.selectbox("Status", status_options)
        bu_filter = st.sidebar.selectbox("Business Unit", bu_options)
        dir_filter = st.sidebar.selectbox("Direktorat", dir_options)
        filter_kat_options = ["Semua", "CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]
        filter_kat = st.sidebar.selectbox("Filter Kategorisasi", filter_kat_options)
        
        st.markdown("---")
        
        # Export
        if st.button("📥 Export CSV", use_container_width=True):
            st.session_state.export_data = True

    # ============================================================
    # LOAD DATA (dengan spinner & cache)
    # ============================================================
    with st.spinner("📊 Memuat data..."):
        # Load FPTK data dari cache
        df = load_fptk_data(
            pic_filter=pic_filter,
            status_filter=status_filter,
            bu_filter=bu_filter,
            dir_filter=dir_filter,
            filter_kat=filter_kat,
            date_from=date_from,
            date_to=date_to
        )
        
        # Load Sourcing data dari cache
        df_sourcing = load_sourcing_data(
            pic_filter=pic_filter,
            date_from=date_from,
            date_to=date_to
        )
    
    # Cek admin role dari cache
    admin = check_admin_role()
    
    # ============================================================
    # METRIC CARDS
    # ============================================================
    metrics = calculate_metrics(df)
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total FPTK", f"{metrics['total']:,}")
    c2.metric("OP", f"{metrics['op']:,}")
    c3.metric("Closed", f"{metrics['closed']:,}")
    c4.metric("Cancel", f"{metrics['cancel']:,}")
    c5.metric("Fulfillment Rate", f"{metrics['fulfillment_rate']:.1f}%")
    c6.metric("Closed Sesuai SLA", f"{metrics['closed_sla_rate']:.1f}%")
    st.markdown("---")
    
    # ============================================================
    # ROW 1: LINE CHART + STATUS PIE
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        if metrics['total'] > 0 and 'fptk_date_real' in df:
            df['date'] = pd.to_datetime(df['fptk_date_real'])
            trend = df.groupby(df['date'].dt.to_period('W')).size().reset_index()
            trend.columns = ['Minggu', 'Jumlah']
            trend['Minggu'] = trend['Minggu'].astype(str)
            fig = px.line(trend, x='Minggu', y='Jumlah', title='📈 Trend FPTK per Minggu', markers=True)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data trend")
    
    with col2:
        if metrics['total'] > 0:
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig = px.pie(status_counts, values='Count', names='Status', title='📊 Distribusi Status',
                         color='Status', color_discrete_map={'OP': '#2ecc71', 'Closed': '#3498db', 'Cancel': '#e74c3c'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data status")
    
    # ============================================================
    # ROW 2: 3 PIE/ DONUT CHARTS
    # ============================================================
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if metrics['total'] > 0 and 'direktorat' in df and df['direktorat'].notna().any():
            dir_counts = df['direktorat'].value_counts().reset_index()
            dir_counts.columns = ['Direktorat', 'Count']
            fig = px.pie(dir_counts, values='Count', names='Direktorat', title='🏢 Direktorat')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data")
    
    with col2:
        if metrics['total'] > 0 and 'business_unit' in df and df['business_unit'].notna().any():
            bu_counts = df['business_unit'].value_counts().reset_index()
            bu_counts.columns = ['Business Unit', 'Count']
            fig = px.pie(bu_counts, values='Count', names='Business Unit', title='🏢 Business Unit')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data")
    
    with col3:
        if metrics['total'] > 0 and 'level_fptk' in df and df['level_fptk'].notna().any():
            level_counts = df['level_fptk'].value_counts().reset_index()
            level_counts.columns = ['Level', 'Count']
            fig = px.bar(level_counts, x='Level', y='Count', title='📊 Level FPTK', color='Count')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data")
    
    # ============================================================
    # ROW 3: BOXPLOT + TOP PIC
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        if metrics['total'] > 0 and 'jumlah_sla' in df and 'pic_recruiter' in df:
            sla_df = df[df['jumlah_sla'] > 0][['pic_recruiter', 'jumlah_sla']].dropna()
            if len(sla_df) > 0:
                top_pics = sla_df['pic_recruiter'].value_counts().head(10).index
                sla_df = sla_df[sla_df['pic_recruiter'].isin(top_pics)]
                fig = px.box(sla_df, x='pic_recruiter', y='jumlah_sla', title='📦 Distribusi SLA per PIC')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data SLA")
        else:
            st.info("Tidak ada data SLA")
    
    with col2:
        if metrics['total'] > 0 and 'pic_recruiter' in df:
            pic_counts = df['pic_recruiter'].value_counts().reset_index()
            pic_counts.columns = ['PIC', 'Jumlah FPTK']
            pic_counts = pic_counts.head(10)
            fig = px.bar(pic_counts, x='PIC', y='Jumlah FPTK', title='🏆 Top 10 PIC Performance', color='Jumlah FPTK')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data PIC")
    
    # ============================================================
    # ROW 4: FUNNEL SOURCING
    # ============================================================
    st.subheader("🔍 Funnel Sourcing")
    
    if not df_sourcing.empty:
        funnel_data = []
        stages = [
            ("Sourcing HR", 'sourcing_hr'),
            ("Shortlist CV", 'shortlist_cv'),
            ("Psikotes", 'psikotes'),
            ("HR Interview", 'hr_interview'),
            ("User Interview", 'user_interview'),
            ("Offering", 'offering'),
            ("Day 1", 'day1')
        ]
        
        for label, col in stages:
            if col in df_sourcing.columns:
                count = df_sourcing[col].notna().sum()
            else:
                count = 0
            funnel_data.append({"Stage": label, "Count": count})
        
        df_funnel = pd.DataFrame(funnel_data)
        if df_funnel['Count'].sum() > 0:
            fig = go.Figure(go.Funnel(
                y=df_funnel['Stage'],
                x=df_funnel['Count'],
                textposition="inside",
                textinfo="value+percent initial"
            ))
            fig.update_layout(title="Funnel Sourcing", height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data funnel sourcing")
    else:
        st.info("Tidak ada data sourcing")

    # ============================================================
    # ROW 5: SLA COMPLIANCE + HEATMAP
    # ============================================================
    try:
        c1, c2 = st.columns(2)
            
        with c1:
            st.subheader("✅ Detail SLA Distribution")
            if 'detail_sla' in df and df['detail_sla'].notna().any():
                detail_counts = df['detail_sla'].value_counts().reset_index()
                detail_counts.columns = ['Detail SLA', 'Count']
                
                sla_order = [
                    "OP Belum Lewat SLA",
                    "OP Tidak Lulus SLA",
                    "Closed Lulus SLA",
                    "Closed Tidak Lulus SLA",
                    "Cancel FPTK"
                ]
                
                sla_order_existing = [s for s in sla_order if s in detail_counts['Detail SLA'].values]
                detail_counts = detail_counts[detail_counts['Detail SLA'].isin(sla_order_existing)]
                
                if not detail_counts.empty:
                    color_map = {
                        "OP Belum Lewat SLA": "#2ecc71",
                        "OP Tidak Lulus SLA": "#e74c3c",
                        "Closed Lulus SLA": "#3498db",
                        "Closed Tidak Lulus SLA": "#e67e22",
                        "Cancel FPTK": "#95a5a6"
                    }
                    
                    fig = px.bar(
                        detail_counts, 
                        x='Detail SLA', 
                        y='Count', 
                        title='Detail SLA Distribution',
                        color='Detail SLA',
                        color_discrete_map=color_map,
                        text='Count'
                    )
                    fig.update_layout(height=400, xaxis_tickangle=-45)
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Belum ada data Detail SLA")
            else:
                st.info("Belum ada data Detail SLA")        
        with c2:
            if 'fptk_date_real' in df and df['fptk_date_real'].notna().any():
                df['date'] = pd.to_datetime(df['fptk_date_real'])
                df['month'] = df['date'].dt.strftime('%Y-%m')
                df['day'] = df['date'].dt.day
                heatmap_data = df.groupby(['month', 'day']).size().reset_index(name='count')
                if len(heatmap_data) > 0:
                    fig = px.density_heatmap(heatmap_data, x='day', y='month', z='count',
                                             title='🔥 Persebaran FPTK (Calendar Heatmap)',
                                             color_continuous_scale='Blues')
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Tidak ada data heatmap")
            else:
                st.info("Tidak ada data heatmap")
    except Exception as e:
        st.error(f"Error grafik ROW 5: {str(e)}")
    
    # ============================================================
    # ROW 6: UPLOAD CYCLE PROGRESS (ADMIN ONLY)
    # ============================================================
    if admin:
        st.markdown("---")
        st.subheader("🔄 Upload Cycle Progress (Admin)")
        df_progress = get_upload_cycle_progress()
        if not df_progress.empty:
            done = len(df_progress[df_progress['Status'] == 'Done'])
            st.progress(done / len(df_progress) if len(df_progress) > 0 else 0, 
                       text=f"Progress: {done}/{len(df_progress)} user selesai")
            st.dataframe(df_progress, use_container_width=True, height=200)
        else:
            st.info("Belum ada data upload cycle")
    
    # ============================================================
    # EXPORT
    # ============================================================
    if st.session_state.get('export_data', False):
        st.session_state.export_data = False
        if not df.empty:
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download Data (CSV)",
                csv,
                f"fptk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )
