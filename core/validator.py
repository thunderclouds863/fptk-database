import pandas as pd
import re
from datetime import datetime
from core.utils import normalize_key, parse_date_dmy, safe_int

# ============================================================
# HEADER ALIAS MAPPING (SESUAI VBA)
# ============================================================
HEADER_ALIASES = {
    "Kode PIC": ["Kode PIC", "PIC Code", "Kode Recruiter"],
    "FPTK Date (Real)": ["FPTK Date (Real)", "FPTK Date Real", "Tanggal FPTK", "FPTK DATE REAL"],
    "Kode Angka": ["Kode Angka", "Kode", "Position Code", "KODE"],
    "FPTK Date (Kode)": ["FPTK Date (Kode)", "FPTK Date Kode", "FPTK Date", "FPTK Date (CODE)"],
    "Kode Unik": ["Kode Unik", "Unique Code", "KODE UNIK"],
    "Posisi": ["Posisi", "Position", "Nama Posisi", "POSISI"],
    "Business Unit": ["Business Unit", "PT/Business Unit", "PT / Business Unit", "BU", "BUSINESS UNIT"],
    "Direktorat": ["Direktorat", "Directorate", "DIREKTORAT"],
    "Divisi": ["Divisi", "Division", "Divisi (Sesuai SO)", "Division Chris", "DIVISI"],
    "Department": ["Department", "Departemen", "DEPARTMENT"],
    "Level FPTK": ["Level FPTK", "Level Posisi", "Level FPTK (Sesuai SO)", "LEVEL FPTK"],
    "Level Number": ["Level Number", "Level No", "Nomor Level", "LEVEL NUMBER"],
    "Alasan Permintaan FPTK": ["Alasan Permintaan FPTK", "Alasan FPTK", "Category", "Status FPTK", "ALASAN PERMINTAAN FPTK"],
    "Category FPTK": ["Category FPTK", "CATEGORY FPTK"],
    "PIC Recruiter": ["PIC Recruiter", "PIC Rekruter", "Recruiter", "PIC RECRUITER"],
    "Filter Kategorisasi FPTK": ["Filter Kategorisasi FPTK", "Filter Kategori FPTK", "Kategorisasi FPTK", "FILTER KATEGORISASI FPTK"],
    "Vacancy": ["Vacancy", "Jumlah Posisi", "Jumlah Vacancy"],
    "Status": ["Status", "Status Rekrutmen", "Status Vacancy"],
    "Offering Date": ["Offering Date", "Tanggal Offering", "OFFERING DATE"],
    "FPTK Cancel Date": ["FPTK Cancel Date", "Cancel Date", "FPTK CANCEL DATE"],
    "Nama Kandidat": ["Nama Kandidat", "Kandidat", "Candidate Name", "NAMA KANDIDAT"],
}

def find_header_column(df: pd.DataFrame, canonical: str) -> str:
    """Cari nama kolom di DataFrame berdasarkan alias mapping."""
    aliases = HEADER_ALIASES.get(canonical, [canonical])
    for col in df.columns:
        col_clean = str(col).strip()
        for alias in aliases:
            if col_clean.lower() == alias.lower():
                return col_clean
            # partial match (spasi diabaikan)
            if alias.lower().replace(" ", "") in col_clean.lower().replace(" ", ""):
                return col_clean
    return None

def get_column_value(row, canonical: str, default=None):
    """Ambil nilai dari row berdasarkan canonical header."""
    col = find_header_column(pd.DataFrame([row]), canonical)
    if col and col in row:
        return row[col]
    return default

