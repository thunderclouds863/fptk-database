import re
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Tuple, List, Dict, Any, Optional

from core.models import FPTK, DBSourcing, DBKodePosisi, Blacklist
from core.utils import parse_date_dmy, safe_int, normalize_key


# ============================================================
# HELPER: FIND COLUMN MAPPING (FUZZY)
# ============================================================
def find_column_mapping(df: pd.DataFrame, required_mappings: Dict[str, List[str]]) -> Dict[str, str]:
    """Cari mapping kolom dengan fuzzy matching."""
    df_cols = list(df.columns)
    df_cols_lower = [normalize_key(str(c)) for c in df_cols]
    
    mapping = {}
    used_cols = set()
    
    for field_key, possible_names in required_mappings.items():
        found = None
        
        # 1. Exact match
        for name in possible_names:
            norm_name = normalize_key(name)
            if norm_name in df_cols_lower:
                idx = df_cols_lower.index(norm_name)
                found = df_cols[idx]
                break
        
        # 2. Fuzzy match
        if not found:
            all_possible = []
            for name in possible_names:
                all_possible.append(normalize_key(name))
                base = normalize_key(name)
                base = re.sub(r'\s*\(.*?\)\s*', '', base)
                all_possible.append(base)
                base = re.sub(r'\s*kebutuhan\s*', '', base, flags=re.IGNORECASE)
                base = re.sub(r'\s*ta\s*', '', base, flags=re.IGNORECASE)
                all_possible.append(base)
            
            all_possible = list(set(all_possible))
            
            for col in df_cols_lower:
                if col in used_cols:
                    continue
                col_norm = normalize_key(col)
                for pattern in all_possible:
                    if col_norm == pattern:
                        idx = df_cols_lower.index(col)
                        found = df_cols[idx]
                        break
                    if pattern in col_norm or col_norm in pattern:
                        ratio = get_similarity_ratio(col_norm, pattern)
                        if ratio > 0.7:
                            idx = df_cols_lower.index(col)
                            found = df_cols[idx]
                            break
                if found:
                    break
        
        if found:
            mapping[field_key] = found
            used_cols.add(normalize_key(found))
    
    return mapping


def get_similarity_ratio(a: str, b: str) -> float:
    """Hitung similarity ratio antara dua string"""
    if not a or not b:
        return 0.0
    
    a = a.lower()
    b = b.lower()
    
    if a in b or b in a:
        shorter = a if len(a) < len(b) else b
        longer = b if len(a) < len(b) else a
        if shorter in longer:
            return len(shorter) / len(longer)
    
    common = len(set(a) & set(b))
    total = (len(a) + len(b)) / 2
    if total == 0:
        return 0.0
    return common / total


def _is_valid_date(value) -> bool:
    """Cek apakah value adalah tanggal yang valid"""
    if pd.isna(value):
        return False
    
    if isinstance(value, (datetime, pd.Timestamp, date)):
        return True
    
    if isinstance(value, (int, float)):
        try:
            from datetime import datetime as dt
            base = dt(1899, 12, 30)
            result = (base + timedelta(days=float(value))).date()
            return result is not None
        except:
            pass
    
    if isinstance(value, str):
        return parse_date_dmy(value) is not None
    
    return False


def safe_level_fptk_from_string(value):
    """Ambil level_fptk dari string, return None jika tidak valid"""
    if value is None or pd.isna(value):
        return None
    
    value_str = str(value).strip().upper()
    
    if re.match(r'^[1-5][A-B]$', value_str):
        return value_str
    
    match = re.search(r'(\d+)', value_str)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 5:
            return f"{num}A"
    
    return None


def safe_level_number_from_string(value):
    """Ambil angka dari level_number"""
    if value is None or pd.isna(value):
        return None
    
    if isinstance(value, (int, float)):
        try:
            int_val = int(value)
            if 1 <= int_val <= 5:
                return int_val
            return None
        except:
            return None
    
    if isinstance(value, str):
        match = re.search(r'(\d+)', value)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 5:
                return num
        return None
    
    return None


