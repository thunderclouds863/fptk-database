# pages/export_data.py
"""Admin-only full database export (previously shown at the bottom of every page for all roles)."""
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from core.auth import is_admin
from core.database import SessionLocal

SHEET_OPTIONS = [
    "Blacklist Candidate", "DB Kode Posisi", "FPTK", "DB Sourcing",
    "Grafik MPP", "Recruiter Performance", "Master Dropdown", "Evidence",
]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def show_export_data():
    db = SessionLocal()
    try:
        if not is_admin(db):
            st.error("Halaman ini hanya untuk Admin.")
            return

        st.title("Export Data")
        st.caption("File berisi data pribadi kandidat. Simpan dan bagikan sesuai kebijakan perusahaan.")

        st.subheader("Seluruh database")
        st.write("Satu workbook Excel, satu sheet per tabel.")
        if st.button("Siapkan file Excel", type="primary", key="export_all"):
            with st.spinner("Menyiapkan file..."):
                from core.export_excel import export_database_to_excel
                st.session_state.export_all_bytes = export_database_to_excel(db).getvalue()
                st.session_state.export_all_name = f"fptk_export_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        if st.session_state.get("export_all_bytes"):
            st.download_button("Unduh " + st.session_state.export_all_name,
                               data=st.session_state.export_all_bytes,
                               file_name=st.session_state.export_all_name,
                               mime=XLSX_MIME, icon=":material/download:")

        st.divider()
        st.subheader("Satu sheet")
        selected = st.selectbox("Sheet", SHEET_OPTIONS)
        if st.button("Siapkan sheet", key="export_one"):
            with st.spinner(f"Menyiapkan {selected}..."):
                from core.export_excel import export_single_sheet
                df = export_single_sheet(db, selected)
                out = BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name=selected[:31], index=False)
                st.session_state.export_one = (selected, out.getvalue())
        if st.session_state.get("export_one"):
            name, data = st.session_state.export_one
            st.download_button(f"Unduh {name}.xlsx", data=data, file_name=f"{name}.xlsx",
                               mime=XLSX_MIME, icon=":material/download:")
    finally:
        db.close()
