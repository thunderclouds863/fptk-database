import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.database import get_db
from core.models import FPTK, DBSourcing, User, UploadStatus, UploadCycle
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import traceback

def show_dashboard():
    st.title("📊 Dashboard FPTK & Sourcing")
    st.markdown("---")
    
    try:
        db = next(get_db())
    except Exception as e:
        st.error(f"❌ Gagal koneksi ke database: {str(e)}")
        return
        try:
        user = get_current_user(db)
    except Exception as e:
        st.error(f"❌ Gagal mendapatkan user: {str(e)}")
        return
    
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # SIDEBAR FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now() - timedelta(days=90))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())
        
        # PIC Filter
        try:
            pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        except:
            pic_options = ["Semua"]
        pic_filter = st.sidebar.selectbox("PIC Recruiter", pic_options)
        
        status_options = ["Semua", "OP", "Closed", "Cancel"]
        status_filter = st.sidebar.selectbox("Status", status_options)
        
        try:
            bu_options = ["Semua"] + [b[0] for b in db.query(FPTK.business_unit).distinct().all() if b[0]]
        except:
            bu_options = ["Semua"]
        bu_filter = st.sidebar.selectbox("Business Unit", bu_options)
        
        try:
            dir_options = ["Semua"] + [d[0] for d in db.query(FPTK.direktorat).distinct().all() if d[0]]
        except:
            dir_options = ["Semua"]
        dir_filter = st.sidebar.selectbox("Direktorat", dir_options)
        
        filter_kat_options = ["Semua", "CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]
        filter_kat = st.sidebar.selectbox("Filter Kategorisasi", filter_kat_options)
        
        st.markdown("---")
        
        # Export
        if st.button("📥 Export CSV", use_container_width=True):
            st.session_state.export_data = True

    # ============================================================
    # BUILD QUERY FPTK
    # ============================================================
    try:
        query = db.query(FPTK)
        
        if pic_filter != "Semua":
            query = query.filter(FPTK.pic_recruiter == pic_filter)
        if status_filter != "Semua":
            query = query.filter(FPTK.status == status_filter)
        if bu_filter != "Semua":
            query = query.filter(FPTK.business_unit == bu_filter)
        if dir_filter != "Semua":
            query = query.filter(FPTK.direktorat == dir_filter)
        if filter_kat != "Semua":
            query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)
        if date_from:
            query = query.filter(FPTK.fptk_date_real >= date_from)
        if date_to:
            query = query.filter(FPTK.fptk_date_real <= date_to)
        
        df = pd.read_sql(query.statement, db.bind)
    except Exception as e:
        st.error(f"❌ Gagal membaca data FPTK: {str(e)}")
        df = pd.DataFrame()
    
    total = len(df)
    
    # ============================================================
    # BUILD QUERY SOURCING
    # ============================================================
    try:
        sourcing_query = db.query(DBSourcing)
        if pic_filter != "Semua":
            sourcing_query = sourcing_query.filter(DBSourcing.rekruter == pic_filter)
        if date_from:
            sourcing_query = sourcing_query.filter(DBSourcing.sourcing_date >= date_from)
        if date_to:
            sourcing_query = sourcing_query.filter(DBSourcing.sourcing_date <= date_to)
        total_sourcing = sourcing_query.count()
    except:
        total_sourcing = 0
    
    # ============================================================
    # METRIC CARDS (6 cards)
    # ============================================================
    if not df.empty and 'status' in df:
        total = len(df)
        op = len(df[df['status'] == 'OP'])
        closed = len(df[df['status'] == 'Closed'])
        cancel = len(df[df['status'] == 'Cancel'])
        
        # Fulfillment Rate = Closed / (Total - Cancel)
        denominator = total - cancel
        if denominator > 0:
            fulfillment_rate = (closed / denominator) * 100
        else:
            fulfillment_rate = 0
        
        # Closed Sesuai SLA Rate
        # Hitung dari detail_sla column
        if 'detail_sla' in df.columns and not df.empty:
            closed_df = df[df['status'] == 'Closed']
            closed_lulus = len(closed_df[closed_df['detail_sla'] == 'Closed Lulus SLA'])
            closed_tidak = len(closed_df[closed_df['detail_sla'] == 'Closed Tidak Lulus SLA'])
            total_closed_sla = closed_lulus + closed_tidak
            if total_closed_sla > 0:
                closed_sla_rate = (closed_lulus / total_closed_sla) * 100
            else:
                closed_sla_rate = 0
        else:
            closed_sla_rate = 0
        
        # Total Sourcing
        total_sourcing = sourcing_query.count() if 'sourcing_query' in dir() else 0
        
        # PIC Active
        total_pic = len(df['pic_recruiter'].unique()) if 'pic_recruiter' in df else 0
    else:
        total = 0
        op = 0
        closed = 0
        cancel = 0
        fulfillment_rate = 0
        closed_sla_rate = 0
        total_sourcing = 0
        total_pic = 0
    
    # Display 6 metric cards
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total FPTK", f"{total:,}")
    c2.metric("OP", f"{op:,}")
    c3.metric("Closed", f"{closed:,}")
    c4.metric("Cancel", f"{cancel:,}")
    c5.metric("Fulfillment Rate", f"{fulfillment_rate:.1f}%")
    c6.metric("Closed Sesuai SLA", f"{closed_sla_rate:.1f}%")
    st.markdown("---")
    
    # ============================================================
    # CEK APAKAH ADA DATA
    # ============================================================
    if total == 0:
        st.info("📭 Belum ada data FPTK. Silakan upload file Excel terlebih dahulu melalui menu Upload & Compile.")
        st.stop()
    
    # ============================================================
    # ROW 1: LINE CHART + STATUS PIE
    # ============================================================
    try:
        c1, c2 = st.columns(2)
        
        with c1:
            if 'fptk_date_real' in df and df['fptk_date_real'].notna().any():
                df['date'] = pd.to_datetime(df['fptk_date_real'])
                trend = df.groupby(df['date'].dt.to_period('W')).size().reset_index()
                trend.columns = ['Minggu', 'Jumlah']
                trend['Minggu'] = trend['Minggu'].astype(str)
                fig = px.line(trend, x='Minggu', y='Jumlah', title='📈 Trend FPTK per Minggu', markers=True)
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data trend (kolom fptk_date_real kosong)")
        
        with c2:
            if 'status' in df and not df.empty:
                status_counts = df['status'].value_counts().reset_index()
                status_counts.columns = ['Status', 'Count']
                fig = px.pie(status_counts, values='Count', names='Status', title='📊 Distribusi Status',
                             color='Status', color_discrete_map={'OP': '#2ecc71', 'Closed': '#3498db', 'Cancel': '#e74c3c'})
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data status")
    except Exception as e:
        st.error(f"Error grafik ROW 1: {str(e)}")
        st.code(traceback.format_exc())
    
    # ============================================================
    # ROW 2: 3 CHARTS (Direktorat, BU, Level)
    # ============================================================
    try:
        c1, c2, c3 = st.columns(3)
        
        with c1:
            if 'direktorat' in df and df['direktorat'].notna().any():
                dir_counts = df['direktorat'].value_counts().reset_index()
                dir_counts.columns = ['Direktorat', 'Count']
                fig = px.pie(dir_counts, values='Count', names='Direktorat', title='🏢 Direktorat')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data Direktorat")
        
        with c2:
            if 'business_unit' in df and df['business_unit'].notna().any():
                bu_counts = df['business_unit'].value_counts().reset_index()
                bu_counts.columns = ['Business Unit', 'Count']
                fig = px.pie(bu_counts, values='Count', names='Business Unit', title='🏢 Business Unit')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data Business Unit")
        
        with c3:
            if 'level_fptk' in df and df['level_fptk'].notna().any():
                level_counts = df['level_fptk'].value_counts().reset_index()
                level_counts.columns = ['Level', 'Count']
                fig = px.bar(level_counts, x='Level', y='Count', title='📊 Level FPTK', color='Count')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data Level")
    except Exception as e:
        st.error(f"Error grafik ROW 2: {str(e)}")
    
    # ============================================================
    # ROW 3: BOXPLOT SLA + TOP PIC
    # ============================================================
    try:
        c1, c2 = st.columns(2)
        
        with c1:
            if 'jumlah_sla' in df and 'pic_recruiter' in df:
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
        
        with c2:
            if 'pic_recruiter' in df and not df.empty:
                pic_counts = df['pic_recruiter'].value_counts().reset_index()
                pic_counts.columns = ['PIC', 'Jumlah FPTK']
                pic_counts = pic_counts.head(10)
                fig = px.bar(pic_counts, x='PIC', y='Jumlah FPTK', title='🏆 Top 10 PIC Performance', color='Jumlah FPTK')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data PIC")
    except Exception as e:
        st.error(f"Error grafik ROW 3: {str(e)}")
    
    # ============================================================
    # ROW 4: FUNNEL SOURCING
    # ============================================================
    try:
        st.subheader("🔍 Funnel Sourcing")
        
        stages = [
            ("Sourcing HR", 'sourcing_hr'),
            ("Shortlist CV", 'shortlist_cv'),
            ("Psikotes", 'psikotes'),
            ("HR Interview", 'hr_interview'),
            ("User Interview", 'user_interview'),
            ("Offering", 'offering'),
            ("Day 1", 'day1')
        ]
        
        funnel_data = []
        for label, col in stages:
            try:
                if col in DBSourcing.__table__.columns:
                    count = sourcing_query.filter(getattr(DBSourcing, col).isnot(None)).count()
                    funnel_data.append({"Stage": label, "Count": count})
                else:
                    funnel_data.append({"Stage": label, "Count": 0})
            except:
                funnel_data.append({"Stage": label, "Count": 0})
        
        if funnel_data and any(d['Count'] > 0 for d in funnel_data):
            df_funnel = pd.DataFrame(funnel_data)
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
    except Exception as e:
        st.error(f"Error Funnel: {str(e)}")
    
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
                
                # Urutkan sesuai dengan yang diinginkan
                sla_order = [
                    "OP Belum Lewat SLA",
                    "OP Tidak Lulus SLA",
                    "Closed Lulus SLA",
                    "Closed Tidak Lulus SLA",
                    "Cancel FPTK"
                ]
                
                # Filter hanya yang ada di data
                sla_order_existing = [s for s in sla_order if s in detail_counts['Detail SLA'].values]
                detail_counts = detail_counts[detail_counts['Detail SLA'].isin(sla_order_existing)]
                
                if not detail_counts.empty:
                    # Warna untuk setiap kategori
                    color_map = {
                        "OP Belum Lewat SLA": "#2ecc71",      # Hijau
                        "OP Tidak Lulus SLA": "#e74c3c",       # Merah
                        "Closed Lulus SLA": "#3498db",         # Biru
                        "Closed Tidak Lulus SLA": "#e67e22",   # Orange
                        "Cancel FPTK": "#95a5a6"               # Abu-abu
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
                    
                    # Tampilkan juga tabel summary
                    st.dataframe(detail_counts, use_container_width=True, hide_index=True)
                    
                    # Hitung summary
                    lulus = detail_counts[detail_counts['Detail SLA'].isin(["OP Belum Lewat SLA", "Closed Lulus SLA"])]['Count'].sum()
                    tidak_lulus = detail_counts[detail_counts['Detail SLA'].isin(["OP Tidak Lulus SLA", "Closed Tidak Lulus SLA"])]['Count'].sum()
                    cancel = detail_counts[detail_counts['Detail SLA'] == "Cancel FPTK"]['Count'].sum()
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("✅ Lulus SLA", lulus)
                    col_b.metric("❌ Tidak Lulus", tidak_lulus)
                    col_c.metric("⏭️ Cancel", cancel)
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
    # ROW 6: UPLOAD CYCLE (ADMIN)
    # ============================================================
    if admin:
        try:
            st.markdown("---")
            st.subheader("🔄 Upload Cycle Progress (Admin)")
            
            cycle = db.query(UploadCycle).filter(UploadCycle.ended_at.is_(None)).order_by(UploadCycle.created_at.desc()).first()
            if cycle:
                statuses = db.query(UploadStatus).filter(UploadStatus.cycle_id == cycle.id).all()
                if statuses:
                    progress_data = []
                    for s in statuses:
                        u = db.query(User).filter(User.id == s.user_id).first()
                        progress_data.append({
                            "User": u.display_name if u else s.user_id,
                            "PIC": u.pic_recruiter if u else "-",
                            "Status": s.status,
                            "First Compile": s.first_compile_at.strftime("%d/%m/%Y") if s.first_compile_at else "-"
                        })
                    df_prog = pd.DataFrame(progress_data)
                    done = len(df_prog[df_prog['Status'] == 'Done'])
                    total_u = len(df_prog)
                    if total_u > 0:
                        st.progress(done / total_u, text=f"Progress: {done}/{total_u} user selesai")
                    st.dataframe(df_prog, use_container_width=True, height=200)
                else:
                    st.info("Belum ada status upload")
            else:
                st.info("Tidak ada cycle aktif")
        except Exception as e:
            st.error(f"Error Upload Cycle: {str(e)}")
    
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
                f"fptk_export_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
