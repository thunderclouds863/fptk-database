# pages/funnel_report.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.database import get_db
from core.models import DBSourcing, FPTK
from core.auth import get_current_user
from datetime import datetime, date
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import time


@st.cache_data(ttl=3600)
def get_funnel_pipeline_stages():
    return [
        {"field": "sourcing_freelance", "label": "Sourcing FL", "funnel_label": "Sourcing FL"},
        {"field": "sourcing_hr", "label": "Lolos Sourcing HR", "funnel_label": "Lolos Sourcing HR"},
        {"field": "shortlist_cv", "label": "Shortlisted User", "funnel_label": "Shortlisted User"},
        {"field": "psikotes", "label": "Lulus Psikotes", "funnel_label": "Lulus Psikotes"},
        {"field": "hr_interview", "label": "Lulus HR Interview", "funnel_label": "Lulus HR Interview"},
        {"field": "technical_test_case_study", "label": "Lulus Technical Case", "funnel_label": "Lulus Technical Case"},
        {"field": "market_visit", "label": "Lulus Market Visit", "funnel_label": "Lulus Market Visit"},
        {"field": "user_interview", "label": "Lulus User Interview", "funnel_label": "Lulus User Interview"},
        {"field": "panel_interview", "label": "Lulus Panel Interview", "funnel_label": "Lulus Panel Interview"},
        {"field": "reference_check", "label": "Reference Check", "funnel_label": "Reference Check"},
        {"field": "mcu", "label": "Lolos MCU", "funnel_label": "Lolos MCU"},
        {"field": "offering", "label": "Lolos Offering", "funnel_label": "Lolos Offering"},
        {"field": "day1", "label": "Day One", "funnel_label": "Day One"}
    ]


@st.cache_data(ttl=3600)
def get_funnel_status_options():
    return ["V", "X"]


EXCEL_HEADERS = [
    "FPTK Date Real",
    "Posisi",
    "Business Unit",
    "Direktorat",
    "Divisi",
    "Department",
    "Level FPTK",
    "Nama Rekruter",
    "Sourcing FL",
    "Lolos Sourcing HR",
    "Shortlisted User",
    "Lulus Psikotes",
    "HR Interview",
    "Technical Case",
    "Market Visit",
    "User Interview",
    "Panel Interview",
    "Reference Check",
    "Proses MCU",
    "Offering",
    "Day One",
]

EXCEL_HEADER_TO_INTERNAL = {
    "FPTK Date Real": "fptk_date_real",
    "Posisi": "posisi",
    "Business Unit": "business_unit",
    "Direktorat": "direktorat",
    "Divisi": "divisi",
    "Department": "department",
    "Level FPTK": "level_fptk",
    "Nama Rekruter": "pic_recruiter",
    "Sourcing FL": "Sourcing FL",
    "Lolos Sourcing HR": "Lolos Sourcing HR",
    "Shortlisted User": "Shortlisted User",
    "Lulus Psikotes": "Lulus Psikotes",
    "HR Interview": "Lulus HR Interview",
    "Technical Case": "Lulus Technical Case",
    "Market Visit": "Lulus Market Visit",
    "User Interview": "Lulus User Interview",
    "Panel Interview": "Lulus Panel Interview",
    "Reference Check": "Reference Check",
    "Proses MCU": "Lolos MCU",
    "Offering": "Lolos Offering",
    "Day One": "Day One",
}


def generate_funnel_excel(df: pd.DataFrame, sheet_name: str = "Sheet4") -> BytesIO:
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    for col_idx, header in enumerate(EXCEL_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = PatternFill(
            start_color="1F4E78",
            end_color="1F4E78",
            fill_type="solid"
        )
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )
        cell.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

    for row_idx, row in enumerate(df.to_dict('records'), start=2):
        for col_idx, excel_header in enumerate(EXCEL_HEADERS, start=1):
            internal_col = EXCEL_HEADER_TO_INTERNAL.get(excel_header, excel_header)
            value = row.get(internal_col, "")

            if pd.isna(value):
                value = ""

            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=False)
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            if excel_header == "FPTK Date Real":
                if isinstance(value, (datetime, date, pd.Timestamp)):
                    cell.number_format = 'YYYY-MM-DD HH:MM:SS'
                else:
                    cell.number_format = '@'

    column_widths = {
        'A': 20,
        'B': 40,
        'C': 32,
        'D': 22,
        'E': 22,
        'F': 22,
        'G': 10,
        'H': 14,
        'I': 12,
        'J': 18,
        'K': 18,
        'L': 16,
        'M': 16,
        'N': 16,
        'O': 14,
        'P': 16,
        'Q': 16,
        'R': 16,
        'S': 12,
        'T': 12,
        'U': 12,
    }
    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:U{len(df) + 1}"

    wb.save(output)
    output.seek(0)
    return output


