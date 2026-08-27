# core/validator.py

import re  # ✅ IMPORT RE DI AWAL
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Tuple, List, Dict, Any, Optional
from difflib import get_close_matches

# IMPORT MODEL FPTK
from core.models import FPTK, DBSourcing, DBKodePosisi, Blacklist
from core.utils import parse_date_dmy, safe_int, normalize_key


def find_column_mapping(df: pd.DataFrame, required_mappings: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Cari mapping kolom dengan fuzzy matching.
    Kalo ga ketemu exact match, cari yang mirip.
    """
    df_cols = list(df.columns)
    df_cols_lower = [normalize_key(str(c)) for c in df_cols]
    
    mapping = {}
    used_cols = set()
    
    for field_key, possible_names in required_mappings.items():
        found = None
        
        # 1. Coba exact match
        for name in possible_names:
            norm_name = normalize_key(name)
            if norm_name in df_cols_lower:
                idx = df_cols_lower.index(norm_name)
                found = df_cols[idx]
                break
        
        # 2. Kalo ga ketemu, coba fuzzy match
        if not found:
            all_possible = []
            for name in possible_names:
                all_possible.append(normalize_key(name))
                
                # Tambahkan variasi tanpa "TA", "(Real)", "(Kode)", dll
                base = normalize_key(name)
                base = re.sub(r'\s*\(.*?\)\s*', '', base)  # Hapus (Real), (Kode), dll
                all_possible.append(base)
                
                # Hapus "Kebutuhan" atau "TA"
                base = re.sub(r'\s*kebutuhan\s*', '', base, flags=re.IGNORECASE)
                base = re.sub(r'\s*ta\s*', '', base, flags=re.IGNORECASE)
                all_possible.append(base)
            
            all_possible = list(set(all_possible))
            
            # Coba fuzzy match
            for col in df_cols_lower:
                if col in used_cols:
                    continue
                col_norm = normalize_key(col)
                
                # Cek apakah ada kemiripan
                for pattern in all_possible:
                    # Exact match setelah normalisasi
                    if col_norm == pattern:
                        idx = df_cols_lower.index(col)
                        found = df_cols[idx]
                        break
                    # Partial match
                    if pattern in col_norm or col_norm in pattern:
                        # Cek similarity ratio
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
    
    # Cek substring
    if a in b or b in a:
        shorter = a if len(a) < len(b) else b
        longer = b if len(a) < len(b) else a
        
        if shorter in longer:
            return len(shorter) / len(longer)
    
    # Hitung common characters
    common = len(set(a) & set(b))
    total = (len(a) + len(b)) / 2
    if total == 0:
        return 0.0
    
    return common / total


def _is_valid_date(value) -> bool:
    """Cek apakah value adalah tanggal yang valid"""
    if pd.isna(value):
        return False
    
    # Jika sudah datetime object
    if isinstance(value, (datetime, pd.Timestamp)):
        return True
    
    # Jika sudah date object
    if isinstance(value, date):
        return True
    
    # Jika numeric (Excel serial date)
    if isinstance(value, (int, float)):
        try:
            from datetime import datetime as dt
            base = dt(1899, 12, 30)
            result = (base + timedelta(days=float(value))).date()
            return result is not None
        except:
            pass
    
    # Coba parse dari string
    if isinstance(value, str):
        return parse_date_dmy(value) is not None
    
    return False


def safe_level_fptk_from_string(value):
    """Ambil level_fptk dari string, return None jika tidak valid"""
    if value is None or pd.isna(value):
        return None
    
    value_str = str(value).strip().upper()
    
    # Cek format 1A-5B
    if re.match(r'^[1-5][A-B]$', value_str):
        return value_str
    
    # Coba extract angka
    match = re.search(r'(\d+)', value_str)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 5:
            return f"{num}A"
    
    return None


def safe_level_number_from_string(value):
    """Ambil angka dari level_number, return None jika tidak valid"""
    if value is None or pd.isna(value):
        return None
    
    # Jika sudah angka
    if isinstance(value, (int, float)):
        try:
            int_val = int(value)
            if 1 <= int_val <= 5:
                return int_val
            return None
        except:
            return None
    
    # Jika string, coba extract angka
    if isinstance(value, str):
        match = re.search(r'(\d+)', value)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 5:
                return num
        return None
    
    return None


def validate_fptk_file(
    df: pd.DataFrame, 
    db, 
    user_id: int, 
    is_sto: bool = False
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file FPTK dengan error detail per row
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
    # REQUIRED COLUMNS MAPPING - DENGAN VARIASI NAMA
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
        "week_cancel_date": ["Week Cancel Date", "Week Cancel"],
        "month_cancel_date": ["Month Cancel Date", "Month Cancel"],
        "offering_date": ["Offering Date", "Tanggal Offering"],
        "week_offering_date": ["Week Offering Date", "Week Offering"],
        "month_offering": ["Month Offering", "Bulan Offering"],
        "jumlah_sla": ["Jumlah SLA", "SLA Days"],
        "deadline_sla": ["Deadline pemenuhan SLA", "Deadline SLA"],
        "detail_sla": ["Detail SLA", "SLA Detail"],
        "keterangan_lulus_sla": ["Keterangan Lulus SLA", "SLA Lulus"],
        "keterangan_tidak_lulus_sla": ["Keterangan Tidak Lulus SLA", "SLA Tidak Lulus"],
        "keterangan_cancel": ["Keterangan Cancel", "Alasan Cancel"],
        "nama_kandidat": ["Nama Kandidat", "Kandidat", "Candidate Name"],
        "estimasi_join": ["Estimasi Join", "Join Date", "Tanggal Join"],
        "kebutuhan_laptop": ["Kebutuhan Laptop (V)", "Kebutuhan Laptop", "Laptop"],
        "lokasi_onboarding": ["Lokasi Onboarding", "Onboarding Location"],
        "tanggal_upload_web": ["Tanggal Upload ke Website", "Upload Date"],
        "user_manager": ["User (Manager)", "User Manager", "Manager"],
        "indirect_user": ["Indirect User", "Indirect"],
        "lokasi_kerja": ["Lokasi Kerja", "Work Location"],
        "lokasi_hr": ["Lokasi HR", "HR Location"],
        "status_karyawan": ["Status Karyawan", "Employee Status"],
        "kode_bu": ["Kode BU", "Kode Business Unit"],
        "fptk_availability": ["FPTK Availability", "Availability"],
        "remark": ["Remark", "Catatan"],
        "source_file": ["Source File", "File Sumber"],
        "is_sto": ["is_sto", "STO", "Tulang Punggung"],
    }
    
    # ============================================================
    # FIND COLUMN MAPPING
    # ============================================================
    df_cols = list(df.columns)
    
    # Gabungkan semua mapping
    all_mappings = {**required_mappings, **optional_mappings}
    
    # Cari mapping kolom
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
                "expected": f"Coba salah satu nama: {', '.join(miss['possible'])}",
                "example": f"Kolom yang ditemukan: {', '.join([str(c)[:30] for c in df_cols[:10]])}..."
            })
        
        # Tambahkan saran perbaikan
        if errors:
            errors.insert(0, {
                "row": 0,
                "field": "SUMMARY",
                "value": "",
                "error": f"Header file tidak sesuai. Ditemukan {len(df_cols)} kolom, butuh {len(required_mappings)} kolom wajib",
                "expected": "Perbaiki nama header sesuai template",
                "example": f"Header ditemukan: {', '.join([str(c)[:30] for c in df_cols[:10]])}..."
            })
        
        return False, errors
    
    # ============================================================
    # RENAME COLUMNS SESUAI MAPPING
    # ============================================================
    rename_map = {}
    for field_key, col_name in column_mapping.items():
        rename_map[col_name] = field_key
    
    # Rename semua kolom yang ada mapping
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # Pastikan kolom yang diperlukan ada
    for field_key in required_mappings.keys():
        if field_key not in df.columns:
            errors.append({
                "row": 0,
                "field": field_key,
                "value": "",
                "error": f"Kolom '{field_key}' tidak ditemukan setelah rename",
                "expected": f"Pastikan kolom '{field_key}' ada"
            })
    
    if errors:
        return False, errors
    
    # ============================================================
    # VALIDATE EACH ROW
    # ============================================================
    for idx, row in df.iterrows():
        row_num = idx + 2  # +1 karena header, +1 karena index 0
        
        # ============================================================
        # 1. VALIDATE KODE UNIK
        # ============================================================
        kode_unik = row.get("kode_unik")
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
            kode_unik_str = str(kode_unik).strip()
            # Cek duplikat di database
            existing = db.query(FPTK).filter(FPTK.kode_unik == kode_unik_str).first()
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
        posisi = row.get("posisi")
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
        kode_pic = row.get("kode_pic")
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
        fptk_date_real = row.get("fptk_date_real")
        if pd.isna(fptk_date_real) or str(fptk_date_real).strip() == "":
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
                "expected": "Format DD/MM/YYYY atau DD-MM-YYYY atau YYYY-MM-DD",
                "example": "Contoh: 15/08/2026 atau 2026-10-16"
            })
        
        # ============================================================
        # 5. VALIDATE BUSINESS UNIT
        # ============================================================
        bu = row.get("business_unit")
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
        direktorat = row.get("direktorat")
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
        level = row.get("level_fptk")
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
            # Cek format 1A-5B
            if not re.match(r'^[1-5][A-B]$', level_str):
                # Coba ekstrak angka dari level
                match = re.search(r'(\d+)', level_str)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 5:
                        # Auto-fix: tambah A
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
                            "error": f"Level FPTK '{level}' tidak valid",
                            "expected": "Level FPTK harus antara 1-5",
                            "example": "1A, 2B, 3A, 4B, 5A"
                        })
                else:
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
        vacancy = row.get("vacancy")
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
        status = row.get("status")
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
            offering_date = row.get("offering_date")
            if pd.isna(offering_date) or str(offering_date).strip() == "":
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
            cancel_date = row.get("fptk_cancel_date")
            if pd.isna(cancel_date) or str(cancel_date).strip() == "":
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
        # 12. VALIDATE LEVEL NUMBER - AUTO FIX
        # ============================================================
        raw_level_number = row.get("level_number")
        level_num = safe_level_number_from_string(raw_level_number)
        
        if level_num is None:
            # Jika level_number kosong, coba dari level_fptk
            level_fptk_val = row.get("level_fptk")
            level_num = safe_level_number_from_string(level_fptk_val)
            
            if level_num is not None:
                # Auto fix: set level_number dari level_fptk
                df.at[idx, 'level_number'] = level_num
            else:
                # Default ke 1
                df.at[idx, 'level_number'] = 1
                errors.append({
                    "row": row_num,
                    "field": "Level Number",
                    "value": raw_level_number,
                    "error": f"Level Number '{raw_level_number}' tidak valid, auto-set ke 1",
                    "expected": "Angka 1-5 atau kosong (auto-dari Level FPTK)",
                    "example": "1, 2, 3, 4, 5"
                })
        else:
            # Pastikan level_number sudah benar
            df.at[idx, 'level_number'] = level_num
    
    # ============================================================
    # SUMMARY
    # ============================================================
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        
        # Hapus summary lama kalo ada
        errors = [e for e in errors if e.get("field") != "SUMMARY"]
        
        # Tambahkan summary baru di awal
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


def validate_db_sourcing_file(
    df: pd.DataFrame,
    db,
    user_id: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file DB Sourcing
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
    
    required_mappings = {
        "kode_unik": ["Kode Unik", "Unique Code"],
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
    
    # Cari mapping kolom
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
    
    # Rename kolom
    rename_map = {}
    for field_key, col_name in column_mapping.items():
        rename_map[col_name] = field_key
    
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # Validasi per row
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        # Kode Unik harus ada
        kode_unik = row.get("kode_unik")
        if pd.isna(kode_unik) or str(kode_unik).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": kode_unik,
                "error": "Kode Unik tidak boleh kosong",
                "expected": "Kode Unik yang terdaftar di FPTK",
                "example": "CORPOmeSales101024"
            })
        else:
            # Cek apakah Kode Unik ada di FPTK
            existing_fptk = db.query(FPTK).filter(FPTK.kode_unik == str(kode_unik).strip()).first()
            if not existing_fptk:
                errors.append({
                    "row": row_num,
                    "field": "Kode Unik",
                    "value": kode_unik,
                    "error": f"Kode Unik '{kode_unik}' tidak ditemukan di FPTK",
                    "expected": "Kode Unik harus terdaftar di FPTK",
                    "example": "Pastikan FPTK sudah di-compile terlebih dahulu"
                })
        
        # Nama harus ada
        nama = row.get("nama")
        if pd.isna(nama) or str(nama).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Nama",
                "value": nama,
                "error": "Nama tidak boleh kosong",
                "expected": "Nama kandidat",
                "example": "Budi Santoso"
            })
        
        # Sourcing Date harus ada
        sourcing_date = row.get("sourcing_date")
        if pd.isna(sourcing_date) or str(sourcing_date).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": "Sourcing Date tidak boleh kosong",
                "expected": "Format tanggal yang valid",
                "example": "15/08/2026"
            })
        elif not _is_valid_date(sourcing_date):
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": f"Format Sourcing Date '{sourcing_date}' tidak valid",
                "expected": "Format DD/MM/YYYY atau DD-MM-YYYY",
                "example": "15/08/2026"
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


def validate_blacklist_file(
    df: pd.DataFrame,
    db,
    user_id: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file Blacklist Candidate
    """
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
            "expected": "Kolom dengan nama: Key, Key Value, Nama, atau Blacklist Key",
            "example": "Tambahkan kolom dengan nama 'Nama' atau 'Key Value'"
        })
        return False, errors
    
    # Rename ke key_value
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
                "expected": "Nama atau identifier untuk blacklist",
                "example": "Budi Santoso"
            })
        else:
            # Cek duplikat
            existing = db.query(Blacklist).filter(Blacklist.key_value == str(key).strip()).first()
            if existing:
                errors.append({
                    "row": row_num,
                    "field": "Key",
                    "value": key,
                    "error": f"Key '{key}' sudah ada di blacklist",
                    "expected": "Key harus unik",
                    "example": "Gunakan key yang berbeda"
                })
    
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data Blacklist",
            "expected": f"Semua {len(df)} baris harus valid",
            "example": "Perbaiki error di bawah ini"
        })
        return False, errors
    
    return True, []