# ============================================================
# VALIDATE FPTK FILE
# ============================================================
def validate_fptk_file(
    df: pd.DataFrame,
    db,
    user_id: int,
    is_sto: bool = False
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Validasi file FPTK dengan error detail per row"""
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
    required_mappings = {
        "kode_unik": ["Kode Unik", "KodeUNIK", "Unique Code"],
        "posisi": ["Posisi", "Posisi - Kebutuhan TA", "Posisi Kebutuhan", "Position"],
        "kode_pic": ["Kode PIC", "PIC Code", "Kode PIC Recruiter"],
        "fptk_date_real": ["FPTK Date (Real)", "FPTK DATE (Real)", "FPTK Date Real", "Tanggal FPTK"],
        "business_unit": ["Business Unit", "PT / Business Unit", "BU", "Business"],
        "direktorat": ["Direktorat", "DIRECTORATE", "Directorate"],
        "divisi": ["Divisi", "Divisi (Sesuai SO)", "Divisi Sesuai SO", "Division"],
        "department": ["Department", "Departemen"],
        "level_fptk": ["Level FPTK", "Level"],
        "alasan_permintaan_fptk": ["Alasan Permintaan FPTK", "Alasan FPTK", "Reason FPTK"],
        "category_fptk": ["Category FPTK", "Kategori FPTK", "Category"],
        "pic_recruiter": ["PIC Recruiter", "PIC Rekruter", "Recruiter"],
        "vacancy": ["Vacancy", "Jumlah Posisi", "Jumlah FPTK"],
        "status": ["Status", "FPTK Status"],
    }
    
    optional_mappings = {
        "level_number": ["Level Number", "Level FPTK Number"],
        "filter_kategorisasi_fptk": ["Filter Kategorisasi FPTK", "Filter Kategorisasi"],
        "week_fptk_date": ["Week FPTK Date (Kode)", "Week FPTK Date", "Week"],
        "month_fptk_date": ["Month FPTK Date", "Month", "Bulan FPTK"],
        "fptk_cancel_date": ["FPTK Cancel Date", "Tanggal Cancel FPTK", "Cancel Date"],
        "offering_date": ["Offering Date", "Tanggal Offering"],
        "jumlah_sla": ["Jumlah SLA", "SLA Days"],
        "deadline_sla": ["Deadline pemenuhan SLA", "Deadline SLA"],
        "detail_sla": ["Detail SLA", "SLA Detail"],
        "nama_kandidat": ["Nama Kandidat", "Kandidat", "Candidate Name"],
        "estimasi_join": ["Estimasi Join", "Join Date", "Tanggal Join"],
        "kebutuhan_laptop": ["Kebutuhan Laptop (V)", "Kebutuhan Laptop", "Laptop"],
        "lokasi_onboarding": ["Lokasi Onboarding", "Onboarding Location"],
        "user_manager": ["User (Manager)", "User Manager", "Manager"],
        "indirect_user": ["Indirect User", "Indirect"],
        "lokasi_kerja": ["Lokasi Kerja", "Work Location"],
        "lokasi_hr": ["Lokasi HR", "HR Location"],
        "status_karyawan": ["Status Karyawan", "Employee Status"],
        "kode_bu": ["Kode BU", "Kode Business Unit"],
        "fptk_availability": ["FPTK Availability", "Availability"],
        "remark": ["Remark", "Catatan"],
        "source_file": ["Source File", "File Sumber"],
    }
    
    # ============================================================
    # FIND COLUMN MAPPING
    # ============================================================
    df_cols = list(df.columns)
    all_mappings = {**required_mappings, **optional_mappings}
    column_mapping = find_column_mapping(df, all_mappings)
    
    # Cek kolom yang hilang
    missing_columns = []
    for field_key in required_mappings.keys():
        if field_key not in column_mapping:
            missing_columns.append({
                "field": field_key,
                "possible": required_mappings[field_key],
                "error": f"Kolom untuk '{field_key}' tidak ditemukan"
            })
    
    if missing_columns:
        for miss in missing_columns:
            errors.append({
                "row": 0,
                "field": miss["field"],
                "value": "",
                "error": f"Kolom '{miss['field']}' tidak ditemukan",
                "expected": f"Coba salah satu nama: {', '.join(miss['possible'])}"
            })
        
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Header file tidak sesuai. Ditemukan {len(df_cols)} kolom",
            "expected": f"Butuh {len(required_mappings)} kolom wajib",
            "example": f"Header ditemukan: {', '.join([str(c)[:30] for c in df_cols[:10]])}..."
        })
        return False, errors
    
    # Rename columns
    rename_map = {}
    for field_key, col_name in column_mapping.items():
        rename_map[col_name] = field_key
    
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # ============================================================
    # VALIDATE EACH ROW
    # ============================================================
    for idx, row in df.iterrows():
        row_num = idx + 2

        # 1. KODE UNIK
        kode_unik = row.get("kode_unik")
        
        if pd.isna(kode_unik) or str(kode_unik).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": kode_unik,
                "error": "Kode Unik tidak boleh kosong",
                "expected": "Format: [Kode PIC][4 huruf posisi][tanggal DDMMYY]"
            })
        
        else:
            kode_unik_clean = str(kode_unik).strip()
        
            existing_same_code = db.query(FPTK).filter(
                FPTK.kode_unik == kode_unik_clean
            ).all()
        
            if existing_same_code:
        
                existing_positions = [
                    x.posisi for x in existing_same_code
                ]
        
                posisi_upload = str(
                    row.get("posisi")
                ).strip()
        
        
                # Kode unik sama tapi posisi beda
                if posisi_upload not in existing_positions:
        
                    errors.append({
                        "row": row_num,
                        "field": "Kode Unik",
                        "value": kode_unik,
                        "warning": True,
                        "error": (
                            f"Kode Unik '{kode_unik}' sudah digunakan "
                            f"dengan posisi berbeda: {', '.join(existing_positions)}"
                        ),
                        "expected": (
                            "Pastikan Kode Unik sesuai posisi. "
                            "Data tetap akan diinsert, mohon segera edit."
                        )
                    })
        
        # 2. POSISI
        posisi = row.get("posisi")
        if pd.isna(posisi) or str(posisi).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Posisi",
                "value": posisi,
                "error": "Posisi tidak boleh kosong",
                "expected": "Nama posisi minimal 3 karakter"
            })
        
        # 3. KODE PIC
        kode_pic = row.get("kode_pic")
        if pd.isna(kode_pic) or str(kode_pic).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode PIC",
                "value": kode_pic,
                "error": "Kode PIC tidak boleh kosong",
                "expected": "Kode PIC (contoh: CORPOme, MPPau)"
            })
        
        # 4. FPTK DATE REAL
        fptk_date = row.get("fptk_date_real")
        if pd.isna(fptk_date) or str(fptk_date).strip() == "":
            errors.append({
                "row": row_num,
                "field": "FPTK Date (Real)",
                "value": fptk_date,
                "error": "FPTK Date (Real) tidak boleh kosong",
                "expected": "Format tanggal yang valid"
            })
        elif not _is_valid_date(fptk_date):
            errors.append({
                "row": row_num,
                "field": "FPTK Date (Real)",
                "value": fptk_date,
                "error": f"Format tanggal '{fptk_date}' tidak valid",
                "expected": "Format DD/MM/YYYY atau DD-MM-YYYY"
            })
        
        # 5. BUSINESS UNIT
        bu = row.get("business_unit")
        if pd.isna(bu) or str(bu).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Business Unit",
                "value": bu,
                "error": "Business Unit tidak boleh kosong",
                "expected": "Business Unit yang valid"
            })
        
        # 6. DIREKTORAT
        direktorat = row.get("direktorat")
        if pd.isna(direktorat) or str(direktorat).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Direktorat",
                "value": direktorat,
                "error": "Direktorat tidak boleh kosong",
                "expected": "Nama Direktorat yang valid"
            })
        
        # 7. LEVEL FPTK
        level = row.get("level_fptk")
        if pd.isna(level) or str(level).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Level FPTK",
                "value": level,
                "error": "Level FPTK tidak boleh kosong",
                "expected": "Level FPTK (1A sampai 5B)"
            })
        else:
            level_str = str(level).strip().upper()
            if not re.match(r'^[1-5][A-B]$', level_str):
                match = re.search(r'(\d+)', level_str)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 5:
                        suggested = f"{num}A"
                        errors.append({
                            "row": row_num,
                            "field": "Level FPTK",
                            "value": level,
                            "error": f"Level FPTK '{level}' harus format [1-5][A-B]",
                            "expected": f"Level FPTK harus: 1A, 1B, 2A, 2B, 3A, 3B, 4A, 4B, 5A, 5B",
                            "example": f"Ganti '{level}' menjadi '{suggested}' atau '{num}B'"
                        })
                    else:
                        errors.append({
                            "row": row_num,
                            "field": "Level FPTK",
                            "value": level,
                            "error": f"Level FPTK '{level}' tidak valid (harus 1-5)",
                            "expected": "Level FPTK harus antara 1-5"
                        })
                else:
                    errors.append({
                        "row": row_num,
                        "field": "Level FPTK",
                        "value": level,
                        "error": f"Level FPTK '{level}' tidak valid",
                        "expected": "Level FPTK harus format [1-5][A-B]"
                    })
        
        # 8. VACANCY
        vacancy = row.get("vacancy")
        if pd.isna(vacancy) or safe_int(vacancy) <= 0:
            errors.append({
                "row": row_num,
                "field": "Vacancy",
                "value": vacancy,
                "error": f"Vacancy '{vacancy}' tidak valid",
                "expected": "Angka positif (minimal 1)"
            })
        
        # 9. STATUS
        status = row.get("status")
        if pd.isna(status) or str(status).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Status",
                "value": status,
                "error": "Status tidak boleh kosong",
                "expected": "Status: OP, Closed, atau Cancel"
            })
        else:
            status_str = str(status).strip()
            if status_str not in ["OP", "Closed", "Cancel"]:
                errors.append({
                    "row": row_num,
                    "field": "Status",
                    "value": status,
                    "error": f"Status '{status}' tidak valid",
                    "expected": "Status harus: OP, Closed, atau Cancel"
                })
        
        # 10. OFFERING DATE (jika status Closed)
        if str(status).strip() == "Closed":
            offering_date = row.get("offering_date")
            if pd.isna(offering_date) or str(offering_date).strip() == "":
                errors.append({
                    "row": row_num,
                    "field": "Offering Date",
                    "value": offering_date,
                    "error": "Offering Date wajib diisi karena Status = Closed",
                    "expected": "Tanggal Offering"
                })
            elif not _is_valid_date(offering_date):
                errors.append({
                    "row": row_num,
                    "field": "Offering Date",
                    "value": offering_date,
                    "error": f"Format Offering Date '{offering_date}' tidak valid",
                    "expected": "Format DD/MM/YYYY atau DD-MM-YYYY"
                })
        
        # 11. CANCEL DATE (jika status Cancel)
        if str(status).strip() == "Cancel":
            cancel_date = row.get("fptk_cancel_date")
            if pd.isna(cancel_date) or str(cancel_date).strip() == "":
                errors.append({
                    "row": row_num,
                    "field": "FPTK Cancel Date",
                    "value": cancel_date,
                    "error": "FPTK Cancel Date wajib diisi karena Status = Cancel",
                    "expected": "Tanggal Cancel"
                })
            elif not _is_valid_date(cancel_date):
                errors.append({
                    "row": row_num,
                    "field": "FPTK Cancel Date",
                    "value": cancel_date,
                    "error": f"Format Cancel Date '{cancel_date}' tidak valid",
                    "expected": "Format DD/MM/YYYY atau DD-MM-YYYY"
                })
        
        # 12. LEVEL NUMBER - AUTO FIX
        raw_level_number = row.get("level_number")
        level_num = safe_level_number_from_string(raw_level_number)
        
        if level_num is None:
            level_fptk_val = row.get("level_fptk")
            level_num = safe_level_number_from_string(level_fptk_val)
            
            if level_num is not None:
                df.at[idx, 'level_number'] = level_num
            else:
                df.at[idx, 'level_number'] = 1
                errors.append({
                    "row": row_num,
                    "field": "Level Number",
                    "value": raw_level_number,
                    "error": f"Level Number '{raw_level_number}' tidak valid, auto-set ke 1",
                    "expected": "Angka 1-5 atau kosong (auto-dari Level FPTK)"
                })
        else:
            df.at[idx, 'level_number'] = level_num
    
    # ============================================================
    # SUMMARY
    # ============================================================
    warnings = [
        e for e in errors
        if e.get("warning", False)
    ]
    
    critical_errors = [
        e for e in errors
        if not e.get("warning", False)
    ]
    
    if critical_errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors = [e for e in errors if e.get("field") != "SUMMARY"]
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data",
            "expected": f"Semua {len(df)} baris harus valid",
            "example": "Perbaiki error di bawah ini"
        })
        return False, errors
    
    return True, warnings


# ============================================================
# VALIDATE DB SOURCING FILE
# ============================================================
def validate_db_sourcing_file(
    df: pd.DataFrame,
    db,
    user_id: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file DB Sourcing
    - Kode Unik BOLEH duplikat
    - Kode Unik TIDAK HARUS ada di FPTK
    """
    errors = []
    
    if df.empty:
        errors.append({
            "row": 0,
            "field": "file",
            "value": "",
            "error": "File kosong, tidak ada data yang ditemukan",
            "expected": "Minimal 1 baris data DB Sourcing"
        })
        return False, errors
    
    # ============================================================
    # REQUIRED COLUMNS MAPPING
    # ============================================================
    required_mappings = {
        "kode_unik": ["Kode Unik", "Kode UNIK", "Unique Code", "Kode Unik (copy value dari FPTK)"],
        "nama": ["Nama", "Nama Kandidat", "Candidate Name"],
        "sourcing_date": ["Sourcing Date", "Tanggal Sourcing", "Tanggal Input"],
    }
    
    optional_mappings = {
        "posisi": ["Posisi", "Position"],
        "model_rekrutmen": ["Model Rekrutmen", "Model"],
        "rekruter": ["Rekruter", "Recruiter", "PIC Recruiter"],
        "sumber_sourcing": ["Sumber Sourcing", "Source"],
        "nomor_hp": ["Nomor HP", "No HP", "Phone"],
        "email": ["Email", "Email Address"],
        "domisili": ["Domisili", "Domicile"],
        "jenjang_pendidikan": ["Jenjang Pendidikan", "Education Level"],
        "jurusan": ["Jurusan", "Major"],
        "tahun_lulus": ["Tahun Lulus", "Graduation Year"],
        "ipk": ["IPK", "GPA"],
        "university_tier": ["University Tier", "Univ Tier"],
        "ipk_tier": ["IPK Tier", "GPA Tier"],
        "nama_universitas_top10": ["Nama Universitas/Sekolah (TOP 10)", "Universitas"],
        "nama_universitas_lainnya": ["Nama Universitas/Sekolah Lainnya", "Universitas Lainnya"],
        "last_position": ["Last Position", "Posisi Terakhir"],
        "last_company": ["Last Company", "Company Terakhir"],
        "last_tenure": ["Last Tenure"],
        "total_tenure": ["Total Tenure"],
        "pernah_di_fmcg": ["Pernah di FMCG?", "FMCG"],
        "sourcing_hr": ["Sourcing HR"],
        "shortlist_cv": ["Shortlist CV"],
        "psikotes": ["Psikotes"],
        "hr_interview": ["HR Interview"],
        "user_interview": ["User Interview"],
        "offering": ["Offering"],
        "day1": ["Day 1"],
    }
    
    # ============================================================
    # FIND COLUMN MAPPING
    # ============================================================
    all_mappings = {**required_mappings, **optional_mappings}
    column_mapping = find_column_mapping(df, all_mappings)
    
    # Cek kolom yang hilang
    missing_columns = []
    for field_key in required_mappings.keys():
        if field_key not in column_mapping:
            missing_columns.append(field_key)
    
    if missing_columns:
        errors.append({
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Kolom wajib hilang: {', '.join(missing_columns)}",
            "expected": f"Kolom wajib: {', '.join(required_mappings.keys())}",
            "example": "Periksa header file DB Sourcing"
        })
        return False, errors
    
    # Rename columns
    rename_map = {}
    for field_key, col_name in column_mapping.items():
        rename_map[col_name] = field_key
    
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # ============================================================
    # VALIDATE EACH ROW
    # ============================================================
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        # KODE UNIK - boleh kosong, boleh duplikat
        kode_unik = row.get("kode_unik")
        if pd.isna(kode_unik) or str(kode_unik).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": kode_unik,
                "error": "Kode Unik tidak boleh kosong",
                "expected": "Kode Unik yang terdaftar di FPTK (opsional, boleh tidak ada)"
            })
        # ✅ TIDAK ADA CEK DUPLIKAT
        # ✅ TIDAK ADA CEK FPTK
        
        # NAMA harus ada
        nama = row.get("nama")
        if pd.isna(nama) or str(nama).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Nama",
                "value": nama,
                "error": "Nama tidak boleh kosong",
                "expected": "Nama kandidat"
            })
        
        # SOURCING DATE harus ada
        sourcing_date = row.get("sourcing_date")
        if pd.isna(sourcing_date) or str(sourcing_date).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": "Sourcing Date tidak boleh kosong",
                "expected": "Format tanggal yang valid"
            })
        elif not _is_valid_date(sourcing_date):
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": f"Format Sourcing Date '{sourcing_date}' tidak valid",
                "expected": "Format DD/MM/YYYY atau DD-MM-YYYY"
            })
    
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data DB Sourcing",
            "expected": f"Semua {len(df)} baris harus valid",
            "example": "Perbaiki error di bawah ini"
        })
        return False, errors
    
    return True, []