def show_funnel_report():
    st.title("🔍 Funnel Report")
    st.markdown("Laporan pipeline sourcing per Kode Unik (agregasi)")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return

    with st.spinner("📋 Memuat data..."):
        pipeline_stages = get_funnel_pipeline_stages()
        status_options = get_funnel_status_options()

    with st.sidebar:
        st.markdown("### 🔍 Filter Funnel")

        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("Dari", datetime.now().replace(year=2020))
        with col2:
            date_to = st.date_input("Sampai", datetime.now())

        pic_options = ["Semua"] + [u[0] for u in db.query(DBSourcing.rekruter).distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_options)

        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()

    query = db.query(DBSourcing)

    if date_from:
        query = query.filter(DBSourcing.sourcing_date >= date_from)
    if date_to:
        query = query.filter(DBSourcing.sourcing_date <= date_to)
    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)

    df = pd.read_sql(query.statement, db.bind)
    total = len(df)

    if total == 0:
        st.info("Belum ada data sourcing dengan filter yang dipilih.")
        return

    fptk_df = pd.DataFrame()
    if 'kode_unik' in df.columns:
        kode_unik_list = df['kode_unik'].dropna().unique().tolist()
        if kode_unik_list:
            fptk_query = db.query(FPTK).filter(FPTK.kode_unik.in_(kode_unik_list))
            fptk_df = pd.read_sql(fptk_query.statement, db.bind)

    grouped = df.groupby('kode_unik')

    aggregated_data = []

    for kode_unik, group in grouped:
        row_data = {
            'kode_unik': kode_unik,
            'total_kandidat': len(group)
        }

        if not fptk_df.empty:
            fptk_row = fptk_df[fptk_df['kode_unik'] == kode_unik]
            if not fptk_row.empty:
                row_data['fptk_date_real'] = fptk_row.iloc[0].get('fptk_date_real', None)
                row_data['posisi'] = fptk_row.iloc[0].get('posisi', '-')
                row_data['business_unit'] = fptk_row.iloc[0].get('business_unit', '-')
                row_data['direktorat'] = fptk_row.iloc[0].get('direktorat', '-')
                row_data['divisi'] = fptk_row.iloc[0].get('divisi', '-')
                row_data['department'] = fptk_row.iloc[0].get('department', '-')
                row_data['level_fptk'] = fptk_row.iloc[0].get('level_fptk', '-')
                row_data['level_number'] = fptk_row.iloc[0].get('level_number', '-')
                row_data['category_fptk'] = fptk_row.iloc[0].get('category_fptk', '-')
                row_data['filter_kategorisasi_fptk'] = fptk_row.iloc[0].get('filter_kategorisasi_fptk', '-')
                row_data['pic_recruiter'] = fptk_row.iloc[0].get('pic_recruiter', '-')
            else:
                row_data['posisi'] = group.iloc[0].get('posisi', '-')
                row_data['pic_recruiter'] = group.iloc[0].get('rekruter', '-')
                for col in ['fptk_date_real', 'business_unit', 'direktorat', 'divisi', 'department',
                           'level_fptk', 'level_number', 'category_fptk', 'filter_kategorisasi_fptk']:
                    row_data[col] = '-'
        else:
            row_data['posisi'] = group.iloc[0].get('posisi', '-')
            row_data['pic_recruiter'] = group.iloc[0].get('rekruter', '-')
            for col in ['fptk_date_real', 'business_unit', 'direktorat', 'divisi', 'department',
                       'level_fptk', 'level_number', 'category_fptk', 'filter_kategorisasi_fptk']:
                row_data[col] = '-'

        for stage in pipeline_stages:
            field = stage["field"]
            if field in group.columns:
                count_v = len(group[group[field] == "V"])
            else:
                count_v = 0
            row_data[stage["label"]] = count_v

        aggregated_data.append(row_data)

    agg_df = pd.DataFrame(aggregated_data)

    st.markdown("### 📊 Total Kandidat per Tahap")

    funnel_totals = {}
    for stage in pipeline_stages:
        label = stage["label"]
        if label in agg_df.columns:
            funnel_totals[label] = agg_df[label].sum()
        else:
            funnel_totals[label] = 0

    funnel_totals["Total Kandidat"] = len(agg_df)

    stage_labels = list(funnel_totals.keys())
    stage_counts = list(funnel_totals.values())

    cols_per_row = 4
    for i in range(0, len(stage_labels), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < len(stage_labels):
                cols[j].metric(stage_labels[idx], stage_counts[idx])

    st.markdown("---")

    st.markdown("### 📈 Funnel Chart")

    funnel_data_chart = {k: v for k, v in funnel_totals.items() if v > 0 and k != "Total Kandidat"}

    if funnel_data_chart:
        df_funnel = pd.DataFrame(list(funnel_data_chart.items()), columns=["Stage", "Count"])

        colors = ['#2ecc71' if i % 2 == 0 else '#3498db' for i in range(len(df_funnel))]

        fig = go.Figure(go.Funnel(
            y=df_funnel['Stage'],
            x=df_funnel['Count'],
            textposition="inside",
            textinfo="value+percent initial",
            marker=dict(color=colors),
            connector=dict(line=dict(color="grey", width=2))
        ))
        fig.update_layout(
            height=500,
            title="Pipeline Sourcing Funnel (per Kode Unik)",
            font=dict(size=14)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Tidak ada data untuk funnel chart.")

    st.markdown("---")

    st.markdown("### 📋 Detail Data per Kode Unik")
    st.caption(f"Total: {len(agg_df)} Kode Unik unik")

    desired_order = [
        'fptk_date_real',
        'posisi',
        'business_unit',
        'direktorat',
        'divisi',
        'department',
        'level_fptk',
        'level_number',
        'category_fptk',
        'filter_kategorisasi_fptk',
        'pic_recruiter',
        'Sourcing FL',
        'Lolos Sourcing HR',
        'Shortlisted User',
        'Lulus Psikotes',
        'Lulus HR Interview',
        'Lulus Technical Case',
        'Lulus Market Visit',
        'Lulus User Interview',
        'Lulus Panel Interview',
        'Reference Check',
        'Lolos MCU',
        'Lolos Offering',
        'Day One'
    ]

    col_display_map = {
        'fptk_date_real': 'FPTK Date Real',
        'posisi': 'Posisi',
        'business_unit': 'Business Unit',
        'direktorat': 'Direktorat',
        'divisi': 'Divisi',
        'department': 'Department',
        'level_fptk': 'Level FPTK',
        'level_number': 'Level Number',
        'category_fptk': 'Category FPTK',
        'filter_kategorisasi_fptk': 'Filter Kategorisasi FPTK',
        'pic_recruiter': 'PIC Recruiter'
    }

    for stage in pipeline_stages:
        col_display_map[stage["label"]] = stage["label"]

    display_df = agg_df.copy()

    if 'fptk_date_real' in display_df.columns:
        display_df['fptk_date_real'] = display_df['fptk_date_real'].apply(
            lambda x: x.strftime('%d/%m/%y') if pd.notna(x) and isinstance(x, pd.Timestamp) else (x if x != '-' else '-')
        )

    for col in desired_order:
        if col not in display_df.columns:
            display_df[col] = 0 if col in [s["label"] for s in pipeline_stages] else '-'

    display_df = display_df[desired_order]

    display_df = display_df.rename(columns=col_display_map)

    st.dataframe(
        display_df,
        use_container_width=True,
        height=500
    )

    st.markdown("---")
    st.markdown("### 📥 Export Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📥 Export CSV", use_container_width=True, type="primary", key="btn_export_csv_funnel"):
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"funnel_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="dl_csv_funnel"
            )

    with col2:
        if st.button("📊 Export Excel (Format Funnel)", use_container_width=True, key="btn_export_excel_funnel"):
            try:
                with st.spinner("Generate Excel..."):
                    excel_buffer = generate_funnel_excel(agg_df, sheet_name="Sheet4")
                    st.session_state["funnel_excel_buffer"] = excel_buffer.getvalue()
                    st.session_state["funnel_excel_filename"] = (
                        f"funneling_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    )
                    st.success("✅ Excel berhasil di-generate! Klik download di bawah.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                with st.expander("Detail error"):
                    st.code(traceback.format_exc())

    with col3:
        if st.button("🔄 Refresh Data", use_container_width=True, key="btn_refresh_funnel"):
            st.cache_data.clear()
            st.rerun()

    if "funnel_excel_buffer" in st.session_state:
        st.download_button(
            label="⬇️ Download Excel Funnel (Format Persis)",
            data=st.session_state["funnel_excel_buffer"],
            file_name=st.session_state["funnel_excel_filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            key="dl_excel_funnel"
        )

    st.markdown("---")
    st.markdown("### 📊 Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_kode_unik = len(agg_df)
        st.metric("Total Kode Unik", total_kode_unik)

    with col2:
        total_kandidat = len(df)
        st.metric("Total Kandidat", total_kandidat)

    with col3:
        offering_count = agg_df['Lolos Offering'].sum() if 'Lolos Offering' in agg_df.columns else 0
        st.metric("Total Lolos Offering", offering_count)

    with col4:
        day1_count = agg_df['Day One'].sum() if 'Day One' in agg_df.columns else 0
        st.metric("Total Day One", day1_count)

    st.markdown("---")
    st.markdown("### 📈 Conversion Rate (per Kode Unik)")

    conversion_data = []
    prev_count = len(agg_df)

    for stage in pipeline_stages:
        label = stage["label"]
        count = agg_df[label].sum() if label in agg_df.columns else 0

        if prev_count > 0:
            rate = (count / prev_count) * 100
        else:
            rate = 0

        conversion_data.append({
            "Tahap": label,
            "Jumlah": count,
            "Conversion Rate": f"{rate:.1f}%"
        })

        prev_count = count if count > 0 else prev_count

    st.dataframe(pd.DataFrame(conversion_data), use_container_width=True, hide_index=True)
