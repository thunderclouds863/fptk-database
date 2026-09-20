# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from core.database import get_db
from core.models import FPTK, DBSourcing, User, UploadStatus, UploadCycle
from core.auth import get_current_user, is_admin
from core.utils import get_filter_options_from_db
from datetime import datetime, timedelta
import time


if "cache_cleared_v2" not in st.session_state:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["cache_cleared_v2"] = True


@st.cache_data(ttl=300, show_spinner=False)
def load_fptk_data(
    pic_filter=None, status_filter=None, bu_filter=None,
    dir_filter=None, divisi_filter=None, dept_filter=None,
    filter_kat=None, date_from=None, date_to=None
):
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
        if divisi_filter and divisi_filter != "Semua":
            query = query.filter(FPTK.divisi == divisi_filter)
        if dept_filter and dept_filter != "Semua":
            query = query.filter(FPTK.department == dept_filter)
        if filter_kat and filter_kat != "Semua":
            query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)
        if date_from:
            query = query.filter(FPTK.fptk_date_real >= date_from)
        if date_to:
            query = query.filter(FPTK.fptk_date_real <= date_to)

        df = pd.read_sql(query.statement, db.bind)
        st.session_state['last_fptk_load'] = datetime.now()
        return df
    except Exception as e:
        st.error(f"Gagal membaca data FPTK: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def load_sourcing_data(pic_filter=None, date_from=None, date_to=None):
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
        st.session_state['last_sourcing_load'] = datetime.now()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def calculate_metrics(df):
    if df.empty or 'status' not in df:
        return {
            'total': 0, 'op': 0, 'closed': 0, 'cancel': 0,
            'diproses': 0, 'fulfillment_rate': 0, 'closed_sla_rate': 0
        }

    total = len(df)
    op = len(df[df['status'] == 'OP'])
    closed = len(df[df['status'] == 'Closed'])
    cancel = len(df[df['status'] == 'Cancel'])
    diproses = total - closed

    denominator = total - cancel
    fulfillment_rate = (closed / denominator * 100) if denominator > 0 else 0

    if 'detail_sla' in df.columns:
        closed_df = df[df['status'] == 'Closed']
        closed_lulus = len(closed_df[closed_df['detail_sla'] == 'Closed Lulus SLA'])
        closed_tidak = len(closed_df[closed_df['detail_sla'] == 'Closed Tidak Lulus SLA'])
        total_closed_sla = closed_lulus + closed_tidak
        closed_sla_rate = (closed_lulus / total_closed_sla * 100) if total_closed_sla > 0 else 0
    else:
        closed_sla_rate = 0

    return {
        'total': total, 'op': op, 'closed': closed, 'cancel': cancel,
        'diproses': diproses,
        'fulfillment_rate': fulfillment_rate,
        'closed_sla_rate': closed_sla_rate
    }


def get_week_number(dt):
    if pd.isna(dt):
        return None
    try:
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
        if isinstance(dt, (datetime, pd.Timestamp)):
            return dt.isocalendar()[1]
    except Exception:
        pass
    return None


def build_weekly_metrics(df):
    """
    Hitung semua metric per week (W1-W53) dari data FPTK.
    Return: DataFrame dengan index week_num, kolom metric.
    """
    weeks = list(range(1, 54))
    metrics = pd.DataFrame(index=weeks)
    metrics.index.name = 'week'

    if df.empty:
        for col in [
            'diterima', 'diterima_akum', 'diproses_akum',
            'pemenuhan', 'pemenuhan_akum', 'sisa', 'cancel',
            'cancel_akum', 'op_belum_sla', 'op_lulus_lewat_sla',
            'closed_lulus_sla', 'closed_tidak_lulus_sla',
            'pct_pemenuhan', 'pct_proses', 'pct_closed_lulus'
        ]:
            metrics[col] = 0
        return metrics

    df = df.copy()
    if 'fptk_date_real' in df.columns:
        df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'], errors='coerce')
        df['week'] = df['fptk_date_real'].apply(get_week_number)

    for w in weeks:
        df_w = df[df['week'] == w] if 'week' in df.columns else pd.DataFrame()

        diterima = len(df_w)
        closed = len(df_w[df_w['status'] == 'Closed']) if 'status' in df_w.columns else 0
        cancel = len(df_w[df_w['status'] == 'Cancel']) if 'status' in df_w.columns else 0

        metrics.loc[w, 'diterima'] = diterima
        metrics.loc[w, 'pemenuhan'] = closed
        metrics.loc[w, 'cancel'] = cancel

    metrics['diterima_akum'] = metrics['diterima'].cumsum()
    metrics['pemenuhan_akum'] = metrics['pemenuhan'].cumsum()
    metrics['cancel_akum'] = metrics['cancel'].cumsum()
    metrics['diproses_akum'] = metrics['diterima_akum'] - metrics['pemenuhan_akum']
    metrics['sisa'] = metrics['diterima_akum'] - metrics['pemenuhan_akum']

    metrics['pct_pemenuhan'] = (metrics['pemenuhan_akum'] / metrics['diterima_akum'].replace(0, pd.NA) * 100).fillna(0)
    metrics['pct_proses'] = (metrics['diproses_akum'] / metrics['diterima_akum'].replace(0, pd.NA) * 100).fillna(0)

    return metrics


def build_sla_weekly(df):
    """
    Hitung SLA per week: OP belum lewat, OP tidak lulus, Closed lulus, Closed tidak lulus.
    """
    weeks = list(range(1, 54))
    sla_df = pd.DataFrame(index=weeks)
    sla_df.index.name = 'week'

    for col in ['op_belum_sla', 'op_tidak_lulus', 'closed_lulus', 'closed_tidak_lulus', 'pct_closed_lulus']:
        sla_df[col] = 0

    if df.empty or 'detail_sla' not in df.columns:
        return sla_df

    df = df.copy()
    if 'fptk_date_real' in df.columns:
        df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'], errors='coerce')
        df['week'] = df['fptk_date_real'].apply(get_week_number)

    for w in weeks:
        df_w = df[df['week'] == w] if 'week' in df.columns else pd.DataFrame()
        if df_w.empty:
            continue

        sla_df.loc[w, 'op_belum_sla'] = len(df_w[df_w['detail_sla'] == 'OP Belum Lewat SLA'])
        sla_df.loc[w, 'op_tidak_lulus'] = len(df_w[df_w['detail_sla'] == 'OP Tidak Lulus SLA'])
        sla_df.loc[w, 'closed_lulus'] = len(df_w[df_w['detail_sla'] == 'Closed Lulus SLA'])
        sla_df.loc[w, 'closed_tidak_lulus'] = len(df_w[df_w['detail_sla'] == 'Closed Tidak Lulus SLA'])

    sla_df['op_belum_sla'] = sla_df['op_belum_sla'].cumsum()
    sla_df['op_tidak_lulus'] = sla_df['op_tidak_lulus'].cumsum()
    sla_df['closed_lulus'] = sla_df['closed_lulus'].cumsum()
    sla_df['closed_tidak_lulus'] = sla_df['closed_tidak_lulus'].cumsum()

    total_sla = sla_df['closed_lulus'] + sla_df['closed_tidak_lulus']
    sla_df['pct_closed_lulus'] = (sla_df['closed_lulus'] / total_sla.replace(0, pd.NA) * 100).fillna(0)

    return sla_df


def show_dashboard():
    st.title("📊 Recruitment Analytic Dashboard")
    st.markdown("---")

    try:
        filter_opts = get_filter_options_from_db()
    except Exception:
        filter_opts = {
            "pic_options": [], "bu_options": [], "direktorat_options": [],
            "filter_kategorisasi_options": [], "divisi_options": [],
            "dept_options": [], "status_options": ["OP", "Closed", "Cancel"],
        }

    with st.sidebar:
        st.markdown("### 🔍 Filters")

        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now() - timedelta(days=90))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())

        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + filter_opts.get("pic_options", []))
        status_filter = st.selectbox("Status", ["Semua"] + filter_opts.get("status_options", ["OP", "Closed", "Cancel"]))
        bu_filter = st.selectbox("Business Unit", ["Semua"] + filter_opts.get("bu_options", []))
        dir_filter = st.selectbox("Direktorat", ["Semua"] + filter_opts.get("direktorat_options", []))

        divisi_options = filter_opts.get("divisi_options", [])
        divisi_filter = st.selectbox("Divisi", ["Semua"] + divisi_options) if divisi_options else "Semua"

        dept_options = filter_opts.get("dept_options", [])
        dept_filter = st.selectbox("Department", ["Semua"] + dept_options) if dept_options else "Semua"

        filter_kat = st.selectbox("Filter Kategorisasi", ["Semua"] + filter_opts.get("filter_kategorisasi_options", []))

        st.markdown("---")

        if st.button("📥 Export CSV", use_container_width=True):
            st.session_state.export_data = True

        if st.button("🔄 Refresh Filter Options", use_container_width=True):
            get_filter_options_from_db.clear()
            st.session_state.pop("cache_cleared_v2", None)
            st.success("✅ Filter refreshed!")
            time.sleep(0.3)
            st.rerun()

    with st.spinner("📊 Memuat data..."):
        df = load_fptk_data(
            pic_filter=pic_filter,
            status_filter=status_filter,
            bu_filter=bu_filter,
            dir_filter=dir_filter,
            divisi_filter=divisi_filter,
            dept_filter=dept_filter,
            filter_kat=filter_kat,
            date_from=date_from,
            date_to=date_to
        )

        df_sourcing = load_sourcing_data(
            pic_filter=pic_filter,
            date_from=date_from,
            date_to=date_to
        )

    admin = is_admin(next(get_db()))
    metrics = calculate_metrics(df)

    # ============================================================
    # SECTION 1: KPI CARDS (Persis Excel Dashboard Sheet)
    # ============================================================
    st.markdown("### 📌 KPI FPTK")

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Total FPTK", f"{metrics['total']:,}")
    c2.metric("FPTK Diproses", f"{metrics['diproses']:,}")
    c3.metric("Closed", f"{metrics['closed']:,}")
    c4.metric("Open", f"{metrics['op']:,}")
    c5.metric("Cancel", f"{metrics['cancel']:,}")
    c6.metric("Fulfillment Rate", f"{metrics['fulfillment_rate']:.1f}%")
    c7.metric("Closed Sesuai SLA", f"{metrics['closed_sla_rate']:.1f}%")

    st.markdown("---")

    # ============================================================
    # SECTION 2: MPP TREND PER WEEK (Chart 1 di Grafik MPP)
    # ============================================================
    st.markdown("### 📈 MPP Trend Per Week (Akumulatif)")

    weekly = build_weekly_metrics(df)
    sla_weekly = build_sla_weekly(df)

    weeks = list(range(1, 54))

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['diterima_akum'].values,
        name='Jumlah FPTK Diterima (Akumulatif)',
        mode='lines+markers', line=dict(color='#3498db', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['diproses_akum'].values,
        name='Jumlah FPTK Diproses',
        mode='lines+markers', line=dict(color='#f39c12', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['pemenuhan_akum'].values,
        name='Pemenuhan (terima offer)',
        mode='lines+markers', line=dict(color='#2ecc71', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['sisa'].values,
        name='Sisa FPTK',
        mode='lines+markers', line=dict(color='#e74c3c', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['cancel_akum'].values,
        name='Cancel',
        mode='lines+markers', line=dict(color='#95a5a6', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['pct_pemenuhan'].values,
        name='% Pemenuhan',
        mode='lines+markers', line=dict(color='#9b59b6', width=2, dash='dot'),
        yaxis='y2'
    ))
    fig.add_trace(go.Scatter(
        x=weeks, y=weekly['pct_proses'].values,
        name='% Proses',
        mode='lines+markers', line=dict(color='#1abc9c', width=2, dash='dot'),
        yaxis='y2'
    ))

    fig.update_layout(
        height=500,
        title="MPP Trend Per Week (Akumulatif)",
        xaxis=dict(title="Week (W1-W53)", tickmode='linear', tick0=1, dtick=1),
        yaxis=dict(title="Jumlah FPTK"),
        yaxis2=dict(title="%", overlaying='y', side='right', range=[0, 110]),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ============================================================
    # SECTION 3: SLA TREND (Chart 2 di Grafik MPP)
    # ============================================================
    st.markdown("### ✅ SLA Trend Per Week (Akumulatif)")

    fig2 = go.Figure()

    fig2.add_trace(go.Bar(
        x=weeks, y=sla_weekly['op_belum_sla'].values,
        name='OP Belum Lewat SLA',
        marker_color='#2ecc71'
    ))
    fig2.add_trace(go.Bar(
        x=weeks, y=sla_weekly['op_tidak_lulus'].values,
        name='OP Tidak Lulus SLA',
        marker_color='#e74c3c'
    ))
    fig2.add_trace(go.Bar(
        x=weeks, y=sla_weekly['closed_lulus'].values,
        name='Closed Lulus SLA',
        marker_color='#3498db'
    ))
    fig2.add_trace(go.Bar(
        x=weeks, y=sla_weekly['closed_tidak_lulus'].values,
        name='Closed Tidak Lulus SLA',
        marker_color='#e67e22'
    ))
    fig2.add_trace(go.Scatter(
        x=weeks, y=sla_weekly['pct_closed_lulus'].values,
        name='% Closed Lulus SLA',
        mode='lines+markers',
        line=dict(color='#9b59b6', width=3),
        yaxis='y2'
    ))

    fig2.update_layout(
        barmode='stack',
        height=500,
        title="SLA Trend Per Week (Akumulatif)",
        xaxis=dict(title="Week (W1-W53)", tickmode='linear', tick0=1, dtick=1),
        yaxis=dict(title="Jumlah FPTK"),
        yaxis2=dict(title="% Closed Lulus SLA", overlaying='y', side='right', range=[0, 110]),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified'
    )

    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ============================================================
    # SECTION 4: AVERAGE PER KUARTAL
    # ============================================================
    st.markdown("### 📊 Average FPTK per Week (Per Kuartal)")

    quarters = {
        "Q1 (W1-W13)": (1, 13),
        "Q2 (W14-W26)": (14, 26),
        "Q3 (W27-W39)": (27, 39),
        "Q4 (W40-W53)": (40, 53),
    }

    avg_data = []
    for q_label, (w_start, w_end) in quarters.items():
        diterima = weekly.loc[w_start:w_end, 'diterima']
        closed = weekly.loc[w_start:w_end, 'pemenuhan']
        avg_data.append({
            "Kuartal": q_label,
            "Avg Diterima/Week": round(diterima.mean(), 2) if len(diterima) > 0 else 0,
            "Avg Closed/Week": round(closed.mean(), 2) if len(closed) > 0 else 0,
            "Total Diterima": int(diterima.sum()),
            "Total Closed": int(closed.sum()),
        })

    st.dataframe(pd.DataFrame(avg_data), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ============================================================
    # SECTION 5: TOP 10 PIC PERFORMANCE (Bar Chart)
    # ============================================================
    col1, col2 = st.columns(2)

    with col1:
        if metrics['total'] > 0 and 'pic_recruiter' in df.columns:
            pic_counts = df['pic_recruiter'].value_counts().reset_index().head(10)
            pic_counts.columns = ['PIC', 'Jumlah FPTK']
            fig = px.bar(
                pic_counts, x='PIC', y='Jumlah FPTK',
                title='🏆 Top 10 PIC Performance',
                color='Jumlah FPTK',
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data PIC")

    with col2:
        if metrics['total'] > 0 and 'filter_kategorisasi_fptk' in df.columns:
            kat_counts = df['filter_kategorisasi_fptk'].value_counts().reset_index()
            kat_counts.columns = ['Kategori', 'Count']
            fig = px.pie(
                kat_counts, values='Count', names='Kategori',
                title='📊 Distribusi Filter Kategorisasi FPTK'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data kategori")

    st.markdown("---")

    # ============================================================
    # SECTION 6: DISTRIBUSI STATUS & DIRECTORAT
    # ============================================================
    col1, col2, col3 = st.columns(3)

    with col1:
        if metrics['total'] > 0:
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig = px.pie(
                status_counts, values='Count', names='Status',
                title='📊 Distribusi Status',
                color='Status',
                color_discrete_map={'OP': '#2ecc71', 'Closed': '#3498db', 'Cancel': '#e74c3c'}
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if metrics['total'] > 0 and 'business_unit' in df.columns and df['business_unit'].notna().any():
            bu_counts = df['business_unit'].value_counts().reset_index()
            bu_counts.columns = ['Business Unit', 'Count']
            fig = px.pie(bu_counts, values='Count', names='Business Unit', title='🏢 Business Unit')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col3:
        if metrics['total'] > 0 and 'direktorat' in df.columns and df['direktorat'].notna().any():
            dir_counts = df['direktorat'].value_counts().reset_index().head(10)
            dir_counts.columns = ['Direktorat', 'Count']
            fig = px.bar(
                dir_counts, x='Count', y='Direktorat',
                title='🏢 Top 10 Direktorat',
                orientation='h',
                color='Count',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ============================================================
    # SECTION 7: RECRUITER PERFORMANCE TABLE (Persis Sheet 3)
    # ============================================================
    st.markdown("### 👥 Recruiter Performance")

    if metrics['total'] > 0 and 'pic_recruiter' in df.columns:
        recruiters = sorted(df['pic_recruiter'].dropna().unique())
        perf_rows = []

        for r in recruiters:
            df_r = df[df['pic_recruiter'] == r]
            open_c = len(df_r[df_r['status'] == 'OP'])
            closed_c = len(df_r[df_r['status'] == 'Closed'])
            cancel_c = len(df_r[df_r['status'] == 'Cancel'])
            total_c = len(df_r)

            closed_lulus = len(df_r[(df_r['status'] == 'Closed') & (df_r['detail_sla'] == 'Closed Lulus SLA')])
            closed_tidak = len(df_r[(df_r['status'] == 'Closed') & (df_r['detail_sla'] == 'Closed Tidak Lulus SLA')])
            op_lewat = len(df_r[(df_r['status'] == 'OP') & (df_r['detail_sla'] == 'OP Tidak Lulus SLA')])

            rate = (closed_lulus / (closed_c + op_lewat) * 100) if (closed_c + op_lewat) > 0 else 0

            perf_rows.append({
                "Nama Recruiter": r,
                "Open": open_c,
                "Closed": closed_c,
                "Cancel": cancel_c,
                "Total": total_c,
                "Closed Sesuai SLA": closed_lulus,
                "Closed Tidak Sesuai SLA": closed_tidak,
                "OP Lewat SLA": op_lewat,
                "Rate (%)": round(rate, 1)
            })

        df_perf = pd.DataFrame(perf_rows)
        df_perf = df_perf.sort_values('Total', ascending=False)

        st.dataframe(df_perf, use_container_width=True, hide_index=True)

        total_row = {
            "Nama Recruiter": "TOTAL",
            "Open": df_perf['Open'].sum(),
            "Closed": df_perf['Closed'].sum(),
            "Cancel": df_perf['Cancel'].sum(),
            "Total": df_perf['Total'].sum(),
            "Closed Sesuai SLA": df_perf['Closed Sesuai SLA'].sum(),
            "Closed Tidak Sesuai SLA": df_perf['Closed Tidak Sesuai SLA'].sum(),
            "OP Lewat SLA": df_perf['OP Lewat SLA'].sum(),
            "Rate (%)": round(
                df_perf['Closed Sesuai SLA'].sum() /
                (df_perf['Closed'].sum() + df_perf['OP Lewat SLA'].sum()) * 100, 1
            ) if (df_perf['Closed'].sum() + df_perf['OP Lewat SLA'].sum()) > 0 else 0
        }

        st.markdown("**TOTAL:**")
        st.dataframe(pd.DataFrame([total_row]), use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada data recruiter.")

    st.markdown("---")

    # ============================================================
    # SECTION 8: POSITION CLOSED PER RECRUITER PER LEVEL
    # ============================================================
    st.markdown("### 🎯 Position Closed per Recruiter per Level Jabatan")

    if metrics['total'] > 0 and 'level_fptk' in df.columns:
        levels = ["1A", "1B", "1C", "2A", "2B", "2C", "3A", "3B", "3C", "4A", "4B"]

        pivot_rows = []
        for r in sorted(df['pic_recruiter'].dropna().unique()):
            df_r = df[(df['pic_recruiter'] == r) & (df['status'] == 'Closed')]
            row = {"Nama Recruiter": r}
            total_r = 0
            for lvl in levels:
                count = len(df_r[df_r['level_fptk'] == lvl])
                row[lvl] = count
                total_r += count
            row["Total"] = total_r
            pivot_rows.append(row)

        if pivot_rows:
            pivot_df = pd.DataFrame(pivot_rows)
            st.dataframe(pivot_df, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada data Closed per level.")
    else:
        st.info("Tidak ada data level FPTK.")

    st.markdown("---")

    # ============================================================
    # SECTION 9: COMPLEXITY CLOSED (Easy/Moderate/Hard)
    # ============================================================
    st.markdown("### 🧩 Complexity Closed Position per Recruiter")

    if metrics['total'] > 0 and 'level_fptk' in df.columns:
        easy_levels = {"1A", "1B", "1C", "2A"}
        moderate_levels = {"2B", "2C", "3A"}
        hard_levels = {"3B", "3C", "4A", "4B"}

        complexity_rows = []
        for r in sorted(df['pic_recruiter'].dropna().unique()):
            df_r = df[(df['pic_recruiter'] == r) & (df['status'] == 'Closed')]
            easy = sum(len(df_r[df_r['level_fptk'] == lvl]) for lvl in easy_levels)
            moderate = sum(len(df_r[df_r['level_fptk'] == lvl]) for lvl in moderate_levels)
            hard = sum(len(df_r[df_r['level_fptk'] == lvl]) for lvl in hard_levels)
            total_c = easy + moderate + hard

            if total_c == 0:
                continue

            complexity_rows.append({
                "Recruiter": r,
                "Total": total_c,
                "Easy": easy,
                "% Easy": round(easy / total_c * 100, 1),
                "Moderate": moderate,
                "% Moderate": round(moderate / total_c * 100, 1),
                "Hard": hard,
                "% Hard": round(hard / total_c * 100, 1),
                "Profile": "Easy" if easy >= moderate and easy >= hard
                          else ("Moderate" if moderate >= hard else "Hard")
            })

        if complexity_rows:
            st.dataframe(pd.DataFrame(complexity_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada data kompleksitas.")
    else:
        st.info("Tidak ada data level FPTK.")

    st.markdown("---")

    # ============================================================
    # SECTION 10: POSITION OPEN PER RECRUITER PER LEVEL
    # ============================================================
    st.markdown("### 📂 Position Open per Recruiter per Level Jabatan")

    if metrics['total'] > 0 and 'level_fptk' in df.columns:
        levels = ["1A", "1B", "1C", "2A", "2B", "2C", "3A", "3B", "3C", "4A", "4B"]

        open_rows = []
        for r in sorted(df['pic_recruiter'].dropna().unique()):
            df_r = df[(df['pic_recruiter'] == r) & (df['status'] == 'OP')]
            row = {"Nama Recruiter": r}
            total_r = 0
            for lvl in levels:
                count = len(df_r[df_r['level_fptk'] == lvl])
                row[lvl] = count
                total_r += count
            row["Total"] = total_r
            open_rows.append(row)

        if open_rows:
            st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada data level FPTK.")

    st.markdown("---")

    # ============================================================
    # SECTION 11: EXPORT
    # ============================================================
    if st.session_state.get('export_data', False):
        st.session_state.export_data = False
        if not df.empty:
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download Data FPTK (CSV)",
                csv,
                f"fptk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )
