# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.database import get_db
from core.models import FPTK, DBSourcing, User, UploadStatus, UploadCycle, MasterDropdown
from core.auth import get_current_user, is_admin
from core.utils import get_filter_options_from_db
from datetime import datetime, timedelta
from sqlalchemy import func
import time


# ============================================================
# CACHE: LOAD FPTK
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
    date_from=None,
    date_to=None,
):
    db = next(get_db())
    try:
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
        st.session_state["last_fptk_load"] = datetime.now()
        return df
    except Exception as e:
        st.error(f"Gagal load data FPTK: {str(e)}")
        return pd.DataFrame()
    finally:
        db.close()


# ============================================================
# CACHE: LOAD SOURCING
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_sourcing_data(pic_filter=None, date_from=None, date_to=None):
    db = next(get_db())
    try:
        query = db.query(DBSourcing)

        if pic_filter and pic_filter != "Semua":
            query = query.filter(DBSourcing.rekruter == pic_filter)
        if date_from:
            query = query.filter(DBSourcing.sourcing_date >= date_from)
        if date_to:
            query = query.filter(DBSourcing.sourcing_date <= date_to)

        df = pd.read_sql(query.statement, db.bind)
        st.session_state["last_sourcing_load"] = datetime.now()
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        db.close()


# ============================================================
# CACHE: METRICS
# ============================================================

@st.cache_data(ttl=300)
def calculate_metrics(df):
    if df.empty or "status" not in df:
        return {
            "total": 0, "op": 0, "closed": 0, "cancel": 0,
            "fulfillment_rate": 0, "closed_sla_rate": 0, "total_pic": 0,
        }

    total = len(df)
    op = len(df[df["status"] == "OP"])
    closed = len(df[df["status"] == "Closed"])
    cancel = len(df[df["status"] == "Cancel"])

    denominator = total - cancel
    fulfillment_rate = (closed / denominator * 100) if denominator > 0 else 0

    if "detail_sla" in df.columns:
        closed_df = df[df["status"] == "Closed"]
        closed_lulus = len(closed_df[closed_df["detail_sla"] == "Closed Lulus SLA"])
        closed_tidak = len(closed_df[closed_df["detail_sla"] == "Closed Tidak Lulus SLA"])
        total_closed_sla = closed_lulus + closed_tidak
        closed_sla_rate = (closed_lulus / total_closed_sla * 100) if total_closed_sla > 0 else 0
    else:
        closed_sla_rate = 0

    total_pic = len(df["pic_recruiter"].unique()) if "pic_recruiter" in df else 0

    return {
        "total": total, "op": op, "closed": closed, "cancel": cancel,
        "fulfillment_rate": fulfillment_rate,
        "closed_sla_rate": closed_sla_rate,
        "total_pic": total_pic,
    }


# ============================================================
# CACHE: UPLOAD CYCLE PROGRESS
# ============================================================