def validate_db_kode_posisi_file(
    df: pd.DataFrame,
    db,
    user_id: int
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file DB Kode Posisi
    """
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
    
    # Cari mapping kolom
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
            "example": "Periksa header file DB Kode Posisi"
        })
        return False, errors
    
    # Rename kolom
    rename_map = {}
    for field_key, col_name in column_mapping.items():
        rename_map[col_name] = field_key
    
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # Validasi per row
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        # Position harus ada
        position = row.get("position")
        if pd.isna(position) or str(position).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Position",
                "value": position,
                "error": "Position tidak boleh kosong",
                "expected": "Nama posisi",
                "example": "Area Sales Supervisor"
            })
        
        # Kode harus ada
        kode = row.get("kode")
        if pd.isna(kode) or str(kode).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode",
                "value": kode,
                "error": "Kode tidak boleh kosong",
                "expected": "Kode posisi",
                "example": "12345"
            })
    
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data DB Kode Posisi",
            "expected": f"Semua {len(df)} baris harus valid",
            "example": "Perbaiki error di bawah ini"
        })
        return False, errors
    
    return True, []

def validate_db_sourcing_file(df: pd.DataFrame):
    """Validasi file DB Sourcing"""
    errors = []
    valid_rows = []
    
    required_cols = ['kode_unik', 'nama']
    for col in required_cols:
        if col not in df.columns:
            errors.append({"field": "HEADER", "error": f"Kolom '{col}' tidak ditemukan"})
            return [], errors
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        if not row.get('kode_unik'):
            errors.append({"row": row_num, "field": "kode_unik", "error": "Kode Unik wajib diisi"})
            continue
        if not row.get('nama'):
            errors.append({"row": row_num, "field": "nama", "error": "Nama wajib diisi"})
            continue
        valid_rows.append(row)
    
    return valid_rows, errors


def validate_db_kode_posisi_file(df: pd.DataFrame):
    """Validasi file DB Kode Posisi"""
    errors = []
    valid_rows = []
    
    required_cols = ['position']
    for col in required_cols:
        if col not in df.columns:
            errors.append({"field": "HEADER", "error": f"Kolom '{col}' tidak ditemukan"})
            return [], errors
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        if not row.get('position'):
            errors.append({"row": row_num, "field": "position", "error": "Position wajib diisi"})
            continue
        valid_rows.append(row)
    
    return valid_rows, errors


def validate_blacklist_file(df: pd.DataFrame):
    """Validasi file Blacklist"""
    errors = []
    valid_rows = []
    
    if 'key_value' not in df.columns and 'key' not in df.columns:
        errors.append({"field": "HEADER", "error": "Kolom 'key_value' tidak ditemukan"})
        return [], errors
    
    key_col = 'key_value' if 'key_value' in df.columns else 'key'
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        key = row.get(key_col, '')
        if not key:
            errors.append({"row": row_num, "field": "key_value", "error": "Key wajib diisi"})
            continue
        valid_rows.append({**row.to_dict(), 'key_value': key})
    
    return valid_rows, errors