# ============================================================
# VALIDATE BLACKLIST FILE
# ============================================================
def validate_blacklist_file(
    df: pd.DataFrame,
    db,
    user_id: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Validasi file Blacklist Candidate"""
    errors = []
    
    if df.empty:
        errors.append({
            "row": 0,
            "field": "file",
            "value": "",
            "error": "File kosong",
            "expected": "Minimal 1 baris data"
        })
        return False, errors
    
    # Cari kolom key
    df_cols = list(df.columns)
    key_col = None
    
    for col in df_cols:
        col_lower = normalize_key(col)
        if col_lower in ["key", "key_value", "unique_key", "blacklist_key", "nama", "name"]:
            key_col = col
            break
    
    if not key_col:
        errors.append({
            "row": 0,
            "field": "Key Column",
            "value": "",
            "error": "Kolom key tidak ditemukan",
            "expected": "Kolom dengan nama: Key, Key Value, Nama, atau Blacklist Key"
        })
        return False, errors
    
    # Rename
    df.rename(columns={key_col: "key_value"}, inplace=True)
    
    # Validasi per row
    for idx, row in df.iterrows():
        row_num = idx + 2
        key = row.get("key_value")
        
        if pd.isna(key) or str(key).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Key",
                "value": key,
                "error": "Key tidak boleh kosong",
                "expected": "Nama atau identifier untuk blacklist"
            })
        else:
            existing_data = db.query(FPTK).filter(
                FPTK.kode_unik == str(kode_unik).strip()
            ).all()
            
            if existing_data:
            
                posisi_upload = str(
                    row.get("posisi")
                ).strip()
            
                existing_positions = [
                    str(x.posisi).strip()
                    for x in existing_data
                ]
            
                # CASE KHUSUS:
                # Kode Unik sama, tapi posisi berbeda
                if posisi_upload not in existing_positions:
            
                    errors.append({
                        "row": row_num,
                        "field": "Kode Unik",
                        "value": kode_unik,
                        "warning": True,
                        "error": (
                            f"Kode Unik '{kode_unik}' "
                            f"sudah digunakan untuk posisi "
                            f"{', '.join(existing_positions)}"
                        ),
                        "expected": (
                            "Data tetap diproses karena posisi berbeda. "
                            "Mohon segera lakukan pengecekan/edit Kode Unik."
                        )
                    })
    
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data Blacklist",
            "expected": f"Semua {len(df)} baris harus valid"
        })
        return False, errors
    
    return True, []


# ============================================================
# VALIDATE DB KODE POSISI FILE
# ============================================================
def validate_db_kode_posisi_file(
    df: pd.DataFrame,
    db,
    user_id: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Validasi file DB Kode Posisi"""
    errors = []
    
    if df.empty:
        errors.append({
            "row": 0,
            "field": "file",
            "value": "",
            "error": "File kosong",
            "expected": "Minimal 1 baris data"
        })
        return False, errors
    
    required_mappings = {
        "position": ["POSITION", "Position", "Posisi"],
        "kode": ["KODE", "Kode", "Kode Angka"],
    }
    
    optional_mappings = {
        "location": ["LOCATION", "Location", "Lokasi", "Lokasi Kerja"],
        "business_unit": ["BUSINESS UNIT", "Business Unit", "BU"],
        "division_chris": ["DIVISION CHRIS", "Division Chris", "Divisi"],
        "department_chris": ["DEPARTMENT CHRIS", "Department Chris", "Department"],
        "user_manager": ["USER (MANAGER)", "User Manager", "Manager"],
        "indirect_user": ["INDIRECT USER", "Indirect User"],
        "directorate": ["DIRECTORATE", "Directorate", "Direktorat"],
        "year": ["YEAR", "Year", "Tahun"],
    }
    
    all_mappings = {**required_mappings, **optional_mappings}
    column_mapping = find_column_mapping(df, all_mappings)
    
    missing_columns = []
    for field_key in required_mappings.keys():
        if field_key not in column_mapping:
            missing_columns.append(field_key)
    
    if missing_columns:
        errors.append({
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Kolom wajib hilang: {', '.join(missing_columns)}",
            "expected": f"Kolom wajib: {', '.join(required_mappings.keys())}"
        })
        return False, errors
    
    # Rename
    rename_map = {}
    for field_key, col_name in column_mapping.items():
        rename_map[col_name] = field_key
    
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        position = row.get("position")
        if pd.isna(position) or str(position).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Position",
                "value": position,
                "error": "Position tidak boleh kosong",
                "expected": "Nama posisi"
            })
        
        kode = row.get("kode")
        if pd.isna(kode) or str(kode).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode",
                "value": kode,
                "error": "Kode tidak boleh kosong",
                "expected": "Kode posisi"
            })
    
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data DB Kode Posisi",
            "expected": f"Semua {len(df)} baris harus valid"
        })
        return False, errors
    
    return True, []