@st.cache_data(ttl=60)
def get_upload_cycle_progress():
    db = next(get_db())
    try:
        cycle = db.query(UploadCycle).filter(
            UploadCycle.ended_at.is_(None)
        ).order_by(UploadCycle.created_at.desc()).first()

        if not cycle:
            return pd.DataFrame()

        statuses = db.query(UploadStatus).filter(
            UploadStatus.cycle_id == cycle.id
        ).all()

        rows = []
        for s in statuses:
            u = db.query(User).filter(User.id == s.user_id).first()
            rows.append({
                "User": u.display_name if u else s.user_id,
                "PIC": u.pic_recruiter if u else "-",
                "Status": s.status,
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()
    finally:
        db.close()


# ============================================================
# CACHE: ADMIN CHECK
# ============================================================

@st.cache_data(ttl=300)
def check_admin_role():
    db = next(get_db())
    try:
        return is_admin(db)
    finally:
        db.close()


# ============================================================
# HELPER: ENRICH DATES
# ============================================================

def enrich_fptk_dates(df):
    if df.empty or "fptk_date_real" not in df.columns:
        return df
    df = df.copy()
    df["fptk_date_real"] = pd.to_datetime(df["fptk_date_real"], errors="coerce")
    df = df.dropna(subset=["fptk_date_real"])
    if df.empty:
        return df
    df["year"] = df["fptk_date_real"].dt.year
    df["month"] = df["fptk_date_real"].dt.to_period("M").astype(str)
    df["week"] = df["fptk_date_real"].dt.isocalendar().week.astype(int)
    df["year_week"] = (
        df["fptk_date_real"].dt.year.astype(str) + "-W" +
        df["fptk_date_real"].dt.isocalendar().week.astype(str).str.zfill(2)
    )
    df["month_year"] = df["fptk_date_real"].dt.strftime("%b %Y")
    df["quarter"] = df["fptk_date_real"].dt.to_period("Q").astype(str)
    return df


# ============================================================
# METRIC CARDS
# ============================================================

def render_metrics_cards(metrics):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total FPTK", f"{metrics['total']:,}")
    col2.metric("Open", f"{metrics['op']:,}")
    col3.metric("Closed", f"{metrics['closed']:,}")
    col4.metric("Cancel", f"{metrics['cancel']:,}")
    col5.metric("Fulfillment Rate", f"{metrics['fulfillment_rate']:.1f}%")
    col6.metric("Closed Sesuai SLA", f"{metrics['closed_sla_rate']:.1f}%")


# ============================================================
# CHART: MPP (CUMULATIVE / WEEK / MONTH / QUARTER)
# ============================================================

def render_mpp_chart(df, mode="Cumulative"):
    if df.empty:
        st.info("Tidak ada data untuk grafik MPP.")
        return

    df = enrich_fptk_dates(df)
    if df.empty:
        st.info("Tidak ada data tanggal FPTK.")
        return

    if mode == "Trend per Week":
        group_col = "year_week"
        title = "📈 Trend FPTK per Week"
    elif mode == "Trend per Month":
        group_col = "month_year"
        title = "📈 Trend FPTK per Month"
    elif mode == "Trend per Quarter":
        group_col = "quarter"
        title = "📈 Trend FPTK per Quarter"
    else:
        group_col = "year_week"
        title = "📊 MPP Cumulative (FPTK Diterima vs Closed)"

    incoming = df.groupby(group_col).size().reset_index(name="FPTK Diterima")
    closed_df = df[df["status"] == "Closed"]
    closed = closed_df.groupby(group_col).size().reset_index(name="FPTK Closed")
    cancel_df = df[df["status"] == "Cancel"]
    cancel = cancel_df.groupby(group_col).size().reset_index(name="FPTK Cancel")

    merged = incoming.merge(closed, on=group_col, how="outer").fillna(0)
    merged = merged.merge(cancel, on=group_col, how="outer").fillna(0)
    merged = merged.sort_values(group_col)

    if mode == "Cumulative":
        merged["FPTK Diterima"] = merged["FPTK Diterima"].cumsum()
        merged["FPTK Closed"] = merged["FPTK Closed"].cumsum()
        merged["FPTK Cancel"] = merged["FPTK Cancel"].cumsum()
        merged["Sisa FPTK"] = merged["FPTK Diterima"] - merged["FPTK Closed"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged[group_col], y=merged["FPTK Diterima"],
        mode="lines+markers", name="FPTK Diterima",
        line=dict(color="#3498db", width=3),
    ))
    fig.add_trace(go.Scatter(
        x=merged[group_col], y=merged["FPTK Closed"],
        mode="lines+markers", name="FPTK Closed",
        line=dict(color="#2ecc71", width=3),
    ))
    fig.add_trace(go.Scatter(
        x=merged[group_col], y=merged["FPTK Cancel"],
        mode="lines+markers", name="FPTK Cancel",
        line=dict(color="#e74c3c", width=2),
    ))

    if mode == "Cumulative":
        fig.add_trace(go.Scatter(
            x=merged[group_col], y=merged["Sisa FPTK"],
            mode="lines+markers", name="Sisa FPTK",
            line=dict(color="#e67e22", width=2, dash="dot"),
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Periode",
        yaxis_title="Jumlah FPTK",
        height=450,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: STATUS DISTRIBUTION
# ============================================================

def render_status_distribution(df):
    if df.empty or "status" not in df.columns:
        st.info("Tidak ada data status.")
        return
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    fig = px.pie(
        status_counts, values="Count", names="Status",
        title="🥧 Distribusi Status FPTK",
        color="Status",
        color_discrete_map={"OP": "#2ecc71", "Closed": "#3498db", "Cancel": "#e74c3c"},
        hole=0.4,
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: FULFILLMENT PER PIC
# ============================================================

def render_fulfillment_per_pic(df):
    if df.empty or "pic_recruiter" not in df.columns:
        st.info("Tidak ada data PIC.")
        return

    df_pic = df[df["status"].isin(["OP", "Closed"])]
    if df_pic.empty:
        st.info("Tidak ada data OP/Closed untuk PIC.")
        return

    agg = df_pic.groupby("pic_recruiter").agg(
        Open=("status", lambda s: (s == "OP").sum()),
        Closed=("status", lambda s: (s == "Closed").sum()),
    ).reset_index()
    agg["Total"] = agg["Open"] + agg["Closed"]
    agg["Fulfillment %"] = agg.apply(
        lambda r: (r["Closed"] / r["Total"] * 100) if r["Total"] > 0 else 0, axis=1
    )
    agg = agg.sort_values("Fulfillment %", ascending=False)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=agg["pic_recruiter"], y=agg["Open"], name="Open", marker_color="#2ecc71",
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=agg["pic_recruiter"], y=agg["Closed"], name="Closed", marker_color="#3498db",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=agg["pic_recruiter"], y=agg["Fulfillment %"], name="Fulfillment %",
        mode="lines+markers", line=dict(color="#e74c3c", width=3),
    ), secondary_y=True)
    fig.update_yaxes(title_text="Jumlah FPTK", secondary_y=False)
    fig.update_yaxes(title_text="Fulfillment %", secondary_y=True, range=[0, 100])
    fig.update_layout(
        title="📊 Pemenuhan SDM per Recruiter (OP & Closed)",
        height=450,
        barmode="group",
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: TOP PIC (USER PILIH METRIK)
# ============================================================

def render_top_pic_performance(df):
    if df.empty or "pic_recruiter" not in df.columns:
        st.info("Tidak ada data PIC.")
        return

    metric_options = {
        "Composite Score (Fair)": "composite",
        "Fulfillment Rate (%)": "fulfillment",
        "SLA Rate (%)": "sla",
        "Total Closed (Volume)": "closed",
        "Total FPTK (All)": "total",
    }

    selected_metric_label = st.radio(
        "🏆 Pilih metrik Top PIC:",
        list(metric_options.keys()),
        horizontal=True,
        key="top_pic_metric",
    )
    key = metric_options[selected_metric_label]

    rows = []
    for pic in df["pic_recruiter"].dropna().unique():
        sub = df[df["pic_recruiter"] == pic]

        op = len(sub[sub["status"] == "OP"])
        closed = len(sub[sub["status"] == "Closed"])
        cancel = len(sub[sub["status"] == "Cancel"])
        total = op + closed + cancel

        denom = op + closed
        fulfillment = (closed / denom * 100) if denom > 0 else 0

        if closed > 0 and "detail_sla" in sub.columns:
            closed_df = sub[sub["status"] == "Closed"]
            lulus = len(closed_df[closed_df["detail_sla"] == "Closed Lulus SLA"])
            sla_rate = (lulus / closed * 100) if closed > 0 else 0
        else:
            sla_rate = 0

        volume_score = min(closed, 50) / 50 * 100
        composite = (fulfillment * 0.4) + (sla_rate * 0.4) + (volume_score * 0.2)

        rows.append({
            "PIC": pic,
            "Open": op,
            "Closed": closed,
            "Cancel": cancel,
            "Total": total,
            "Fulfillment %": round(fulfillment, 1),
            "SLA %": round(sla_rate, 1),
            "Composite Score": round(composite, 1),
            "composite": composite,
            "fulfillment": fulfillment,
            "sla": sla_rate,
            "closed": closed,
            "total": total,
        })

    perf_df = pd.DataFrame(rows)

    if perf_df.empty:
        st.info("Tidak ada data untuk dianalisis.")
        return

    perf_df = perf_df.sort_values(key, ascending=False).head(10)

    fig = px.bar(
        perf_df,
        x="PIC",
        y=key,
        title=f"🏆 Top 10 PIC by {selected_metric_label}",
        color=key,
        color_continuous_scale="RdYlGn",
        text=key,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=450,
        xaxis_tickangle=-45,
        showlegend=False,
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Detail Metrik PIC", expanded=False):
        st.dataframe(
            perf_df[["PIC", "Open", "Closed", "Cancel", "Fulfillment %", "SLA %", "Composite Score"]],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# CHART: POSITION CLOSED PER LEVEL
# ============================================================

def render_position_closed_per_level(df):
    if df.empty or "level_fptk" not in df.columns:
        st.info("Tidak ada data level.")
        return

    closed = df[df["status"] == "Closed"]
    if closed.empty:
        st.info("Belum ada FPTK Closed.")
        return

    pivot = closed.pivot_table(
        index="pic_recruiter", columns="level_fptk",
        values="id", aggfunc="count", fill_value=0,
    ).reset_index()

    level_cols = [c for c in pivot.columns if c != "pic_recruiter"]
    for col in level_cols:
        pivot[col] = pivot[col].astype(int)

    fig = go.Figure()
    for col in level_cols:
        fig.add_trace(go.Bar(x=pivot["pic_recruiter"], y=pivot[col], name=col))

    fig.update_layout(
        title="📊 Position Closed per Recruiter per Level Jabatan",
        xaxis_title="Recruiter",
        yaxis_title="Jumlah Closed",
        barmode="stack",
        height=500,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: POSITION COMPLEXITY
# ============================================================

def render_position_complexity(df):
    if df.empty or "level_fptk" not in df.columns:
        st.info("Tidak ada data complexity.")
        return

    closed = df[df["status"] == "Closed"].copy()
    if closed.empty:
        st.info("Belum ada FPTK Closed.")
        return

    def classify(level):
        if not level:
            return "Unknown"
        try:
            num = int(str(level)[0])
        except Exception:
            return "Unknown"
        if num in [1, 2]:
            return "Easy"
        elif num == 3:
            return "Moderate"
        elif num >= 4:
            return "Hard"
        return "Unknown"

    closed["complexity"] = closed["level_fptk"].apply(classify)

    pivot = closed.pivot_table(
        index="pic_recruiter", columns="complexity",
        values="id", aggfunc="count", fill_value=0,
    ).reset_index()

    fig = go.Figure()
    for cat in ["Easy", "Moderate", "Hard"]:
        if cat in pivot.columns:
            fig.add_trace(go.Bar(x=pivot["pic_recruiter"], y=pivot[cat], name=cat))

    fig.update_layout(
        title="🎯 Complexity Closed Position: Distribution per Recruiter",
        xaxis_title="Recruiter",
        yaxis_title="Jumlah Closed",
        barmode="stack",
        height=450,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: SLA DISTRIBUTION
# ============================================================

def render_sla_distribution(df):
    if df.empty or "detail_sla" not in df.columns:
        st.info("Tidak ada data SLA.")
        return

    detail_counts = df["detail_sla"].value_counts().reset_index()
    detail_counts.columns = ["Detail SLA", "Count"]

    order = [
        "OP Belum Lewat SLA", "OP Tidak Lulus SLA",
        "Closed Lulus SLA", "Closed Tidak Lulus SLA", "Cancel FPTK",
    ]
    detail_counts = detail_counts[detail_counts["Detail SLA"].isin(order)]
    detail_counts["Detail SLA"] = pd.Categorical(
        detail_counts["Detail SLA"], categories=order, ordered=True
    )
    detail_counts = detail_counts.sort_values("Detail SLA")

    color_map = {
        "OP Belum Lewat SLA": "#2ecc71",
        "OP Tidak Lulus SLA": "#e74c3c",
        "Closed Lulus SLA": "#3498db",
        "Closed Tidak Lulus SLA": "#e67e22",
        "Cancel FPTK": "#95a5a6",
    }
    fig = px.bar(
        detail_counts, x="Detail SLA", y="Count",
        title="⏱️ Distribusi Detail SLA",
        color="Detail SLA", color_discrete_map=color_map, text="Count",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: SLA PER RECRUITER
# ============================================================

def render_sla_per_recruiter(df):
    if df.empty or "pic_recruiter" not in df.columns:
        st.info("Tidak ada data SLA per recruiter.")
        return

    closed = df[df["status"] == "Closed"]
    op = df[df["status"] == "OP"]

    rows = []
    recruiters = sorted(df["pic_recruiter"].dropna().unique())
    for r in recruiters:
        c_df = closed[closed["pic_recruiter"] == r]
        o_df = op[op["pic_recruiter"] == r]
        total_closed = len(c_df)
        sesuai = len(c_df[c_df["detail_sla"] == "Closed Lulus SLA"])
        tidak_sesuai = len(c_df[c_df["detail_sla"] == "Closed Tidak Lulus SLA"])
        op_lewat = len(o_df[o_df["detail_sla"] == "OP Tidak Lulus SLA"])
        rate = (sesuai / (total_closed + op_lewat) * 100) if (total_closed + op_lewat) > 0 else 0
        rows.append({
            "Recruiter": r,
            "Total Closed": total_closed,
            "Sesuai SLA": sesuai,
            "Tidak Sesuai SLA": tidak_sesuai,
            "OP Lewat SLA": op_lewat,
            "Rate (%)": round(rate, 1),
        })

    if not rows:
        st.info("Tidak ada data.")
        return

    sla_df = pd.DataFrame(rows).sort_values("Rate (%)", ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sla_df["Recruiter"], y=sla_df["Sesuai SLA"], name="Sesuai SLA", marker_color="#2ecc71",
    ))
    fig.add_trace(go.Bar(
        x=sla_df["Recruiter"], y=sla_df["Tidak Sesuai SLA"], name="Tidak Sesuai SLA", marker_color="#e74c3c",
    ))
    fig.add_trace(go.Bar(
        x=sla_df["Recruiter"], y=sla_df["OP Lewat SLA"], name="OP Lewat SLA", marker_color="#e67e22",
    ))
    fig.update_layout(
        title="⏱️ Pemenuhan SDM by SLA (Total Closed)",
        barmode="group",
        xaxis_title="Recruiter",
        yaxis_title="Jumlah",
        height=450,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: OVERVIEW PER DIREKTORAT
# ============================================================

def render_penyebaran_per_direktorat(df):
    if df.empty or "direktorat" not in df.columns:
        st.info("Tidak ada data direktorat.")
        return

    pivot = df.pivot_table(
        index="direktorat", columns="status",
        values="id", aggfunc="count", fill_value=0,
    ).reset_index()

    for col in ["OP", "Closed", "Cancel"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["Total"] = pivot["OP"] + pivot["Closed"] + pivot["Cancel"]
    pivot = pivot.sort_values("Total", ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=pivot["direktorat"], y=pivot["OP"], name="Open", marker_color="#2ecc71"))
    fig.add_trace(go.Bar(x=pivot["direktorat"], y=pivot["Closed"], name="Closed", marker_color="#3498db"))
    fig.add_trace(go.Bar(x=pivot["direktorat"], y=pivot["Cancel"], name="Cancel", marker_color="#e74c3c"))
    fig.update_layout(
        title="🏢 Overview Status FPTK per Direktorat",
        barmode="stack",
        xaxis_title="Direktorat",
        yaxis_title="Jumlah FPTK",
        height=500,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: LEVEL DISTRIBUTION
# ============================================================

def render_level_distribution(df):
    if df.empty or "level_fptk" not in df.columns:
        st.info("Tidak ada data level.")
        return

    counts = df["level_fptk"].value_counts().reset_index()
    counts.columns = ["Level", "Count"]
    counts = counts.sort_values("Level")

    fig = px.bar(
        counts, x="Level", y="Count",
        title="📊 Distribusi Level FPTK",
        color="Count", color_continuous_scale="Viridis",
        text="Count",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=400, showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: HEATMAP FPTK
# ============================================================

def render_heatmap_fptk(df):
    if df.empty or "fptk_date_real" not in df.columns:
        st.info("Tidak ada data heatmap.")
        return

    df = enrich_fptk_dates(df)
    if df.empty:
        return

    df["month_name"] = df["fptk_date_real"].dt.strftime("%Y-%m")
    df["day"] = df["fptk_date_real"].dt.day

    heatmap_data = df.groupby(["month_name", "day"]).size().reset_index(name="count")

    if heatmap_data.empty:
        st.info("Tidak ada data heatmap.")
        return

    fig = px.density_heatmap(
        heatmap_data, x="day", y="month_name", z="count",
        title="🔥 Persebaran FPTK (Calendar Heatmap)",
        color_continuous_scale="Blues",
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CHART: SOURCING FUNNEL
# ============================================================

def render_sourcing_funnel(df_sourcing):
    if df_sourcing.empty:
        st.info("Tidak ada data sourcing.")
        return

    stages = [
        ("Sourcing HR", "sourcing_hr"),
        ("Shortlist CV", "shortlist_cv"),
        ("Psikotes", "psikotes"),
        ("HR Interview", "hr_interview"),
        ("Technical Test", "technical_test_case_study"),
        ("Market Visit", "market_visit"),
        ("User Interview", "user_interview"),
        ("Panel Interview", "panel_interview"),
        ("Reference Check", "reference_check"),
        ("MCU", "mcu"),
        ("Offering", "offering"),
        ("Day 1", "day1"),
    ]

    data = []
    for label, col in stages:
        if col in df_sourcing.columns:
            count = df_sourcing[col].notna().sum()
        else:
            count = 0
        data.append({"Stage": label, "Count": count})

    df_funnel = pd.DataFrame(data)
    if df_funnel["Count"].sum() == 0:
        st.info("Belum ada data pipeline.")
        return

    fig = go.Figure(go.Funnel(
        y=df_funnel["Stage"], x=df_funnel["Count"],
        textposition="inside", textinfo="value+percent initial",
        marker=dict(color=px.colors.sequential.Blues_r[: len(df_funnel)]),
    ))
    fig.update_layout(title="🔍 Funnel Sourcing Pipeline", height=550)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# SOURCING SUMMARY
# ============================================================

def render_sourcing_summary(df_sourcing):
    if df_sourcing.empty:
        return

    total = len(df_sourcing)
    blacklisted = int(df_sourcing["is_blacklisted"].fillna(False).sum()) if "is_blacklisted" in df_sourcing.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Kandidat Sourcing", f"{total:,}")
    c2.metric("Kandidat Blacklist", f"{blacklisted:,}")
    c3.metric("Kandidat Aktif", f"{total - blacklisted:,}")


# ============================================================
# SOURCING BY SUMBER (DARI DATABASE)
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_sumber_sourcing_options():
    """Ambil sumber sourcing dari database (DBSourcing → fallback MasterDropdown)."""
    db = next(get_db())
    try:
        sources = set()

        rows = db.query(DBSourcing.sumber_sourcing).filter(
            DBSourcing.sumber_sourcing.isnot(None),
            DBSourcing.sumber_sourcing != ""
        ).distinct().all()
        for r in rows:
            if r[0]:
                sources.add(r[0].strip())

        if not sources:
            rows = db.query(MasterDropdown.sumber_sourcing).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.sumber_sourcing.isnot(None),
                MasterDropdown.sumber_sourcing != ""
            ).distinct().all()
            for r in rows:
                if r[0]:
                    sources.add(r[0].strip())

        return sorted(sources)
    except Exception:
        return []
    finally:
        db.close()


def render_sumber_sourcing_pie(df_sourcing):
    if df_sourcing.empty or "sumber_sourcing" not in df_sourcing.columns:
        st.info("Tidak ada data sumber sourcing.")
        return

    src = df_sourcing["sumber_sourcing"].dropna()
    src = src[src.astype(str).str.strip() != ""]

    if src.empty:
        st.info("Tidak ada data sumber sourcing.")
        return

    counts = src.value_counts().reset_index()
    counts.columns = ["Sumber", "Count"]

    fig = px.pie(
        counts,
        values="Count",
        names="Sumber",
        title="🌐 Distribusi Sumber Sourcing",
        hole=0.4,
    )
    fig.update_layout(height=550)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# UPLOAD CYCLE PROGRESS
# ============================================================

def render_upload_cycle_progress():
    df = get_upload_cycle_progress()
    if df.empty:
        st.info("Belum ada upload cycle aktif.")
        return

    done = len(df[df["Status"] == "Done"])
    total = len(df)
    st.progress(done / total if total > 0 else 0, text=f"{done}/{total} user selesai")

    summary = df["Status"].value_counts().reset_index()
    summary.columns = ["Status", "Count"]

    fig = px.pie(
        summary, values="Count", names="Status",
        title="Progress Upload Cycle (Admin)",
        hole=0.4,
        color="Status",
        color_discrete_map={
            "Done": "#2ecc71",
            "Sedang Upload": "#f39c12",
            "Belum Mulai": "#95a5a6",
        },
    )
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# MAIN DASHBOARD
# ============================================================

def show_dashboard():
    st.title("📊 Dashboard FPTK & Sourcing")
    st.markdown("Visualisasi lengkap recruitment analytics.")
    st.markdown("---")

    try:
        filter_opts = get_filter_options_from_db()
    except Exception:
        filter_opts = {
            "pic_options": [], "bu_options": [], "direktorat_options": [],
            "filter_kategorisasi_options": [], "divisi_options": [], "dept_options": [],
            "status_options": ["OP", "Closed", "Cancel"],
        }

    with st.sidebar:
        st.markdown("### 🔍 Filter Dashboard")

        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now() - timedelta(days=180))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())

        pic_filter = st.selectbox("PIC Recruiter", ["Semua"] + filter_opts.get("pic_options", []))
        status_filter = st.selectbox("Status", ["Semua"] + filter_opts.get("status_options", ["OP", "Closed", "Cancel"]))
        bu_filter = st.selectbox("Business Unit", ["Semua"] + filter_opts.get("bu_options", []))
        dir_filter = st.selectbox("Direktorat", ["Semua"] + filter_opts.get("direktorat_options", []))
        divisi_filter = st.selectbox("Divisi", ["Semua"] + filter_opts.get("divisi_options", []))
        dept_filter = st.selectbox("Department", ["Semua"] + filter_opts.get("dept_options", []))
        filter_kat = st.selectbox("Filter Kategorisasi", ["Semua"] + filter_opts.get("filter_kategorisasi_options", []))

        st.markdown("---")
        mpp_mode = st.selectbox(
            "Mode Grafik MPP",
            ["Cumulative", "Trend per Week", "Trend per Month", "Trend per Quarter"],
        )

        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
            st.cache_data.clear()
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
            date_to=date_to,
        )
        df_sourcing = load_sourcing_data(
            pic_filter=pic_filter,
            date_from=date_from,
            date_to=date_to,
        )

    admin = check_admin_role()

    metrics = calculate_metrics(df)
    render_metrics_cards(metrics)
    st.markdown("---")

    col1, col2 = st.columns([2, 1])
    with col1:
        render_mpp_chart(df, mode=mpp_mode)
    with col2:
        render_status_distribution(df)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        render_fulfillment_per_pic(df)
    with col2:
        render_top_pic_performance(df)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        render_position_closed_per_level(df)
    with col2:
        render_position_complexity(df)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        render_sla_distribution(df)
    with col2:
        render_sla_per_recruiter(df)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        render_level_distribution(df)
    with col2:
        render_heatmap_fptk(df)

    st.markdown("---")

    st.subheader("🔍 Sourcing Analytics")
    render_sourcing_summary(df_sourcing)
    st.markdown("")
    col1, col2 = st.columns([2, 1])
    with col1:
        render_sourcing_funnel(df_sourcing)
    with col2:
        render_sumber_sourcing_pie(df_sourcing)

    st.markdown("---")

    if dir_filter == "Semua" and bu_filter == "Semua":
        st.subheader("🏢 Overview per Direktorat")
        render_penyebaran_per_direktorat(df)
        st.markdown("---")

    if admin:
        st.subheader("🔄 Upload Cycle Progress (Admin)")
        render_upload_cycle_progress()
        st.markdown("---")

    last_fptk = st.session_state.get("last_fptk_load", datetime.now())
    last_sourcing = st.session_state.get("last_sourcing_load", datetime.now())
    st.caption(
        f"🕐 FPTK terakhir dimuat: {last_fptk.strftime('%H:%M:%S')} | "
        f"Sourcing: {last_sourcing.strftime('%H:%M:%S')}"
    )