def validate_fptk_file(df: pd.DataFrame, db, user_id: int, is_sto: bool = False):
    """
    Strict validation dengan alias header untuk FPTK.
    Returns: (validated_rows, errors)
    """
    errors = []
    validated_rows = []

    # Cek header wajib dengan alias
    required_canonical = [
        "Kode PIC", "FPTK Date (Real)", "Kode Unik", "Posisi",
        "Business Unit", "Direktorat", "Divisi", "Department",
        "Level FPTK", "Level Number", "Alasan Permintaan FPTK",
        "Category FPTK", "PIC Recruiter", "Vacancy", "Status"
    ]

    missing_headers = []
    for canon in required_canonical:
        if not find_header_column(df, canon):
            missing_headers.append(canon)
    if missing_headers:
        errors.append({
            "row": 0,
            "field": "HEADER",
            "message": f"Kolom tidak ditemukan: {', '.join(missing_headers)}"
        })
        return [], errors

    # Proses setiap row
    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (header=1)
        row_errors = []
        row_data = {}

        # Helper untuk ambil nilai dari row
        def get_val(canonical: str):
            col = find_header_column(df, canonical)
            if col and col in row:
                return row[col]
            return None

        # Kode PIC
        kode_pic = str(get_val("Kode PIC") or "").strip()
        if not kode_pic:
            row_errors.append({"row": row_num, "field": "Kode PIC", "message": "Wajib diisi"})
        row_data['kode_pic'] = kode_pic

        # FPTK Date Real
        fptk_date = parse_date_dmy(get_val("FPTK Date (Real)"))
        if not fptk_date:
            row_errors.append({"row": row_num, "field": "FPTK Date (Real)", "message": "Wajib diisi dan valid (dd/mm/yyyy)"})
        row_data['fptk_date_real'] = fptk_date

        # Kode Unik
        kode_unik = normalize_key(get_val("Kode Unik"))
        if not kode_unik:
            row_errors.append({"row": row_num, "field": "Kode Unik", "message": "Wajib diisi"})
        row_data['kode_unik'] = kode_unik

        # Posisi
        posisi = str(get_val("Posisi") or "").strip()
        if not posisi:
            row_errors.append({"row": row_num, "field": "Posisi", "message": "Wajib diisi"})
        row_data['posisi'] = posisi

        # Business Unit
        bu = str(get_val("Business Unit") or "").strip()
        if not bu:
            row_errors.append({"row": row_num, "field": "Business Unit", "message": "Wajib diisi"})
        row_data['business_unit'] = bu

        # Direktorat
        direktorat = str(get_val("Direktorat") or "").strip()
        if not direktorat:
            row_errors.append({"row": row_num, "field": "Direktorat", "message": "Wajib diisi"})
        row_data['direktorat'] = direktorat

        # Divisi
        divisi = str(get_val("Divisi") or "").strip()
        if not divisi:
            row_errors.append({"row": row_num, "field": "Divisi", "message": "Wajib diisi"})
        row_data['divisi'] = divisi

        # Department
        department = str(get_val("Department") or "").strip()
        if not department:
            row_errors.append({"row": row_num, "field": "Department", "message": "Wajib diisi"})
        row_data['department'] = department

        # Level FPTK
        level_fptk = str(get_val("Level FPTK") or "").strip()
        if not level_fptk:
            row_errors.append({"row": row_num, "field": "Level FPTK", "message": "Wajib diisi"})
        elif not re.match(r'^[0-9]+[A-Za-z]$', level_fptk):
            row_errors.append({"row": row_num, "field": "Level FPTK", "message": f"Format harus 1A/2B/3A (input: {level_fptk})"})
        row_data['level_fptk'] = level_fptk

        # Level Number
        level_num = safe_int(get_val("Level Number"))
        if level_num <= 0:
            row_errors.append({"row": row_num, "field": "Level Number", "message": "Wajib angka > 0"})
        row_data['level_number'] = level_num

        # Alasan
        alasan = str(get_val("Alasan Permintaan FPTK") or "").strip()
        if not alasan:
            row_errors.append({"row": row_num, "field": "Alasan Permintaan FPTK", "message": "Wajib diisi"})
        row_data['alasan_permintaan_fptk'] = alasan

        # Category FPTK
        category = str(get_val("Category FPTK") or "").strip()
        if not category:
            row_errors.append({"row": row_num, "field": "Category FPTK", "message": "Wajib diisi"})
        row_data['category_fptk'] = category

        # PIC Recruiter
        pic = str(get_val("PIC Recruiter") or "").strip()
        if not pic:
            row_errors.append({"row": row_num, "field": "PIC Recruiter", "message": "Wajib diisi"})
        row_data['pic_recruiter'] = pic

        # Vacancy
        vacancy = safe_int(get_val("Vacancy"))
        if vacancy <= 0:
            row_errors.append({"row": row_num, "field": "Vacancy", "message": "Harus angka > 0"})
        row_data['vacancy'] = vacancy

        # Status
        status = str(get_val("Status") or "").strip()
        if not status:
            row_errors.append({"row": row_num, "field": "Status", "message": "Wajib diisi"})
        elif status not in ["OP", "Closed", "Cancel"]:
            row_errors.append({"row": row_num, "field": "Status", "message": f"Hanya OP/Closed/Cancel (input: {status})"})
        row_data['status'] = status

        # Closed → Offering Date
        if status == "Closed":
            offering = parse_date_dmy(get_val("Offering Date"))
            if not offering:
                row_errors.append({"row": row_num, "field": "Offering Date", "message": "Wajib diisi jika Status = Closed"})
            row_data['offering_date'] = offering

        # Cancel → FPTK Cancel Date
        if status == "Cancel":
            cancel = parse_date_dmy(get_val("FPTK Cancel Date"))
            if not cancel:
                row_errors.append({"row": row_num, "field": "FPTK Cancel Date", "message": "Wajib diisi jika Status = Cancel"})
            row_data['fptk_cancel_date'] = cancel

        # Jika ada error di row ini, skip row
        if row_errors:
            errors.extend(row_errors)
            continue

        validated_rows.append(row_data)

    return validated_rows, errors


