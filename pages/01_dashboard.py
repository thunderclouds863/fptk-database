import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.database import get_db
from core.models import FPTK, DBSourcing, User, UploadStatus, UploadCycle, DBKodePosisi, Blacklist
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import io
import xlsxwriter

def export_excel_full(df_fptk, df_sourcing, df_kode_posisi, df_blacklist):
    """Export all data to Excel with multiple sheets matching the original format"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Blacklist Candidate
        if not df_blacklist.empty:
            df_blacklist.to_excel(writer, sheet_name='Blacklist Candidate', index=False)
        
        # Sheet 2: DB Kode Posisi
        if not df_kode_posisi.empty:
            df_kode_posisi.to_excel(writer, sheet_name='DB Kode Posisi', index=False)
        
        # Sheet 3: FPTK
        if not df_fptk.empty:
            df_fptk.to_excel(writer, sheet_name='FPTK', index=False)
        
        # Sheet 4: DB Sourcing
        if not df_sourcing.empty:
            df_sourcing.to_excel(writer, sheet_name='DB Sourcing', index=False)
        
        # Sheet 5: Grafik MPP (create summary)
        if not df_fptk.empty:
            grafik_mpp_data = create_grafik_mpp(df_fptk)
            grafik_mpp_data.to_excel(writer, sheet_name='Grafik MPP', index=False)
        
        # Sheet 6: Recruiter Performance
        if not df_fptk.empty:
            perf_data = create_recruiter_performance(df_fptk)
            perf_data.to_excel(writer, sheet_name='Recruiter Performance', index=False)
    
    return output.getvalue()

def create_grafik_mpp(df_fptk):
    """Create Grafik MPP summary from FPTK data"""
    if df_fptk.empty:
        return pd.DataFrame()
    
    # Convert date columns
    df_fptk['fptk_date_real'] = pd.to_datetime(df_fptk['fptk_date_real'])
    
    # Add week and month columns
    df_fptk['week_number'] = df_fptk['fptk_date_real'].dt.isocalendar().week
    df_fptk['month_name'] = df_fptk['fptk_date_real'].dt.strftime('%B %Y')
    df_fptk['year'] = df_fptk['fptk_date_real'].dt.year
    
    # Summary by week
    weekly_summary = df_fptk.groupby(['year', 'week_number']).agg({
        'id': 'count',
        'status': lambda x: (x == 'Closed').sum(),
        'status_cancel': lambda x: (x == 'Cancel').sum(),
    }).reset_index()
    weekly_summary.columns = ['Year', 'Week', 'Total_FPTK', 'Closed', 'Cancel']
    weekly_summary['Processed'] = weekly_summary['Total_FPTK'] - weekly_summary['Closed'] - weekly_summary['Cancel']
    
    # Add month info
    weekly_summary['Month'] = weekly_summary.apply(
        lambda row: f"Week {row['Week']}", axis=1
    )
    
    # Pivot for chart display
    result = pd.DataFrame()
    result['Minggu'] = weekly_summary.apply(
        lambda r: f"W{r['Week']}", axis=1
    )
    result['Jumlah FPTK Diterima'] = weekly_summary['Total_FPTK']
    result['Jumlah FPTK Diproses'] = weekly_summary['Processed']
    result['Pemenuhan (terima offer)'] = weekly_summary['Closed']
    result['Cancel'] = weekly_summary['Cancel']
    
    # Calculate percentages
    result['%Pemenuhan'] = result.apply(
        lambda r: r['Pemenuhan (terima offer)'] / r['Jumlah FPTK Diterima'] if r['Jumlah FPTK Diterima'] > 0 else 0,
        axis=1
    )
    result['%Proses'] = result.apply(
        lambda r: r['Jumlah FPTK Diproses'] / r['Jumlah FPTK Diterima'] if r['Jumlah FPTK Diterima'] > 0 else 0,
        axis=1
    )
    
    return result

def create_recruiter_performance(df_fptk):
    """Create Recruiter Performance summary"""
    if df_fptk.empty:
        return pd.DataFrame()
    
    # Aggregate by PIC Recruiter
    perf = df_fptk.groupby('pic_recruiter').agg({
        'id': 'count',
        'status': lambda x: (x == 'OP').sum(),
        'status_closed': lambda x: (x == 'Closed').sum(),
        'status_cancel': lambda x: (x == 'Cancel').sum(),
        'level_number': lambda x: len(x.unique()),
    }).reset_index()
    
    perf.columns = ['PIC Recruiter', 'Total', 'Open', 'Closed', 'Cancel', 'Unique_Levels']
    
    # Calculate rates
    perf['Close_Rate'] = perf.apply(
        lambda r: r['Closed'] / (r['Open'] + r['Closed']) if (r['Open'] + r['Closed']) > 0 else 0,
        axis=1
    )
    perf['Open_Rate'] = perf.apply(
        lambda r: r['Open'] / (r['Open'] + r['Closed']) if (r['Open'] + r['Closed']) > 0 else 0,
        axis=1
    )
    
    # SLA Compliance (if available)
    if 'detail_sla' in df_fptk.columns:
        sla_compliance = df_fptk.groupby('pic_recruiter')['detail_sla'].apply(
            lambda x: (x.str.contains('Lulus', case=False, na=False)).sum()
        ).reset_index()
        sla_compliance.columns = ['pic_recruiter', 'SLA_Lulus']
        
        perf = perf.merge(sla_compliance, left_on='PIC Recruiter', right_on='pic_recruiter', how='left')
        perf['SLA_Rate'] = perf.apply(
            lambda r: r['SLA_Lulus'] / r['Closed'] if r['Closed'] > 0 else 0,
            axis=1
        )
    
    return perf

def export_dashboard_csv(df, db, date_from, date_to):
    """Export current dashboard view as CSV with summary data"""
    if df.empty:
        st.warning("Tidak ada data untuk diekspor")
        return
    
    # Prepare summary data
    summary = pd.DataFrame({
        'Metric': ['Total FPTK', 'OP', 'Closed', 'Cancel', 'Date Range'],
        'Value': [
            len(df),
            len(df[df['status'] == 'OP']) if 'status' in df else 0,
            len(df[df['status'] == 'Closed']) if 'status' in df else 0,
            len(df[df['status'] == 'Cancel']) if 'status' in df else 0,
            f"{date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}"
        ]
    })
    
    # Create export file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary.to_excel(writer, sheet_name='Summary', index=False)
        df.to_excel(writer, sheet_name='Data', index=False)
        
        # Add charts summary if possible
        if 'status' in df.columns:
            status_dist = df['status'].value_counts().reset_index()
            status_dist.columns = ['Status', 'Count']
            status_dist.to_excel(writer, sheet_name='Status_Distribution', index=False)
        
        if 'direktorat' in df.columns and df['direktorat'].notna().any():
            dir_dist = df['direktorat'].value_counts().reset_index()
            dir_dist.columns = ['Direktorat', 'Count']
            dir_dist.to_excel(writer, sheet_name='Direktorat_Distribution', index=False)
    
    # Download
    st.download_button(
        "📥 Download Dashboard Export (Excel)",
        output.getvalue(),
        f"dashboard_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def export_full_excel(db, admin, date_from, date_to):
    """Export full database in original Excel format"""
    if not admin:
        st.warning("Only admin can export full database")
        return
    
    try:
        with st.spinner("Loading data..."):
            # Query all data
            fptk_data = pd.read_sql(db.query(FPTK).statement, db.bind)
            sourcing_data = pd.read_sql(db.query(DBSourcing).statement, db.bind)
            kode_posisi_data = pd.read_sql(db.query(DBKodePosisi).statement, db.bind)
            blacklist_data = pd.read_sql(db.query(Blacklist).statement, db.bind)
        
        with st.spinner("Creating Excel file..."):
            # Rename columns to match original format
            if not fptk_data.empty:
                fptk_data = fptk_data.rename(columns={
                    'kode_pic': 'Kode PIC',
                    'fptk_date_real': 'FPTK Date (Real)',
                    'kode_angka': 'Kode Angka',
                    'fptk_date_kode': 'FPTK Date (Kode)',
                    'kode_unik': 'Kode Unik',
                    'posisi': 'Posisi',
                    'business_unit': 'Business Unit',
                    'direktorat': 'Direktorat',
                    'divisi': 'Divisi',
                    'department': 'Department',
                    'level_fptk': 'Level FPTK',
                    'level_number': 'Level Number',
                    'alasan_permintaan_fptk': 'Alasan Permintaan FPTK',
                    'category_fptk': 'Category FPTK',
                    'pic_recruiter': 'PIC Recruiter',
                    'filter_kategorisasi_fptk': 'Filter Kategorisasi FPTK',
                    'vacancy': 'Vacancy',
                    'status': 'Status',
                    'week_fptk_date': 'Week FPTK Date (Kode)',
                    'month_fptk_date': 'Month FPTK Date',
                    'fptk_cancel_date': 'FPTK Cancel Date',
                    'week_cancel_date': 'Week Cancel Date',
                    'month_cancel_date': 'Month Cancel Date',
                    'offering_date': 'Offering Date',
                    'week_offering_date': 'Week Offering Date',
                    'month_offering': 'Month Offering',
                    'jumlah_sla': 'Jumlah SLA',
                    'deadline_sla': 'Deadline pemenuhan SLA',
                    'detail_sla': 'Detail SLA',
                    'keterangan_lulus_sla': 'Keterangan Lulus SLA',
                    'keterangan_tidak_lulus_sla': 'Keterangan Tidak Lulus SLA',
                    'keterangan_cancel': 'Keterangan Cancel [Kosong]',
                    'nama_kandidat': 'Nama Kandidat',
                    'estimasi_join': 'Estimasi Join',
                    'kebutuhan_laptop': 'Kebutuhan Laptop (V)',
                    'lokasi_onboarding': 'Lokasi Onboarding',
                    'tanggal_upload_web': 'Tanggal Upload ke Website',
                    'user_manager': 'User (Manager)',
                    'indirect_user': 'Indirect User',
                    'lokasi_kerja': 'Lokasi Kerja',
                    'lokasi_hr': 'Lokasi HR',
                    'status_karyawan': 'Status Karyawan',
                    'kode_bu': 'Kode BU',
                    'fptk_availability': 'FPTK Availability',
                    'remark': 'Remark',
                    'created_at': 'Created At',
                    'last_updated_at': 'Last Updated At',
                    'last_compile_action': 'Last Compile Action',
                    'source_file': 'Source File',
                })
            
            # Create Grafik MPP
            grafik_mpp = create_grafik_mpp(fptk_data)
            
            # Create Recruiter Performance
            recruiter_perf = create_recruiter_performance(fptk_data)
        
        with st.spinner("Exporting..."):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Blacklist Candidate
                if not blacklist_data.empty:
                    blacklist_data.to_excel(writer, sheet_name='Blacklist Candidate', index=False)
                else:
                    pd.DataFrame({'No': [], 'Last Update': [], 'Business Unit': [], 'Posisi': [], 'Lokasi': [], 
                                 'Nama Kandidat': [], 'Kategori': [], 'Alasan Tidak Proceed': [], 'PIC Rekruter': []}).to_excel(
                        writer, sheet_name='Blacklist Candidate', index=False
                    )
                
                # Sheet 2: DB Kode Posisi
                if not kode_posisi_data.empty:
                    kode_posisi_data.to_excel(writer, sheet_name='DB Kode Posisi', index=False)
                else:
                    pd.DataFrame({'KODE_ANGKA': [], 'POSISI_KEBUTUHAN_TA': [], 'LOKASI_ONBOARDING': [], 
                                 'BUSINESS UNIT': [], 'DIVISI_SESUAI_SO': [], 'DEPARTMENT': [], 'USER (MANAGER)': [],
                                 'INDIRECT USER': [], 'DIREKTORAT': [], 'YEAR': []}).to_excel(
                        writer, sheet_name='DB Kode Posisi', index=False
                    )
                
                # Sheet 3: FPTK
                if not fptk_data.empty:
                    fptk_data.to_excel(writer, sheet_name='FPTK', index=False)
                else:
                    pd.DataFrame({'Kode PIC': [], 'FPTK Date (Real)': [], 'Kode Angka': [], 'FPTK Date (Kode)': []}).to_excel(
                        writer, sheet_name='FPTK', index=False
                    )
                
                # Sheet 4: DB Sourcing
                if not sourcing_data.empty:
                    sourcing_data.to_excel(writer, sheet_name='DB Sourcing', index=False)
                else:
                    pd.DataFrame({'No': [], 'Kode Unik': [], 'Posisi': [], 'Model Rekrutmen': [], 
                                 'Rekruter': [], 'Sumber Sourcing': [], 'Nama': []}).to_excel(
                        writer, sheet_name='DB Sourcing', index=False
                    )
                
                # Sheet 5: Grafik MPP
                if not grafik_mpp.empty:
                    grafik_mpp.to_excel(writer, sheet_name='Grafik MPP', index=False)
                else:
                    pd.DataFrame({'PEMENUHAN SDM 2026': []}).to_excel(
                        writer, sheet_name='Grafik MPP', index=False
                    )
                
                # Sheet 6: Recruiter Performance
                if not recruiter_perf.empty:
                    recruiter_perf.to_excel(writer, sheet_name='Recruiter Performance', index=False)
                else:
                    pd.DataFrame({'Nama Recruiter': [], 'Open': [], 'Closed': [], 'Cancel': [], 'Total': []}).to_excel(
                        writer, sheet_name='Recruiter Performance', index=False
                    )
                
                # Format worksheets
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    # Auto-fit columns
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_length = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_length
        
        # Download
        st.download_button(
            "📥 Download Full Database Export (Excel)",
            output.getvalue(),
            f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.success("✅ Export completed successfully!")
        
    except Exception as e:
        st.error(f"Error exporting data: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

def show_dashboard():
    """Main dashboard function - with all charts and export enhancements"""
    st.title("📊 Dashboard FPTK & Sourcing")
    st.markdown("---")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # SIDEBAR FILTERS (LENGKAP)
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        
        # Timeline / Date Range
        col1, col2 = st.sidebar.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now() - timedelta(days=90))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())
        
        # PIC Filter
        pic_options = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        pic_filter = st.sidebar.selectbox("PIC Recruiter", pic_options)
        
        # Status Filter
        status_options = ["Semua", "OP", "Closed", "Cancel"]
        status_filter = st.sidebar.selectbox("Status", status_options)
        
        # BU Filter
        bu_options = ["Semua"] + [b[0] for b in db.query(FPTK.business_unit).distinct().all() if b[0]]
        bu_filter = st.sidebar.selectbox("Business Unit", bu_options)
        
        # Direktorat Filter
        dir_options = ["Semua"] + [d[0] for d in db.query(FPTK.direktorat).distinct().all() if d[0]]
        dir_filter = st.sidebar.selectbox("Direktorat", dir_options)
        
        # Level Filter
        level_options = ["Semua"] + [l[0] for l in db.query(FPTK.level_fptk).distinct().all() if l[0]]
        level_filter = st.sidebar.selectbox("Level FPTK", level_options)
        
        # Filter Kategorisasi
        filter_kat_options = ["Semua", "CLAP FGDP", "STO", "Level 1-2", "Level 3", "Level 4"]
        filter_kat = st.sidebar.selectbox("Filter Kategorisasi", filter_kat_options)
        
        st.markdown("---")
        
        # ============================================================
        # DYNAMIC FILTERS (USER BISA TAMBAH SENDIRI)
        # ============================================================
        st.markdown("### ✚ Add Custom Filter")
        
        available_columns = [
            "status", "business_unit", "direktorat", "divisi", "department",
            "level_fptk", "level_number", "filter_kategorisasi_fptk",
            "pic_recruiter", "kode_bu", "fptk_availability", "vacancy",
            "kode_unik", "posisi", "nama_kandidat"
        ]
        
        col1, col2, col3 = st.columns([2, 1.5, 1])
        with col1:
            filter_col = st.selectbox("Kolom", available_columns, key="filter_col")
        with col2:
            filter_op = st.selectbox("Operator", ["equals", "contains", ">", "<", "in"], key="filter_op")
        with col3:
            filter_val = st.text_input("Value", placeholder="nilai", key="filter_val")
        
        if st.button("➕ Tambah Filter", use_container_width=True):
            if filter_val:
                if "custom_filters" not in st.session_state:
                    st.session_state.custom_filters = []
                st.session_state.custom_filters.append({
                    "column": filter_col,
                    "operator": filter_op,
                    "value": filter_val
                })
                st.rerun()
        
        if "custom_filters" in st.session_state and st.session_state.custom_filters:
            st.markdown("**Filter Aktif:**")
            for i, f in enumerate(st.session_state.custom_filters):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.caption(f"{f['column']} {f['operator']} '{f['value']}'")
                with col2:
                    if st.button("✕", key=f"del_filter_{i}"):
                        st.session_state.custom_filters.pop(i)
                        st.rerun()
        
        if st.button("🗑️ Clear All Filters", use_container_width=True):
            if "custom_filters" in st.session_state:
                st.session_state.custom_filters = []
            st.rerun()
        
        st.markdown("---")
        
        # ============================================================
        # EXPORT SECTION (ENHANCED)
        # ============================================================
        st.markdown("### 📤 Export Options")
        
        export_type = st.selectbox(
            "Export Type",
            ["Dashboard Export (CSV)", "Full Database Export (Excel)", "Download Current View"],
            help="Dashboard Export: Export charts & metrics as CSV. Full Database: Export all sheets matching original Excel format."
        )
        
        if st.button("📥 Export", use_container_width=True, type="primary"):
            if export_type == "Dashboard Export (CSV)":
                # We need df here, but df is defined after filters
                st.session_state.export_dashboard = True
            elif export_type == "Full Database Export (Excel)":
                export_full_excel(db, admin, date_from, date_to)
            elif export_type == "Download Current View":
                st.session_state.export_data = True
        
        st.markdown("---")

    # ============================================================
    # BUILD QUERY WITH FILTERS
    # ============================================================
    query = db.query(FPTK)
    
    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)
    if status_filter != "Semua":
        query = query.filter(FPTK.status == status_filter)
    if bu_filter != "Semua":
        query = query.filter(FPTK.business_unit == bu_filter)
    if dir_filter != "Semua":
        query = query.filter(FPTK.direktorat == dir_filter)
    if level_filter != "Semua":
        query = query.filter(FPTK.level_fptk == level_filter)
    if filter_kat != "Semua":
        query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)
    if date_from:
        query = query.filter(FPTK.fptk_date_real >= date_from)
    if date_to:
        query = query.filter(FPTK.fptk_date_real <= date_to)
    
    if "custom_filters" in st.session_state:
        for f in st.session_state.custom_filters:
            col = getattr(FPTK, f["column"], None)
            if col:
                op = f["operator"]
                val = f["value"]
                if op == "equals":
                    query = query.filter(col == val)
                elif op == "contains":
                    query = query.filter(col.ilike(f"%{val}%"))
                elif op == ">":
                    try:
                        query = query.filter(col > float(val))
                    except:
                        pass
                elif op == "<":
                    try:
                        query = query.filter(col < float(val))
                    except:
                        pass
                elif op == "in":
                    values = [v.strip() for v in val.split(",")]
                    query = query.filter(col.in_(values))
    
    df = pd.read_sql(query.statement, db.bind)
    total = len(df)
    
    # Handle dashboard export after df is defined
    if st.session_state.get('export_dashboard', False):
        st.session_state.export_dashboard = False
        export_dashboard_csv(df, db, date_from, date_to)
    
    # Sourcing query
    sourcing_query = db.query(DBSourcing)
    if pic_filter != "Semua":
        sourcing_query = sourcing_query.filter(DBSourcing.rekruter == pic_filter)
    if date_from:
        sourcing_query = sourcing_query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        sourcing_query = sourcing_query.filter(DBSourcing.sourcing_date <= date_to)
    
    # ============================================================
    # METRIC CARDS (6 cards)
    # ============================================================
    op = len(df[df['status'] == 'OP']) if 'status' in df else 0
    closed = len(df[df['status'] == 'Closed']) if 'status' in df else 0
    cancel = len(df[df['status'] == 'Cancel']) if 'status' in df else 0
    
    total_sourcing = sourcing_query.count()
    total_pic = len(df['pic_recruiter'].unique()) if 'pic_recruiter' in df else 0
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total FPTK", f"{total:,}")
    col2.metric("OP", f"{op:,}")
    col3.metric("Closed", f"{closed:,}")
    col4.metric("Cancel", f"{cancel:,}")
    col5.metric("Total Sourcing", f"{total_sourcing:,}")
    col6.metric("PIC Active", f"{total_pic}")
    
    st.markdown("---")
    
    # ============================================================
    # ROW 1: LINE CHART + STATUS PIE
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        # LINE CHART: Trend FPTK per Minggu
        if total > 0 and 'fptk_date_real' in df:
            df['date'] = pd.to_datetime(df['fptk_date_real'])
            # Group by week
            trend = df.groupby(df['date'].dt.to_period('W')).size().reset_index()
            trend.columns = ['Minggu', 'Jumlah']
            trend['Minggu'] = trend['Minggu'].astype(str)
            
            fig = px.line(trend, x='Minggu', y='Jumlah', title='📈 Trend FPTK per Minggu', markers=True)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data trend")
    
    with col2:
        # PIE CHART: Status Distribution
        if total > 0:
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig = px.pie(status_counts, values='Count', names='Status', title='📊 Distribusi Status',
                         color='Status', color_discrete_map={'OP': '#2ecc71', 'Closed': '#3498db', 'Cancel': '#e74c3c'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data status")
    
    # ============================================================
    # ROW 2: 3 PIE/ DONUT CHARTS (Direktorat, BU, Level)
    # ============================================================
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Direktorat Distribution
        if total > 0 and 'direktorat' in df and df['direktorat'].notna().any():
            dir_counts = df['direktorat'].value_counts().reset_index()
            dir_counts.columns = ['Direktorat', 'Count']
            fig = px.pie(dir_counts, values='Count', names='Direktorat', title='🏢 Direktorat')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data")
    
    with col2:
        # BU Distribution
        if total > 0 and 'business_unit' in df and df['business_unit'].notna().any():
            bu_counts = df['business_unit'].value_counts().reset_index()
            bu_counts.columns = ['Business Unit', 'Count']
            fig = px.pie(bu_counts, values='Count', names='Business Unit', title='🏢 Business Unit')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data")
    
    with col3:
        # Level Distribution
        if total > 0 and 'level_fptk' in df and df['level_fptk'].notna().any():
            level_counts = df['level_fptk'].value_counts().reset_index()
            level_counts.columns = ['Level', 'Count']
            fig = px.bar(level_counts, x='Level', y='Count', title='📊 Level FPTK', color='Count')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data")
    
    # ============================================================
    # ROW 3: BOXPLOT SLA + TOP PIC
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        # BOXPLOT: SLA Distribution per PIC
        if total > 0 and 'jumlah_sla' in df and 'pic_recruiter' in df:
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
        # TOP 10 PIC Performance
        if total > 0 and 'pic_recruiter' in df:
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
        if col in DBSourcing.__table__.columns:
            count = sourcing_query.filter(getattr(DBSourcing, col).isnot(None)).count()
            funnel_data.append({"Stage": label, "Count": count})
        else:
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
    
    # ============================================================
    # ROW 5: SLA COMPLIANCE (FIXED) + DETAIL SLA DISTRIBUTION
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        # SLA Compliance - menggunakan detail_sla dari database
        st.subheader("✅ SLA Compliance")
        if total > 0 and 'detail_sla' in df and df['detail_sla'].notna().any():
            # Hitung compliance dari detail_sla
            detail_counts = df['detail_sla'].value_counts().reset_index()
            detail_counts.columns = ['Detail SLA', 'Count']
            
            # Kategorikan "Lulus" vs "Tidak Lulus"
            lulus_keywords = ["Lulus", "Belum Lewat"]
            lulus = detail_counts[detail_counts['Detail SLA'].str.contains('|'.join(lulus_keywords), case=False, na=False)]['Count'].sum()
            tidak_lulus = detail_counts[~detail_counts['Detail SLA'].str.contains('|'.join(lulus_keywords), case=False, na=False)]['Count'].sum()
            
            sla_data = pd.DataFrame([
                {"Status": "Lulus SLA", "Count": lulus},
                {"Status": "Tidak Lulus SLA", "Count": tidak_lulus}
            ])
            if lulus + tidak_lulus > 0:
                fig = px.pie(sla_data, values='Count', names='Status', title='SLA Compliance',
                             color='Status', color_discrete_map={'Lulus SLA': '#2ecc71', 'Tidak Lulus SLA': '#e74c3c'})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Belum ada data Detail SLA")
        else:
            st.info("Belum ada data Detail SLA. Silakan compile file terlebih dahulu.")
    
    with col2:
        # DISTRIBUSI DETAIL SLA
        st.subheader("📋 Detail SLA Distribution")
        if total > 0 and 'detail_sla' in df and df['detail_sla'].notna().any():
            detail_counts = df['detail_sla'].value_counts().reset_index()
            detail_counts.columns = ['Detail SLA', 'Count']
            fig = px.bar(detail_counts, x='Detail SLA', y='Count', title='Distribusi Detail SLA',
                         color='Detail SLA', text='Count')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data Detail SLA")
    
    # ============================================================
    # ROW 6: HEATMAP (Calendar)
    # ============================================================
    st.subheader("📅 Persebaran FPTK")
    if total > 0 and 'fptk_date_real' in df:
        df['date'] = pd.to_datetime(df['fptk_date_real'])
        df['month'] = df['date'].dt.strftime('%Y-%m')
        df['day'] = df['date'].dt.day
        heatmap_data = df.groupby(['month', 'day']).size().reset_index(name='count')
        if len(heatmap_data) > 0:
            fig = px.density_heatmap(heatmap_data, x='day', y='month', z='count',
                                     title='🔥 Persebaran FPTK (Calendar Heatmap)',
                                     color_continuous_scale='Blues')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # ============================================================
    # ROW 7: UPLOAD CYCLE PROGRESS (ADMIN ONLY)
    # ============================================================
    if admin:
        st.markdown("---")
        st.subheader("🔄 Upload Cycle Progress (Admin)")
        
        cycle = db.query(UploadCycle).filter(UploadCycle.ended_at.is_(None)).order_by(UploadCycle.created_at.desc()).first()
        if cycle:
            statuses = db.query(UploadStatus).filter(UploadStatus.cycle_id == cycle.id).all()
            if statuses:
                progress_data = []
                for s in statuses:
                    user_obj = db.query(User).filter(User.id == s.user_id).first()
                    progress_data.append({
                        "User": user_obj.display_name if user_obj else s.user_id,
                        "PIC": user_obj.pic_recruiter if user_obj else "-",
                        "Status": s.status,
                        "First Compile": s.first_compile_at.strftime("%d/%m/%Y") if s.first_compile_at else "-"
                    })
                df_progress = pd.DataFrame(progress_data)
                
                done = len(df_progress[df_progress['Status'] == 'Done'])
                total_user = len(df_progress)
                
                st.progress(done / total_user if total_user > 0 else 0, text=f"Progress: {done}/{total_user} user selesai")
                st.dataframe(df_progress, use_container_width=True, height=200)
            else:
                st.info("Belum ada status upload")
        else:
            st.info("Tidak ada cycle aktif")
    
    # ============================================================
    # EXPORT HANDLING
    # ============================================================
    if st.session_state.get('export_data', False):
        st.session_state.export_data = False
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download Data (CSV)",
            csv,
            f"fptk_export_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
