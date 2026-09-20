# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.database import get_db
from core.models import (
    FPTK, DBSourcing, User, UploadStatus, UploadCycle, UploadLog
)
from core.auth import get_current_user, is_admin
from core.utils import get_filter_options_from_db
from datetime import datetime, timedelta
import time


# ============================================================
# CACHE FIX
# ============================================================

if "cache_cleared_v3" not in st.session_state:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["cache_cleared_v3"] = True


# ============================================================
# CONSTANTS
# ============================================================

LEVEL_ORDER = ["1A", "1B", "1C", "2A", "2B", "2C",
               "3A", "3B", "3C", "4A", "4B", "4C", "5A", "5B", "5C"]

WEEK_NUMBERS = list(range(1, 54))

# Kategori FPTK yang dipakai di sheet Grafik MPP
FPTK_KATEGORI = ["CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]

# Direktorat yang dipakai di sheet Grafik MPP
DIREKTORAT_KATEGORI = [
    "Commercial CMD", "Commercial JES", "Commercial MP",
    "Manufacture CMD", "Manufacture JES", "Manufacture MP",
    "Sales General Trade CMD", "Sales General Trade JES", "Sales General Trade MP",
    "Sales Modern Trade", "Sales International Market",
    "Finance & Business Support", "Logistic & Distribution",
    "Procurement CMD & Corporate", "Procurement MP & JES",
    "CEO Office", "CEO, Corsec, & Investor Relation",
]


# ============================================================
# HELPER: GET WEEK NUMBER (ISO)
# ============================================================

def get_current_week():
    today = datetime.now().date()
    iso = today.isocalendar()
    return iso[1], iso[0]


def get_week_label(week_num, year):
    return f"Week {week_num}, {year}"


def get_week_range(week_num, year):
    try:
        jan4 = datetime(year, 1, 4).date()
        start_of_year_week = jan4 - timedelta(days=jan4.isoweekday() - 1)
        week_start = start_of_year_week + timedelta(weeks=week_num - 1)
        week_end = week_start + timedelta(days=6)
        return week_start, week_end
    except Exception:
        return None, None


# ============================================================
# CACHE: LOAD FPTK DATA
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_fptk_data(
    pic_filter=None,
    status_filter=None,
    bu_filter=None,
    dir_filter=None,
    divisi_filter=None,
    dept_filter=None,
    filter_kat=None,
    posisi_filter=None,
    date_from=None,
    date_to=None
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
        if posisi_filter and posisi_filter != "Semua":
            query = query.filter(FPTK.posisi == posisi_filter)
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


# ============================================================
# CACHE: FILTER OPTIONS
# ============================================================

@st.cache_data(ttl=300)
def get_posisi_options():
    try:
        db = next(get_db())
        posisi = sorted(set([
            r[0] for r in db.query(FPTK.posisi)
            .filter(FPTK.posisi.isnot(None), FPTK.posisi != "")
            .distinct().all() if r[0]
        ]))
        return posisi
    except Exception:
        return []


# ============================================================
# CACHE: METRICS
# ============================================================

@st.cache_data(ttl=300)
def calculate_metrics(df):
    if df.empty or 'status' not in df:
        return {
            'total': 0, 'op': 0, 'closed': 0, 'cancel': 0,
            'diproses': 0, 'fulfillment_rate': 0, 'closed_sla_rate': 0,
            'total_pic': 0
        }

    total = len(df)
    op = len(df[df['status'] == 'OP'])
    closed = len(df[df['status'] == 'Closed'])
    cancel = len(df[df['status'] == 'Cancel'])
    diproses = total - cancel

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

    total_pic = len(df['pic_recruiter'].unique()) if 'pic_recruiter' in df else 0

    return {
        'total': total, 'op': op, 'closed': closed, 'cancel': cancel,
        'diproses': diproses,
        'fulfillment_rate': fulfillment_rate,
        'closed_sla_rate': closed_sla_rate,
        'total_pic': total_pic
    }


# ============================================================
# HELPER: HITUNG WoW & MoM
# ============================================================

def calculate_wow(df):
    """Hitung Week over Week untuk total FPTK"""
    if df.empty or 'fptk_date_real' not in df:
        return 0, 0

    df = df.copy()
    df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'], errors='coerce')
    df = df.dropna(subset=['fptk_date_real'])

    if df.empty:
        return 0, 0

    df['week'] = df['fptk_date_real'].dt.isocalendar().week
    df['year'] = df['fptk_date_real'].dt.isocalendar().year

    today = datetime.now().date()
    current_week = today.isocalendar()[1]
    current_year = today.isocalendar()[0]

    this_week = len(df[(df['week'] == current_week) & (df['year'] == current_year)])

    prev_week = current_week - 1
    prev_year = current_year
    if prev_week < 1:
        prev_week = 52
        prev_year = current_year - 1

    last_week = len(df[(df['week'] == prev_week) & (df['year'] == prev_year)])

    if last_week == 0:
        wow_pct = 100 if this_week > 0 else 0
    else:
        wow_pct = ((this_week - last_week) / last_week) * 100

    return this_week, wow_pct


def calculate_mom(df):
    """Hitung Month over Month untuk total FPTK"""
    if df.empty or 'fptk_date_real' not in df:
        return 0, 0

    df = df.copy()
    df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'], errors='coerce')
    df = df.dropna(subset=['fptk_date_real'])

    if df.empty:
        return 0, 0

    df['month'] = df['fptk_date_real'].dt.month
    df['year'] = df['fptk_date_real'].dt.year

    today = datetime.now().date()
    current_month = today.month
    current_year = today.year

    this_month = len(df[(df['month'] == current_month) & (df['year'] == current_year)])

    prev_month = current_month - 1
    prev_year = current_year
    if prev_month < 1:
        prev_month = 12
        prev_year = current_year - 1

    last_month = len(df[(df['month'] == prev_month) & (df['year'] == prev_year)])

    if last_month == 0:
        mom_pct = 100 if this_month > 0 else 0
    else:
        mom_pct = ((this_month - last_month) / last_month) * 100

    return this_month, mom_pct


# ============================================================
# HELPER: HITUNG PER WEEK
# ============================================================

def build_week_matrix(df):
    """
    Build matrix mingguan W1-W53 untuk:
    - Jumlah FPTK Diterima (count per week based on fptk_date_real)
    - Pemenuhan (Closed) (count per week based on offering_date)
    - Cancel (count per week based on fptk_cancel_date)
    """
    matrix = {
        'diterima': {w: 0 for w in WEEK_NUMBERS},
        'closed': {w: 0 for w in WEEK_NUMBERS},
        'cancel': {w: 0 for w in WEEK_NUMBERS},
    }

    if df.empty:
        return matrix

    df = df.copy()

    # Diterima per week — pakai fptk_date_real
    if 'fptk_date_real' in df.columns:
        df['fptk_date_real'] = pd.to_datetime(df['fptk_date_real'], errors='coerce')
        valid = df.dropna(subset=['fptk_date_real'])
        for _, row in valid.iterrows():
            w = row['fptk_date_real'].isocalendar()[1]
            if 1 <= w <= 53:
                matrix['diterima'][w] += 1

    # Closed per week — pakai offering_date
    if 'offering_date' in df.columns and 'status' in df.columns:
        closed_df = df[df['status'] == 'Closed'].copy()
        closed_df['offering_date'] = pd.to_datetime(closed_df['offering_date'], errors='coerce')
        valid = closed_df.dropna(subset=['offering_date'])
        for _, row in valid.iterrows():
            w = row['offering_date'].isocalendar()[1]
            if 1 <= w <= 53:
                matrix['closed'][w] += 1

    # Cancel per week — pakai fptk_cancel_date
    if 'fptk_cancel_date' in df.columns and 'status' in df.columns:
        cancel_df = df[df['status'] == 'Cancel'].copy()
        cancel_df['fptk_cancel_date'] = pd.to_datetime(cancel_df['fptk_cancel_date'], errors='coerce')
        valid = cancel_df.dropna(subset=['fptk_cancel_date'])
        for _, row in valid.iterrows():
            w = row['fptk_cancel_date'].isocalendar()[1]
            if 1 <= w <= 53:
                matrix['cancel'][w] += 1

    return matrix


def build_category_week_matrix(df, category_field, category_value):
    """
    Build week matrix untuk kategori spesifik (FPTK atau Direktorat).
    """
    if df.empty or category_field not in df.columns:
        return {
            'diterima': {w: 0 for w in WEEK_NUMBERS},
            'closed': {w: 0 for w in WEEK_NUMBERS},
            'cancel': {w: 0 for w in WEEK_NUMBERS},
        }

    filtered = df[df[category_field] == category_value].copy()
    return build_week_matrix(filtered)


# ============================================================
# HELPER: BUILD DATAFRAME GRAFIK MPP
# ============================================================

def build_grafik_mpp_row(matrix, category_label=""):
    """
    Build 1 set baris grafik MPP (diterima, diproses, closed, sisa, cancel,
    OP Belum Lewat SLA, OP Tidak Lulus SLA, Closed Lulus SLA, Closed Tidak Lulus SLA)
    """
    diterima = matrix['diterima']
    closed = matrix['closed']
    cancel = matrix['cancel']

    rows = []
    rows.append(['Jumlah FPTK Diterima'] + [diterima[w] for w in WEEK_NUMBERS])
    rows.append(['Jumlah FPTK Diproses'] + [diterima[w] - cancel[w] for w in WEEK_NUMBERS])
    rows.append(['Pemenuhan (terima offer)'] + [closed[w] for w in WEEK_NUMBERS])
    rows.append(['Sisa FPTK'] + [diterima[w] - closed[w] for w in WEEK_NUMBERS])
    rows.append(['Cancel'] + [cancel[w] for w in WEEK_NUMBERS])

    return rows


# ============================================================
# HELPER: UPLOAD CYCLE INFO
# ============================================================

@st.cache_data(ttl=60)
def get_upload_cycle_info():
    try:
        db = next(get_db())
        cycle = db.query(UploadCycle).filter(
            UploadCycle.ended_at.is_(None)
        ).order_by(UploadCycle.created_at.desc()).first()

        if not cycle:
            return None

        statuses = db.query(UploadStatus).filter(
            UploadStatus.cycle_id == cycle.id
        ).all()

        total = len(statuses)
        done = len([s for s in statuses if s.status == "Done"])
        uploading = len([s for s in statuses if s.status == "Sedang Upload"])
        belum = len([s for s in statuses if s.status == "Belum Mulai"])

        last_log = db.query(UploadLog).filter(
            UploadLog.cycle_id == cycle.id
        ).order_by(UploadLog.uploaded_at.desc()).first()

        last_file = last_log.file_name if last_log else "-"
        started_at = cycle.started_at.strftime("%Y-%m-%d %H:%M:%S") if cycle.started_at else "-"
        last_updated = last_log.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if last_log and last_log.uploaded_at else "-"

        lead_time = "-"
        if cycle.started_at and last_log and last_log.uploaded_at:
            delta = last_log.uploaded_at - cycle.started_at
            total_seconds = int(delta.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            lead_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return {
            "cycle_name": cycle.cycle_name,
            "status": "RUNNING" if not cycle.ended_at else "SELESAI",
            "total": total,
            "done": done,
            "uploading": uploading,
            "belum": belum,
            "progress_pct": (done / total * 100) if total > 0 else 0,
            "current_file": last_file,
            "started_at": started_at,
            "last_updated": last_updated,
            "lead_time": lead_time,
        }
    except Exception:
        return None


# ============================================================
# TAB 1: OVERVIEW
# ============================================================

def render_overview_tab(df, df_sourcing, metrics):
    st.markdown("## 📊 Overview")

    # Upload cycle info
    cycle_info = get_upload_cycle_info()
    if cycle_info:
        st.markdown("### 📋 Status Compile Database FPTK")
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**Status:**")
            st.markdown(f"**Progress:**")
            st.markdown(f"**Current File:**")
            st.markdown(f"**Started At:**")
            st.markdown(f"**Last Updated:**")
            st.markdown(f"**Lead Time:**")
        with col2:
            st.markdown(f"{cycle_info['status']}")
            st.markdown(f"{cycle_info['progress_pct']:.0f}% ({cycle_info['done']}/{cycle_info['total']})")
            st.markdown(f"{cycle_info['current_file']}")
            st.markdown(f"{cycle_info['started_at']}")
            st.markdown(f"{cycle_info['last_updated']}")
            st.markdown(f"{cycle_info['lead_time']}")

    st.markdown("---")

    # Metric cards
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Total FPTK", f"{metrics['total']:,}")
    c2.metric("FPTK Diproses", f"{metrics['diproses']:,}")
    c3.metric("Closed", f"{metrics['closed']:,}")
    c4.metric("Open", f"{metrics['op']:,}")
    c5.metric("Cancel", f"{metrics['cancel']:,}")
    c6.metric("Fulfillment Rate", f"{metrics['fulfillment_rate']:.1f}%")
    c7.metric("Closed Sesuai SLA", f"{metrics['closed_sla_rate']:.1f}%")

    st.markdown("---")

    # MoM / WoW
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📈 MoM% (Month over Month)")
        this_month, mom_pct = calculate_mom(df)
        st.metric("FPTK Bulan Ini", f"{this_month:,}",
                  delta=f"{mom_pct:+.1f}%")
    with col2:
        st.markdown("### 📈 WoW% (Week over Week)")
        this_week, wow_pct = calculate_wow(df)
        st.metric("FPTK Minggu Ini", f"{this_week:,}",
                  delta=f"{wow_pct:+.1f}%")

    st.markdown("---")

    # Trend FPTK
    if not df.empty and 'fptk_date_real' in df.columns:
        df_trend = df.copy()
        df_trend['fptk_date_real'] = pd.to_datetime(df_trend['fptk_date_real'], errors='coerce')
        df_trend = df_trend.dropna(subset=['fptk_date_real'])
        if not df_trend.empty:
            df_trend['week'] = df_trend['fptk_date_real'].dt.strftime('%Y-W%V')
            trend = df_trend.groupby('week').size().reset_index(name='Jumlah')
            fig = px.line(trend, x='week', y='Jumlah',
                          title='📈 Trend FPTK per Minggu',
                          markers=True)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    # Distribusi Status
    if metrics['total'] > 0:
        col1, col2 = st.columns(2)
        with col1:
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig = px.pie(status_counts, values='Count', names='Status',
                         title='📊 Distribusi Status',
                         color='Status',
                         color_discrete_map={
                             'OP': '#2ecc71',
                             'Closed': '#3498db',
                             'Cancel': '#e74c3c'
                         })
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if 'detail_sla' in df.columns and df['detail_sla'].notna().any():
                detail_counts = df['detail_sla'].value_counts().reset_index()
                detail_counts.columns = ['Detail SLA', 'Count']
                fig = px.bar(detail_counts, x='Detail SLA', y='Count',
                             title='📊 Detail SLA Distribution',
                             text='Count')
                fig.update_layout(height=400, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)


# ============================================================
# TAB 2: GRAFIK MPP
# ============================================================

def render_grafik_mpp_tab(df):
    st.markdown("## 📈 Grafik MPP (W1 - W53)")

    st.markdown("""
    **Grafik mingguan akumulatif per kategori.** Kolom = Week 1 s/d Week 53.
    Baris = Jumlah FPTK Diterima, Diproses, Pemenuhan, Sisa, Cancel.
    """)

    st.markdown("---")

    # Section 1: Total keseluruhan
    st.markdown("### 📊 Total Keseluruhan")
    matrix = build_week_matrix(df)
    rows = build_grafik_mpp_row(matrix)

    df_total = pd.DataFrame(rows, columns=['Kategori'] + [f"W{w}" for w in WEEK_NUMBERS])
    st.dataframe(df_total, use_container_width=True, height=250)

    # Grafik line untuk total
    diterima_series = [matrix['diterima'][w] for w in WEEK_NUMBERS]
    closed_series = [matrix['closed'][w] for w in WEEK_NUMBERS]
    cancel_series = [matrix['cancel'][w] for w in WEEK_NUMBERS]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=diterima_series,
                              mode='lines+markers', name='Diterima',
                              line=dict(color='#3498db', width=3)))
    fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=closed_series,
                              mode='lines+markers', name='Closed',
                              line=dict(color='#2ecc71', width=3)))
    fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=cancel_series,
                              mode='lines+markers', name='Cancel',
                              line=dict(color='#e74c3c', width=3)))
    fig.update_layout(
        title='📈 Trend Mingguan Total FPTK',
        height=400,
        xaxis_title='Week',
        yaxis_title='Jumlah FPTK',
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Section 2: Per Kategori FPTK
    st.markdown("### 📊 Per Kategori FPTK")
    for kategori in FPTK_KATEGORI:
        with st.expander(f"📁 {kategori}", expanded=False):
            matrix_kat = build_category_week_matrix(df, 'filter_kategorisasi_fptk', kategori)
            rows_kat = build_grafik_mpp_row(matrix_kat)
            df_kat = pd.DataFrame(rows_kat, columns=['Kategori'] + [f"W{w}" for w in WEEK_NUMBERS])
            st.dataframe(df_kat, use_container_width=True, height=220)

            diterima_series = [matrix_kat['diterima'][w] for w in WEEK_NUMBERS]
            closed_series = [matrix_kat['closed'][w] for w in WEEK_NUMBERS]
            cancel_series = [matrix_kat['cancel'][w] for w in WEEK_NUMBERS]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=diterima_series,
                                      mode='lines+markers', name='Diterima',
                                      line=dict(color='#3498db', width=2)))
            fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=closed_series,
                                      mode='lines+markers', name='Closed',
                                      line=dict(color='#2ecc71', width=2)))
            fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=cancel_series,
                                      mode='lines+markers', name='Cancel',
                                      line=dict(color='#e74c3c', width=2)))
            fig.update_layout(
                title=f'📈 Trend Mingguan — {kategori}',
                height=350,
                xaxis_title='Week',
                yaxis_title='Jumlah FPTK',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Section 3: Per Direktorat
    st.markdown("### 📊 Per Direktorat")
    for direktorat in DIREKTORAT_KATEGORI:
        with st.expander(f"📁 {direktorat}", expanded=False):
            matrix_dir = build_category_week_matrix(df, 'direktorat', direktorat)
            rows_dir = build_grafik_mpp_row(matrix_dir)
            df_dir = pd.DataFrame(rows_dir, columns=['Kategori'] + [f"W{w}" for w in WEEK_NUMBERS])
            st.dataframe(df_dir, use_container_width=True, height=220)

            diterima_series = [matrix_dir['diterima'][w] for w in WEEK_NUMBERS]
            closed_series = [matrix_dir['closed'][w] for w in WEEK_NUMBERS]
            cancel_series = [matrix_dir['cancel'][w] for w in WEEK_NUMBERS]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=diterima_series,
                                      mode='lines+markers', name='Diterima',
                                      line=dict(color='#3498db', width=2)))
            fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=closed_series,
                                      mode='lines+markers', name='Closed',
                                      line=dict(color='#2ecc71', width=2)))
            fig.add_trace(go.Scatter(x=[f"W{w}" for w in WEEK_NUMBERS], y=cancel_series,
                                      mode='lines+markers', name='Cancel',
                                      line=dict(color='#e74c3c', width=2)))
            fig.update_layout(
                title=f'📈 Trend Mingguan — {direktorat}',
                height=350,
                xaxis_title='Week',
                yaxis_title='Jumlah FPTK',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# TAB 3: RECRUITER PERFORMANCE
# ============================================================

def render_recruiter_performance_tab(df):
    st.markdown("## 👥 Recruiter Performance")

    if df.empty or 'pic_recruiter' not in df.columns:
        st.info("Tidak ada data FPTK.")
        return

    recruiters = sorted(set([
        r for r in df['pic_recruiter'].dropna().unique() if r
    ]))

    # 1. Pemenuhan SDM by Numbers
    st.markdown("### 1️⃣ Pemenuhan SDM by Numbers")
    data = []
    for r in recruiters:
        sub = df[df['pic_recruiter'] == r]
        op = len(sub[sub['status'] == 'OP'])
        closed = len(sub[sub['status'] == 'Closed'])
        cancel = len(sub[sub['status'] == 'Cancel'])
        data.append({
            'Nama Recruiter': r,
            'Open': op,
            'Closed': closed,
            'Cancel': cancel,
            'Total': op + closed + cancel
        })
    df_num = pd.DataFrame(data)
    st.dataframe(df_num, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 2. Pemenuhan SDM by Percentage
    st.markdown("### 2️⃣ Pemenuhan SDM by Percentage")
    st.caption("Persentase berdasarkan FPTK yang diproses (OP & Closed)")
    data_pct = []
    for r in recruiters:
        sub = df[df['pic_recruiter'] == r]
        op = len(sub[sub['status'] == 'OP'])
        closed = len(sub[sub['status'] == 'Closed'])
        total = op + closed
        data_pct.append({
            'Nama Recruiter': r,
            'Open %': f"{(op/total*100):.1f}%" if total > 0 else "0%",
            'Closed %': f"{(closed/total*100):.1f}%" if total > 0 else "0%",
            'Total': total
        })
    st.dataframe(pd.DataFrame(data_pct), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 3. Position Closed per Recruiter per Level Jabatan
    st.markdown("### 3️⃣ Position Closed per Recruiter per Level Jabatan")
    level_options = ["1A", "1B", "1C", "2A", "2B", "2C", "3A", "3B", "3C", "4A", "4B"]
    rows_level = []
    for r in recruiters:
        sub = df[(df['pic_recruiter'] == r) & (df['status'] == 'Closed')]
        row = {'Nama Recruiter': r}
        total = 0
        for lvl in level_options:
            cnt = len(sub[sub['level_fptk'] == lvl])
            row[lvl] = cnt
            total += cnt
        row['Total'] = total
        rows_level.append(row)
    st.dataframe(pd.DataFrame(rows_level), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 4. Complexity Closed Position
    st.markdown("### 4️⃣ Complexity Closed Position (Distribution per Recruiter)")
    st.caption("Easy (1A–2A) · Moderate (2B–3A) · Hard (3B–4B)")
    rows_complex = []
    for r in recruiters:
        sub = df[(df['pic_recruiter'] == r) & (df['status'] == 'Closed')]
        easy = len(sub[sub['level_fptk'].isin(['1A', '1B', '1C', '2A'])])
        moderate = len(sub[sub['level_fptk'].isin(['2B', '2C', '3A'])])
        hard = len(sub[sub['level_fptk'].isin(['3B', '3C', '4A', '4B'])])
        total = easy + moderate + hard
        rows_complex.append({
            'Recruiter': r,
            'Total': total,
            'Easy': easy,
            '% Easy': f"{(easy/total*100):.1f}%" if total > 0 else "0%",
            'Moderate': moderate,
            '% Moderate': f"{(moderate/total*100):.1f}%" if total > 0 else "0%",
            'Hard': hard,
            '% Hard': f"{(hard/total*100):.1f}%" if total > 0 else "0%",
        })
    st.dataframe(pd.DataFrame(rows_complex), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 5. Pemenuhan SDM by SLA
    st.markdown("### 5️⃣ Pemenuhan SDM by SLA (Total Closed)")
    rows_sla = []
    for r in recruiters:
        sub = df[df['pic_recruiter'] == r]
        closed = sub[sub['status'] == 'Closed']
        total_closed = len(closed)
        sesuai = len(closed[closed['detail_sla'] == 'Closed Lulus SLA'])
        tidak_sesuai = len(closed[closed['detail_sla'] == 'Closed Tidak Lulus SLA'])
        op_lewat = len(sub[(sub['status'] == 'OP') & (sub['detail_sla'] == 'OP Tidak Lulus SLA')])
        rate = (sesuai / (total_closed + op_lewat) * 100) if (total_closed + op_lewat) > 0 else 0
        rows_sla.append({
            'Recruiter': r,
            'Total Closed': total_closed,
            'Sesuai SLA': sesuai,
            'Tidak Sesuai SLA': tidak_sesuai,
            'OP Lewat SLA': op_lewat,
            'Rate (%)': f"{rate:.1f}%"
        })
    st.dataframe(pd.DataFrame(rows_sla), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 6. Overview Status FPTK per Direktorat
    st.markdown("### 6️⃣ Overview Status FPTK per Direktorat")
    if 'direktorat' in df.columns:
        direktorat_list = sorted(set([
            d for d in df['direktorat'].dropna().unique() if d
        ]))
        rows_dir = []
        total_all = len(df)
        for d in direktorat_list:
            sub = df[df['direktorat'] == d]
            op = len(sub[sub['status'] == 'OP'])
            closed = len(sub[sub['status'] == 'Closed'])
            cancel = len(sub[sub['status'] == 'Cancel'])
            total = op + closed + cancel
            rows_dir.append({
                'Direktorat': d,
                'Open': op,
                '% Open': f"{(op/total*100):.1f}%" if total > 0 else "0%",
                'Closed': closed,
                '% Closed': f"{(closed/total*100):.1f}%" if total > 0 else "0%",
                'Cancel': cancel,
                '% Cancel': f"{(cancel/total*100):.1f}%" if total > 0 else "0%",
                'Total': total
            })
        st.dataframe(pd.DataFrame(rows_dir), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 7. Penyebaran FPTK per Recruiter per Direktorat
    st.markdown("### 7️⃣ Penyebaran FPTK per Recruiter per Direktorat")
    if 'direktorat' in df.columns:
        direktorat_list = sorted(set([
            d for d in df['direktorat'].dropna().unique() if d
        ]))
        rows_sebar = []
        for r in recruiters:
            sub = df[df['pic_recruiter'] == r]
            row = {'Nama Recruiter': r}
            total = 0
            for d in direktorat_list:
                cnt = len(sub[sub['direktorat'] == d])
                row[d] = cnt
                total += cnt
            row['Total'] = total
            rows_sebar.append(row)
        st.dataframe(pd.DataFrame(rows_sebar), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 8. Position Open per Recruiter per Level Jabatan
    st.markdown("### 8️⃣ Position Open per Recruiter per Level Jabatan")
    level_options = ["1A", "1B", "1C", "2A", "2B", "2C", "3A", "3B", "3C", "4A", "4B"]
    rows_open = []
    for r in recruiters:
        sub = df[(df['pic_recruiter'] == r) & (df['status'] == 'OP')]
        row = {'Nama Recruiter': r}
        total = 0
        for lvl in level_options:
            cnt = len(sub[sub['level_fptk'] == lvl])
            row[lvl] = cnt
            total += cnt
        row['Total'] = total
        rows_open.append(row)
    st.dataframe(pd.DataFrame(rows_open), use_container_width=True, hide_index=True)


# ============================================================
# TAB 4: FUNNEL SOURCING
# ============================================================

def render_funnel_sourcing_tab(df_sourcing):
    st.markdown("## 🔍 Funnel Sourcing")

    if df_sourcing.empty:
        st.info("Tidak ada data sourcing.")
        return

    funnel_data = []
    stages = [
        ("Sourcing HR", 'sourcing_hr'),
        ("Shortlist CV", 'shortlist_cv'),
        ("Psikotes", 'psikotes'),
        ("HR Interview", 'hr_interview'),
        ("Technical Test", 'technical_test_case_study'),
        ("Market Visit", 'market_visit'),
        ("User Interview", 'user_interview'),
        ("Panel Interview", 'panel_interview'),
        ("Reference Check", 'reference_check'),
        ("MCU", 'mcu'),
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

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Kandidat", len(df_sourcing))
    col2.metric("Lolos Offering", len(df_sourcing[df_sourcing['offering'] == 'V']) if 'offering' in df_sourcing else 0)
    col3.metric("Day 1", len(df_sourcing[df_sourcing['day1'] == 'V']) if 'day1' in df_sourcing else 0)

    if df_funnel['Count'].sum() > 0:
        fig = go.Figure(go.Funnel(
            y=df_funnel['Stage'],
            x=df_funnel['Count'],
            textposition="inside",
            textinfo="value+percent initial"
        ))
        fig.update_layout(title="Funnel Sourcing", height=500)
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# MAIN
# ============================================================

def show_dashboard():
    st.title("📊 Recruitment Analytic Dashboard")
    st.markdown("---")

    # Load filter options
    try:
        filter_opts = get_filter_options_from_db()
    except Exception:
        filter_opts = {
            "pic_options": [], "bu_options": [], "direktorat_options": [],
            "filter_kategorisasi_options": [], "divisi_options": [],
            "dept_options": [], "status_options": ["OP", "Closed", "Cancel"],
        }

    if not filter_opts.get("pic_options"):
        get_filter_options_from_db.clear()
        try:
            filter_opts = get_filter_options_from_db()
        except Exception:
            pass

    posisi_options = get_posisi_options()

    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔍 Filters")

        with st.expander("🐛 Debug Filter", expanded=False):
            st.caption(
                f"PIC: {len(filter_opts.get('pic_options', []))} | "
                f"BU: {len(filter_opts.get('bu_options', []))} | "
                f"Dir: {len(filter_opts.get('direktorat_options', []))} | "
                f"Kat: {len(filter_opts.get('filter_kategorisasi_options', []))} | "
                f"Posisi: {len(posisi_options)}"
            )

        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now() - timedelta(days=90))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())

        posisi_filter = st.selectbox("Posisi",
                                     ["Semua"] + posisi_options,
                                     key="dash_posisi_filter")

        pic_options = ["Semua"] + filter_opts.get("pic_options", [])
        pic_filter = st.selectbox("PIC Recruiter", pic_options, key="dash_pic")

        status_options = ["Semua"] + filter_opts.get("status_options", ["OP", "Closed", "Cancel"])
        status_filter = st.selectbox("Status", status_options, key="dash_status")

        bu_options = ["Semua"] + filter_opts.get("bu_options", [])
        bu_filter = st.selectbox("Business Unit", bu_options, key="dash_bu")

        dir_options = ["Semua"] + filter_opts.get("direktorat_options", [])
        dir_filter = st.selectbox("Direktorat", dir_options, key="dash_dir")

        divisi_options = ["Semua"] + filter_opts.get("divisi_options", [])
        divisi_filter = st.selectbox("Divisi", divisi_options, key="dash_div")

        dept_options = ["Semua"] + filter_opts.get("dept_options", [])
        dept_filter = st.selectbox("Department", dept_options, key="dash_dept")

        filter_kat_options = ["Semua"] + filter_opts.get("filter_kategorisasi_options", [])
        filter_kat = st.selectbox("Filter Kategorisasi", filter_kat_options, key="dash_kat")

        st.markdown("---")

        if st.button("🔄 Refresh Filter Options", use_container_width=True):
            get_filter_options_from_db.clear()
            get_posisi_options.clear()
            st.success("✅ Filter refreshed!")
            time.sleep(0.3)
            st.rerun()

    # Load data
    with st.spinner("📊 Memuat data..."):
        df = load_fptk_data(
            pic_filter=pic_filter,
            status_filter=status_filter,
            bu_filter=bu_filter,
            dir_filter=dir_filter,
            divisi_filter=divisi_filter,
            dept_filter=dept_filter,
            filter_kat=filter_kat,
            posisi_filter=posisi_filter,
            date_from=date_from,
            date_to=date_to
        )

        df_sourcing = load_sourcing_data(
            pic_filter=pic_filter,
            date_from=date_from,
            date_to=date_to
        )

    metrics = calculate_metrics(df)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview",
        "📈 Grafik MPP",
        "👥 Recruiter Performance",
        "🔍 Funnel Sourcing",
    ])

    with tab1:
        render_overview_tab(df, df_sourcing, metrics)

    with tab2:
        render_grafik_mpp_tab(df)

    with tab3:
        render_recruiter_performance_tab(df)

    with tab4:
        render_funnel_sourcing_tab(df_sourcing)