# ============================================================
# VALIDASI DB SOURCING
# ============================================================
SOURCING_HEADER_ALIASES = {
    "Sourcing Date": ["Sourcing Date", "Tanggal Sourcing", "Tanggal Input"],
    "Kode Unik (copy value dari FPTK)": ["Kode Unik (copy value dari FPTK)", "Kode Unik", "Unique Code"],
    "Posisi": ["Posisi", "Position", "Nama Posisi"],
    "Nama": ["Nama", "Nama Kandidat", "Candidate Name"],
}

def find_sourcing_header_column(df: pd.DataFrame, canonical: str) -> str:
    """Cari nama kolom di DataFrame berdasarkan alias mapping untuk sourcing."""
    aliases = SOURCING_HEADER_ALIASES.get(canonical, [canonical])
    for col in df.columns:
        col_clean = str(col).strip()
        for alias in aliases:
            if col_clean.lower() == alias.lower():
                return col_clean
            # partial match
            if alias.lower().replace(" ", "") in col_clean.lower().replace(" ", ""):
                return col_clean
    return None

def validate_db_sourcing_rows(df: pd.DataFrame):
    """
    Validasi DB Sourcing: Sourcing Date mandatory.
    Returns: (valid_rows, errors)
    """
    errors = []
    valid_rows = []

    # Cek header Sourcing Date
    src_date_col = find_sourcing_header_column(df, "Sourcing Date")
    if not src_date_col:
        errors.append({
            "row": 0,
            "field": "HEADER",
            "message": "Kolom Sourcing Date tidak ditemukan"
        })
        return [], errors

    # Cek apakah ada data
    if df.empty:
        return [], errors

    for idx, row in df.iterrows():
        row_num = idx + 2
        row_errors = []

        # Sourcing Date
        raw_date = row.get(src_date_col)
        sourcing_date = parse_date_dmy(raw_date)
        if not sourcing_date:
            row_errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "message": "Wajib diisi dan valid (dd/mm/yyyy)"
            })

        # Jika error, skip row
        if row_errors:
            errors.extend(row_errors)
            continue

        # Simpan data valid
        row_data = row.to_dict()
        row_data['sourcing_date'] = sourcing_date
        valid_rows.append(row_data)

    return valid_rows, errors