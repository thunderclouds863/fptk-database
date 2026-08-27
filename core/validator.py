# core/validator.py

import re
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict, Any
from core.utils import parse_date_dmy, safe_int, normalize_key


def validate_fptk_file(
    df: pd.DataFrame, 
    db, 
    user_id: int, 
    is_sto: bool = False
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file FPTK dengan error detail per row
    
    Returns:
        (is_valid, errors): 
            - is_valid: True jika semua data valid
            - errors: List error detail dengan format:
                {
                    "row": int,
                    "field": str,
                    "value": Any,
                    "error": str,
                    "expected": str (opsional),
                    "example": str (opsional)
                }
    """
    errors = []
    
    if df.empty:
        errors.append({
            "row": 0,
            "field": "file",
            "value": "",
            "error": "File kosong, tidak ada data yang ditemukan",
            "expected": "Minimal 1 baris data FPTK"
        })
        return False, errors
    
    # ============================================================
    # REQUIRED COLUMNS MAPPING
    # ============================================================
    required_columns = {
        "kode_unik": ["Kode Unik", "KodeUNIK"],
        "posisi": ["Posisi"],
        "kode_pic": ["Kode PIC"],
        "fptk_date_real": ["FPTK Date (Real)"],
        "fptk_date_kode": ["FPTK Date (Kode)"],
        "kode_angka": ["Kode Angka"],
        "business_unit": ["Business Unit", "PT / Business Unit"],
        "direktorat": ["Direktorat"],
        "divisi": ["Divisi"],
        "department": ["Department"],
        "level_fptk": ["Level FPTK"],
        "level_number": ["Level Number"],
        "alasan_permintaan_fptk": ["Alasan Permintaan FPTK"],
        "category_fptk": ["Category FPTK"],
        "pic_recruiter": ["PIC Recruiter"],
        "filter_kategorisasi_fptk": ["Filter Kategorisasi FPTK"],
        "vacancy": ["Vacancy"],
        "status": ["Status"],
        "week_fptk_date": ["Week FPTK Date (Kode)", "Week FPTK Date"],
        "month_fptk_date": ["Month FPTK Date"],
    }
    
    optional_columns = {
        "fptk_cancel_date": ["FPTK Cancel Date"],
        "week_cancel_date": ["Week Cancel Date"],
        "month_cancel_date": ["Month Cancel Date"],
        "offering_date": ["Offering Date"],
        "week_offering_date": ["Week Offering Date"],
        "month_offering": ["Month Offering"],
        "jumlah_sla": ["Jumlah SLA"],
        "deadline_sla": ["Deadline pemenuhan SLA"],
        "detail_sla": ["Detail SLA"],
        "keterangan_lulus_sla": ["Keterangan Lulus SLA"],
        "keterangan_tidak_lulus_sla": ["Keterangan Tidak Lulus SLA"],
        "keterangan_cancel": ["Keterangan Cancel"],
        "nama_kandidat": ["Nama Kandidat"],
        "estimasi_join": ["Estimasi Join"],
        "kebutuhan_laptop": ["Kebutuhan Laptop (V)"],
        "lokasi_onboarding": ["Lokasi Onboarding"],
        "tanggal_upload_web": ["Tanggal Upload ke Website"],
        "user_manager": ["User (Manager)"],
        "indirect_user": ["Indirect User"],
        "lokasi_kerja": ["Lokasi Kerja"],
        "lokasi_hr": ["Lokasi HR"],
        "status_karyawan": ["Status Karyawan"],
        "kode_bu": ["Kode BU"],
        "fptk_availability": ["FPTK Availability"],
        "remark": ["Remark"],
        "source_file": ["Source File"],
        "is_sto": ["is_sto"],
    }
    
    # ============================================================
    # CHECK COLUMNS EXIST
    # ============================================================
    df_cols = [normalize_key(c) for c in df.columns]
    df_cols_original = list(df.columns)
    
    missing_columns = []
    for col_key, possible_names in required_columns.items():
        found = False
        for name in possible_names:
            if normalize_key(name) in df_cols:
                found = True
                break
        if not found:
            missing_columns.append({
                "field": col_key,
                "expected": possible_names[0],
                "possible": possible_names,
                "error": f"Kolom '{possible_names[0]}' tidak ditemukan"
            })
    
    if missing_columns:
        for miss in missing_columns:
            errors.append({
                "row": 0,
                "field": miss["field"],
                "value": "",
                "error": f"Kolom '{miss['expected']}' tidak ditemukan di file. Pastikan file memiliki kolom: {', '.join(miss['possible'])}",
                "expected": "Kolom header harus sesuai dengan template",
                "example": f"Kolom yang ditemukan: {', '.join(df_cols_original[:10])}..."
            })
        return False, errors
    
    # ============================================================
    # VALIDATE EACH ROW
    # ============================================================
    date_format_example = "DD/MM/YYYY (contoh: 15/08/2026 atau 15-08-2026)"
    
    for idx, row in df.iterrows():
        row_num = idx + 2  # +1 karena header, +1 karena index 0
        
        # ============================================================
        # 1. VALIDATE KODE UNIK
        # ============================================================
        kode_unik = row.get("Kode Unik") or row.get("KodeUNIK")
        if pd.isna(kode_unik) or str(kode_unik).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": kode_unik,
                "error": "Kode Unik tidak boleh kosong",
                "expected": "Format: [Kode PIC][4 huruf posisi][tanggal DDMMYY]",
                "example": "CORPOmeSales101024"
            })
        else:
            # Cek duplikat
            existing = db.query(FPTK).filter(FPTK.kode_unik == str(kode_unik)).first()
            if existing:
                errors.append({
                    "row": row_num,
                    "field": "Kode Unik",
                    "value": kode_unik,
                    "error": f"Kode Unik '{kode_unik}' sudah ada di database",
                    "expected": "Kode Unik harus unik",
                    "example": "Gunakan kode unik yang berbeda"
                })
        
        # ============================================================
        # 2. VALIDATE POSISI
        # ============================================================
        posisi = row.get("Posisi")
        if pd.isna(posisi) or str(posisi).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Posisi",
                "value": posisi,
                "error": "Posisi tidak boleh kosong",
                "expected": "Nama posisi minimal 3 karakter",
                "example": "Area Sales Promotion Supervisor"
            })
        
        # ============================================================
        # 3. VALIDATE KODE PIC
        # ============================================================
        kode_pic = row.get("Kode PIC")
        if pd.isna(kode_pic) or str(kode_pic).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode PIC",
                "value": kode_pic,
                "error": "Kode PIC tidak boleh kosong",
                "expected": "Kode PIC (contoh: CORPOme, MPPau)",
                "example": "CORPOme, MPPau, CMDSal"
            })
        
        # ============================================================
        # 4. VALIDATE FPTK DATE (REAL)
        # ============================================================
        fptk_date_real = row.get("FPTK Date (Real)")
        if pd.isna(fptk_date_real):
            errors.append({
                "row": row_num,
                "field": "FPTK Date (Real)",
                "value": fptk_date_real,
                "error": "FPTK Date (Real) tidak boleh kosong",
                "expected": "Format tanggal yang valid",
                "example": f"Contoh: 15/08/2026 atau {datetime.now().strftime('%d/%m/%Y')}"
            })
        elif not _is_valid_date(fptk_date_real):
            errors.append({
                "row": row_num,
                "field": "FPTK Date (Real)",
                "value": fptk_date_real,
                "error": f"Format tanggal '{fptk_date_real}' tidak valid",
                "expected": "Format DD/MM/YYYY atau DD-MM-YYYY",
                "example": "Contoh: 15/08/2026"
            })
        
        # ============================================================
        # 5. VALIDATE BUSINESS UNIT
        # ============================================================
        bu = row.get("Business Unit") or row.get("PT / Business Unit")
        if pd.isna(bu) or str(bu).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Business Unit",
                "value": bu,
                "error": "Business Unit tidak boleh kosong",
                "expected": "Business Unit yang valid",
                "example": "CORP, MP, CMD, JESS, MS"
            })
        
        # ============================================================
        # 6. VALIDATE DIREKTORAT
        # ============================================================
        direktorat = row.get("Direktorat")
        if pd.isna(direktorat) or str(direktorat).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Direktorat",
                "value": direktorat,
                "error": "Direktorat tidak boleh kosong",
                "expected": "Nama Direktorat yang valid",
                "example": "Corporate, Commercial MP, Commercial CMD"
            })
        
        # ============================================================
        # 7. VALIDATE LEVEL FPTK
        # ============================================================
        level = row.get("Level FPTK")
        if pd.isna(level) or str(level).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Level FPTK",
                "value": level,
                "error": "Level FPTK tidak boleh kosong",
                "expected": "Level FPTK (1A sampai 5B)",
                "example": "1A, 1B, 2A, 2B, 3A, 3B, 4A, 4B, 5A, 5B"
            })
        else:
            level_str = str(level).strip().upper()
            if not re.match(r'^[1-5][A-B]$', level_str):
                errors.append({
                    "row": row_num,
                    "field": "Level FPTK",
                    "value": level,
                    "error": f"Level FPTK '{level}' tidak valid",
                    "expected": "Level FPTK harus format [1-5][A-B]",
                    "example": "1A, 2B, 3A, 4B, 5A"
                })
        
        # ============================================================
        # 8. VALIDATE VACANCY
        # ============================================================
        vacancy = row.get("Vacancy")
        if pd.isna(vacancy) or safe_int(vacancy) <= 0:
            errors.append({
                "row": row_num,
                "field": "Vacancy",
                "value": vacancy,
                "error": f"Vacancy '{vacancy}' tidak valid",
                "expected": "Angka positif (minimal 1)",
                "example": "1, 2, 3, dst"
            })
        
        # ============================================================
        # 9. VALIDATE STATUS
        # ============================================================
        status = row.get("Status")
        if pd.isna(status) or str(status).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Status",
                "value": status,
                "error": "Status tidak boleh kosong",
                "expected": "Status: OP, Closed, atau Cancel",
                "example": "OP, Closed, Cancel"
            })
        else:
            status_str = str(status).strip()
            if status_str not in ["OP", "Closed", "Cancel"]:
                errors.append({
                    "row": row_num,
                    "field": "Status",
                    "value": status,
                    "error": f"Status '{status}' tidak valid",
                    "expected": "Status harus: OP, Closed, atau Cancel",
                    "example": "OP, Closed, Cancel"
                })
        
        # ============================================================
        # 10. VALIDATE OFFERING DATE (jika status Closed)
        # ============================================================
        if str(status).strip() == "Closed":
            offering_date = row.get("Offering Date")
            if pd.isna(offering_date):
                errors.append({
                    "row": row_num,
                    "field": "Offering Date",
                    "value": offering_date,
                    "error": "Offering Date wajib diisi karena Status = Closed",
                    "expected": "Tanggal Offering",
                    "example": "15/08/2026"
                })
            elif not _is_valid_date(offering_date):
                errors.append({
                    "row": row_num,
                    "field": "Offering Date",
                    "value": offering_date,
                    "error": f"Format Offering Date '{offering_date}' tidak valid",
                    "expected": "Format DD/MM/YYYY atau DD-MM-YYYY",
                    "example": "15/08/2026"
                })
        
        # ============================================================
        # 11. VALIDATE CANCEL DATE (jika status Cancel)
        # ============================================================
        if str(status).strip() == "Cancel":
            cancel_date = row.get("FPTK Cancel Date")
            if pd.isna(cancel_date):
                errors.append({
                    "row": row_num,
                    "field": "FPTK Cancel Date",
                    "value": cancel_date,
                    "error": "FPTK Cancel Date wajib diisi karena Status = Cancel",
                    "expected": "Tanggal Cancel",
                    "example": "15/08/2026"
                })
            elif not _is_valid_date(cancel_date):
                errors.append({
                    "row": row_num,
                    "field": "FPTK Cancel Date",
                    "value": cancel_date,
                    "error": f"Format Cancel Date '{cancel_date}' tidak valid",
                    "expected": "Format DD/MM/YYYY atau DD-MM-YYYY",
                    "example": "15/08/2026"
                })
        
        # ============================================================
        # 12. VALIDATE LEVEL NUMBER
        # ============================================================
        level_num = row.get("Level Number")
        if not pd.isna(level_num):
            try:
                int_val = int(level_num)
                if int_val < 1 or int_val > 5:
                    errors.append({
                        "row": row_num,
                        "field": "Level Number",
                        "value": level_num,
                        "error": f"Level Number '{level_num}' harus antara 1-5",
                        "expected": "Angka 1-5",
                        "example": "1, 2, 3, 4, 5"
                    })
            except (ValueError, TypeError):
                errors.append({
                    "row": row_num,
                    "field": "Level Number",
                    "value": level_num,
                    "error": f"Level Number '{level_num}' harus angka",
                    "expected": "Angka 1-5",
                    "example": "1, 2, 3, 4, 5"
                })
        
        # ============================================================
        # 13. VALIDATE WEEK FPTK DATE
        # ============================================================
        week = row.get("Week FPTK Date (Kode)") or row.get("Week FPTK Date")
        if not pd.isna(week):
            try:
                int_val = int(week)
                if int_val < 1 or int_val > 53:
                    errors.append({
                        "row": row_num,
                        "field": "Week FPTK Date",
                        "value": week,
                        "error": f"Week FPTK Date '{week}' harus antara 1-53",
                        "expected": "Angka 1-53",
                        "example": "1-53"
                    })
            except (ValueError, TypeError):
                errors.append({
                    "row": row_num,
                    "field": "Week FPTK Date",
                    "value": week,
                    "error": f"Week FPTK Date '{week}' harus angka",
                    "expected": "Angka 1-53",
                    "example": "1, 2, 3, ... 53"
                })
    
    # ============================================================
    # SUMMARY
    # ============================================================
    if errors:
        # Tambahkan error summary di awal
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data",
            "expected": f"Semua {len(df)} baris harus valid",
            "example": "Perbaiki error di bawah ini"
        })
        return False, errors
    
    return True, []


def _is_valid_date(value) -> bool:
    """Cek apakah value adalah tanggal yang valid"""
    if pd.isna(value):
        return False
    
    # Jika sudah datetime object
    if isinstance(value, (datetime, pd.Timestamp)):
        return True
    
    # Coba parse dari string
    if isinstance(value, str):
        return parse_date_dmy(value) is not None
    
    return False
