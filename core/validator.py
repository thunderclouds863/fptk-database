# core/validator.py

import re
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
from core.utils import parse_date_dmy, safe_int, normalize_key, normalize_text
from core.models import FPTK, DBSourcing, Blacklist, DBKodePosisi


# ============================================================
# HEADER MAPPING UTILITY
# ============================================================

def find_column_mapping(df: pd.DataFrame, required_mappings: Dict[str, List[str]]) -> Dict[str, str]:
    """Cari mapping kolom dengan fuzzy matching."""
    df_cols = list(df.columns)
    df_cols_lower = [normalize_key(c) for c in df_cols]
    
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
                base = re.sub(r'\s*\(.*?\)\s*', '', base)
                all_possible.append(base)
                
                # Hapus kata tambahan
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
    if isinstance(value, (datetime, pd.Timestamp)):
        return True
    if isinstance(value, str):
        return parse_date_dmy(value) is not None
    return False


# ============================================================
# 1. VALIDATOR DB SOURCING
# ============================================================

def validate_db_sourcing_file(
    df: pd.DataFrame,
    db,
    user_id: int,
    cycle_id: int = None
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file DB Sourcing dengan strict rules:
    - Sourcing Date WAJIB
    - Kode Unik WAJIB (harus ada di FPTK)
    - Nama WAJIB
    - Status pipeline (V/X) hanya boleh V atau X
    - Blank source value TIDAK overwrite existing nonblank data
    """
    errors = []
    
    if df.empty:
        errors.append({
            "row": 0,
            "field": "file",
            "value": "",
            "error": "File kosong, tidak ada data yang ditemukan",
            "expected": "Minimal 1 baris data sourcing"
        })
        return False, errors
    
    # ============================================================
    # REQUIRED COLUMNS MAPPING - DB SOURCING
    # ============================================================
    required_mappings = {
        "kode_unik": ["Kode Unik (copy value dari FPTK)", "Kode Unik", "Unique Code"],
        "nama": ["Nama", "Nama Kandidat", "Candidate Name"],
        "sourcing_date": ["Sourcing Date", "Tanggal Sourcing", "Tgl Sourcing", "Date"],
        "sumber_sourcing": ["Sumber Sourcing", "Source", "Sourcing Source"],
        "rekruter": ["Rekruter", "Recruiter", "PIC Recruiter"],
        "posisi": ["Posisi", "Position"],
    }
    
    optional_mappings = {
        "model_rekrutmen": ["Model Rekrutmen", "Model", "Recruitment Model"],
        "jenjang_pendidikan": ["Jenjang Pendidikan", "Education Level"],
        "nama_universitas_top10": ["Nama Universitas/Sekolah (TOP 10)", "Universitas Top 10"],
        "nama_universitas_lainnya": ["Nama Universitas/Sekolah Lainnya", "Universitas Lainnya"],
        "jurusan": ["Jurusan", "Major"],
        "tahun_lulus": ["Tahun Lulus", "Graduation Year"],
        "ipk": ["IPK", "GPA"],
        "skor_bahasa_inggris": ["Skor Bahasa Inggris", "English Score"],
        "university_tier": ["University Tier", "Univ Tier"],
        "ipk_tier": ["IPK Tier", "GPA Tier"],
        "nomor_hp": ["Nomor HP", "No HP", "Phone"],
        "email": ["Email", "Email Address"],
        "domisili": ["Domisili", "Domicile", "Location"],
        "last_position": ["Last Position", "Posisi Terakhir"],
        "last_tenure": ["Last Tenure", "Tenure Terakhir"],
        "last_company": ["Last Company", "Company Terakhir"],
        "total_tenure": ["Total Tenure", "Total Experience"],
        "pernah_di_fmcg": ["Pernah di FMCG?", "FMCG", "FMCG Experience"],
        "sourcing_freelance": ["Sourcing Freelance", "Freelance Sourcing"],
        "tanggal_sourcing_freelance": ["Tanggal Sourcing Freelance", "Freelance Date"],
        "sourcing_hr": ["Sourcing HR", "HR Sourcing"],
        "detail_keterangan_sourcing_hr": ["Detail Keterangan Sourcing HR", "Detail Sourcing HR"],
        "tanggal_sourcing": ["Tanggal Sourcing", "Sourcing Date HR"],
        "shortlist_cv": ["Shortlist CV", "CV Shortlist"],
        "detail_keterangan_shortlist_cv": ["Detail Keterangan Shortlist CV", "Detail Shortlist"],
        "tanggal_shortlist_cv": ["Tanggal Shortlist CV", "Shortlist Date"],
        "psikotes": ["Psikotes", "Psycho Test"],
        "kode_psikotes": ["Kode Psikotes", "Psycho Code"],
        "detail_keterangan_psikotes": ["Detail Keterangan Psikotes", "Detail Psikotes"],
        "tanggal_psikotes": ["Tanggal Psikotes / Cek psikotes", "Tanggal Psikotes"],
        "nilai_logika": ["Nilai Logika", "Logic Score"],
        "nilai_iq": ["Nilai IQ", "IQ Score"],
        "nilai_daya_tangkap": ["Nilai Daya Tangkap", "Aptitude Score"],
        "nilai_ra": ["Nilai RA", "RA Score"],
        "disc": ["DISC", "DISC Profile"],
        "hr_interview": ["HR Interview", "HR Interview"],
        "detail_keterangan_hr_interview": ["Detail Keterangan HR Interview", "Detail HR Interview"],
        "tanggal_hr_interview": ["Tanggal HR Interview", "HR Interview Date"],
        "technical_test_case_study": ["Technical Test/ Case Study", "Technical Test"],
        "detail_keterangan_technical_test": ["Detail Keterangan Technical Test/ Case Study", "Detail Technical"],
        "tanggal_technical_test": ["Tanggal Technical Test/ Case Study", "Technical Date"],
        "market_visit": ["Market Visit", "Market Visit"],
        "detail_market_visit": ["Detail Market Visit", "Detail Market Visit"],
        "tanggal_market_visit": ["Tanggal Market Visit", "Market Visit Date"],
        "user_interview": ["User Interview", "User Interview"],
        "detail_keterangan_user_interview": ["Detail Keterangan User Interview", "Detail User Interview"],
        "tanggal_user_interview": ["Tanggal User Interview", "User Interview Date"],
        "panel_interview": ["Panel Interview", "Panel Interview"],
        "detail_keterangan_panel_interview": ["Detail Keterangan Panel Interview", "Detail Panel Interview"],
        "tanggal_panel_interview": ["Tanggal Panel Interview", "Panel Interview Date"],
        "reference_check": ["Reference Check", "Reference Check"],
        "detail_keterangan_reference_check": ["Detail Keterangan Reference Check", "Detail Reference Check"],
        "tanggal_reference_check": ["Tanggal Reference Check", "Reference Check Date"],
        "mcu": ["MCU", "MCU"],
        "detail_keterangan_mcu": ["Detail Keterangan MCU", "Detail MCU"],
        "tanggal_mcu": ["Tanggal MCU", "MCU Date"],
        "offering": ["Offering", "Offering"],
        "detail_keterangan_offering": ["Detail Keterangan Offering", "Detail Offering"],
        "tanggal_offering": ["Tanggal Offering", "Offering Date"],
        "notes": ["Notes", "Catatan"],
        "day1": ["Day 1", "Day One"],
        "detail_keterangan_day1": ["Detail Keterangan Day 1", "Detail Day 1"],
        "tanggal_day1": ["Tanggal Day 1", "Day 1 Date"],
    }
    
    # Pipeline status headers (V/X)
    pipeline_headers = [
        "sourcing_freelance", "sourcing_hr", "shortlist_cv", "psikotes",
        "hr_interview", "technical_test_case_study", "market_visit",
        "user_interview", "panel_interview", "reference_check",
        "mcu", "offering", "day1"
    ]
    
    # ============================================================
    # FIND COLUMN MAPPING
    # ============================================================
    all_mappings = {**required_mappings, **optional_mappings}
    column_mapping = find_column_mapping(df, all_mappings)
    
    # Cek kolom wajib yang hilang
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
                "error": f"Kolom wajib '{miss['field']}' tidak ditemukan",
                "expected": f"Coba salah satu nama: {', '.join(miss['possible'])}"
            })
        return False, errors
    
    # ============================================================
    # RENAME COLUMNS
    # ============================================================
    rename_map = {col: field_key for field_key, col in column_mapping.items()}
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # ============================================================
    # VALIDATE EACH ROW
    # ============================================================
    # Get existing Kode Unik mapping untuk cek duplikat
    existing_kode_unik = {}
    for record in db.query(DBSourcing.kode_unik, DBSourcing.nama).all():
        key = f"{record.kode_unik}|{record.nama}"
        existing_kode_unik[key] = True
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        # ============================================================
        # 1. VALIDATE SOURCING DATE (WAJIB)
        # ============================================================
        sourcing_date = row.get("sourcing_date")
        if pd.isna(sourcing_date):
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": "Sourcing Date WAJIB diisi",
                "expected": "Format tanggal DD/MM/YYYY atau YYYY-MM-DD",
                "example": "15/08/2026 atau 2026-08-15"
            })
        elif not _is_valid_date(sourcing_date):
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": f"Format tanggal '{sourcing_date}' tidak valid",
                "expected": "DD/MM/YYYY atau YYYY-MM-DD",
                "example": "15/08/2026 atau 2026-08-15"
            })
        
        # ============================================================
        # 2. VALIDATE KODE UNIK (WAJIB & HARUS ADA DI FPTK)
        # ============================================================
        kode_unik = row.get("kode_unik")
        if pd.isna(kode_unik) or str(kode_unik).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": kode_unik,
                "error": "Kode Unik WAJIB diisi",
                "expected": "Kode Unik yang valid dari FPTK",
                "example": "CORPOmeSales101024"
            })
        else:
            kode_unik_str = str(kode_unik).strip()
            # Cek apakah Kode Unik ada di FPTK
            fptk = db.query(FPTK).filter(FPTK.kode_unik == kode_unik_str).first()
            if not fptk:
                errors.append({
                    "row": row_num,
                    "field": "Kode Unik",
                    "value": kode_unik_str,
                    "error": f"Kode Unik '{kode_unik_str}' tidak ditemukan di database FPTK",
                    "expected": "Kode Unik harus sudah ada di FPTK",
                    "example": "Pastikan FPTK dengan Kode Unik tersebut sudah di-compile"
                })
            else:
                # Auto-fill posisi dari FPTK jika kosong
                if pd.isna(row.get("posisi")) or str(row.get("posisi")).strip() == "":
                    df.at[idx, "posisi"] = fptk.posisi
                    row["posisi"] = fptk.posisi
        
        # ============================================================
        # 3. VALIDATE NAMA (WAJIB)
        # ============================================================
        nama = row.get("nama")
        if pd.isna(nama) or str(nama).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Nama",
                "value": nama,
                "error": "Nama WAJIB diisi",
                "expected": "Nama kandidat minimal 3 karakter",
                "example": "Budi Santoso"
            })
        else:
            # Cek duplikat: Kode Unik + Nama yang sama
            key = f"{kode_unik}|{nama}" if not pd.isna(kode_unik) else f"|{nama}"
            if key in existing_kode_unik:
                errors.append({
                    "row": row_num,
                    "field": "Nama",
                    "value": nama,
                    "error": f"Data duplikat: Kode Unik '{kode_unik}' dengan Nama '{nama}' sudah ada",
                    "expected": "Kombinasi Kode Unik + Nama harus unik",
                    "example": "Cek apakah kandidat sudah pernah di-input"
                })
            else:
                existing_kode_unik[key] = True
        
        # ============================================================
        # 4. VALIDATE SOURCING DATE (WAJIB)
        # ============================================================
        if pd.isna(sourcing_date):
            errors.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date,
                "error": "Sourcing Date WAJIB diisi",
                "expected": "Format DD/MM/YYYY atau YYYY-MM-DD"
            })
        
        # ============================================================
        # 5. VALIDATE PIPELINE STATUS (V/X ONLY)
        # ============================================================
        for header in pipeline_headers:
            if header in df.columns:
                value = row.get(header)
                if not pd.isna(value) and str(value).strip() != "":
                    val_str = str(value).strip().upper()
                    if val_str not in ["V", "X", "YA", "TIDAK", "Y", "N", "YES", "NO", "TRUE", "FALSE", "1", "0"]:
                        # Warning: value tidak dikenal
                        pass
                    # Normalize ke V/X
                    if val_str in ["V", "YA", "Y", "YES", "TRUE", "1"]:
                        df.at[idx, header] = "V"
                    elif val_str in ["X", "TIDAK", "N", "NO", "FALSE", "0"]:
                        df.at[idx, header] = "X"
        
        # ============================================================
        # 6. VALIDATE EMAIL (OPTIONAL - IF FILLED, MUST BE VALID)
        # ============================================================
        email = row.get("email")
        if not pd.isna(email) and str(email).strip() != "":
            email_str = str(email).strip()
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_str):
                errors.append({
                    "row": row_num,
                    "field": "Email",
                    "value": email_str,
                    "error": f"Format email '{email_str}' tidak valid",
                    "expected": "Format email: nama@domain.com",
                    "example": "budi.santoso@company.com"
                })
        
        # ============================================================
        # 7. VALIDATE NOMOR HP (OPTIONAL - IF FILLED)
        # ============================================================
        hp = row.get("nomor_hp")
        if not pd.isna(hp) and str(hp).strip() != "":
            hp_str = str(hp).strip()
            hp_clean = re.sub(r'[^0-9+]', '', hp_str)
            if len(hp_clean) < 10 or len(hp_clean) > 15:
                errors.append({
                    "row": row_num,
                    "field": "Nomor HP",
                    "value": hp_str,
                    "error": f"Nomor HP '{hp_str}' tidak valid",
                    "expected": "Minimal 10 digit, maksimal 15 digit",
                    "example": "081234567890 atau +6281234567890"
                })
    
    # ============================================================
    # SUMMARY
    # ============================================================
    if errors:
        error_count = len(errors)
        unique_rows = len(set(e["row"] for e in errors if e["row"] > 0))
        errors = [e for e in errors if e.get("field") != "SUMMARY"]
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada {unique_rows} baris data sourcing",
            "expected": f"Semua {len(df)} baris harus valid",
            "example": "Perbaiki error di bawah ini"
        })
        return False, errors
    
    return True, []


# ============================================================
# 2. VALIDATOR BLACKLIST CANDIDATE
# ============================================================

def validate_blacklist_file(
    df: pd.DataFrame,
    db,
    user_id: int,
    cycle_id: int = None
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file Blacklist Candidate:
    - Kolom A (key) WAJIB
    - Key harus unik (tidak boleh duplikat)
    """
    errors = []
    
    if df.empty:
        errors.append({
            "row": 0,
            "field": "file",
            "value": "",
            "error": "File kosong",
            "expected": "Minimal 1 baris data blacklist"
        })
        return False, errors
    
    # ============================================================
    # AMBIL KOLOM PERTAMA (KEY)
    # ============================================================
    first_col = df.columns[0]
    
    # Get existing keys
    existing_keys = set()
    for record in db.query(Blacklist.key_value).all():
        existing_keys.add(normalize_key(record.key_value))
    
    seen_keys = set()
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        key_value = row.iloc[0] if len(row) > 0 else None
        
        if pd.isna(key_value) or str(key_value).strip() == "":
            errors.append({
                "row": row_num,
                "field": "Key",
                "value": key_value,
                "error": "Key tidak boleh kosong",
                "expected": "Key harus diisi",
                "example": "NIK atau nama lengkap"
            })
        else:
            key_norm = normalize_key(key_value)
            
            # Cek duplikat dalam file
            if key_norm in seen_keys:
                errors.append({
                    "row": row_num,
                    "field": "Key",
                    "value": key_value,
                    "error": f"Duplikat key '{key_value}' dalam file",
                    "expected": "Key harus unik dalam file",
                    "example": "Hapus baris duplikat"
                })
            else:
                seen_keys.add(key_norm)
            
            # Cek duplikat di database
            if key_norm in existing_keys:
                errors.append({
                    "row": row_num,
                    "field": "Key",
                    "value": key_value,
                    "error": f"Key '{key_value}' sudah ada di database",
                    "expected": "Key harus unik",
                    "example": "Key sudah terdaftar sebagai blacklist"
                })
            else:
                existing_keys.add(key_norm)
    
    if errors:
        error_count = len(errors)
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada file blacklist",
            "expected": "Semua key harus unik dan tidak boleh kosong"
        })
        return False, errors
    
    return True, []


# ============================================================
# 3. VALIDATOR DB KODE POSISI
# ============================================================

def validate_db_kode_posisi_file(
    df: pd.DataFrame,
    db,
    user_id: int,
    cycle_id: int = None
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file DB Kode Posisi:
    - POSITION WAJIB
    - LOCATION WAJIB
    - BUSINESS UNIT WAJIB
    - Key = POSITION + LOCATION + BUSINESS UNIT (harus unik)
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
    
    # ============================================================
    # REQUIRED COLUMNS MAPPING
    # ============================================================
    required_mappings = {
        "position": ["POSITION", "Position", "Posisi"],
        "location": ["LOCATION", "Location", "Lokasi"],
        "business_unit": ["BUSINESS UNIT", "Business Unit", "BU"],
    }
    
    optional_mappings = {
        "kode": ["KODE", "Kode", "Kode Angka"],
        "division_chris": ["DIVISION CHRIS", "Division Chris", "Divisi"],
        "department_chris": ["DEPARTMENT CHRIS", "Department Chris", "Departemen"],
        "user_manager": ["USER (MANAGER)", "User Manager", "User"],
        "indirect_user": ["INDIRECT USER", "Indirect User", "Indirect"],
        "directorate": ["DIRECTORATE", "Directorate", "Direktorat"],
        "year": ["YEAR", "Year", "Tahun"],
    }
    
    # ============================================================
    # FIND COLUMN MAPPING
    # ============================================================
    all_mappings = {**required_mappings, **optional_mappings}
    column_mapping = find_column_mapping(df, all_mappings)
    
    # Cek kolom wajib yang hilang
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
                "error": f"Kolom wajib '{miss['field']}' tidak ditemukan",
                "expected": f"Coba salah satu nama: {', '.join(miss['possible'])}"
            })
        return False, errors
    
    # ============================================================
    # RENAME COLUMNS
    # ============================================================
    rename_map = {col: field_key for field_key, col in column_mapping.items()}
    for col in df.columns:
        if col in rename_map:
            df.rename(columns={col: rename_map[col]}, inplace=True)
    
    # ============================================================
    # GET EXISTING KEYS
    # ============================================================
    existing_keys = set()
    for record in db.query(DBKodePosisi.position, DBKodePosisi.location, DBKodePosisi.business_unit).all():
        key = normalize_key(f"{record.position}|{record.location}|{record.business_unit}")
        existing_keys.add(key)
    
    seen_keys = set()
    
    # ============================================================
    # VALIDATE EACH ROW
    # ============================================================
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        position = row.get("position")
        location = row.get("location")
        business_unit = row.get("business_unit")
        
        # ============================================================
        # 1. VALIDATE POSITION (WAJIB)
        # ============================================================
        if pd.isna(position) or str(position).strip() == "":
            errors.append({
                "row": row_num,
                "field": "POSITION",
                "value": position,
                "error": "POSITION tidak boleh kosong",
                "expected": "Nama posisi minimal 3 karakter",
                "example": "Area Sales Supervisor"
            })
        
        # ============================================================
        # 2. VALIDATE LOCATION (WAJIB)
        # ============================================================
        if pd.isna(location) or str(location).strip() == "":
            errors.append({
                "row": row_num,
                "field": "LOCATION",
                "value": location,
                "error": "LOCATION tidak boleh kosong",
                "expected": "Lokasi (contoh: Jakarta, Bandung, Surabaya)",
                "example": "Jakarta"
            })
        
        # ============================================================
        # 3. VALIDATE BUSINESS UNIT (WAJIB)
        # ============================================================
        if pd.isna(business_unit) or str(business_unit).strip() == "":
            errors.append({
                "row": row_num,
                "field": "BUSINESS UNIT",
                "value": business_unit,
                "error": "BUSINESS UNIT tidak boleh kosong",
                "expected": "Business Unit (CORP, CMD, MS, JESS, MP, MB, BHC, ARC)",
                "example": "CMD"
            })
        
        # ============================================================
        # 4. VALIDATE UNIQUE KEY (POSITION + LOCATION + BU)
        # ============================================================
        if position and location and business_unit:
            key = normalize_key(f"{position}|{location}|{business_unit}")
            
            if key in seen_keys:
                errors.append({
                    "row": row_num,
                    "field": "KEY",
                    "value": f"{position}|{location}|{business_unit}",
                    "error": "Duplikat kombinasi POSITION + LOCATION + BUSINESS UNIT",
                    "expected": "Kombinasi harus unik",
                    "example": "Perbaiki salah satu field"
                })
            elif key in existing_keys:
                errors.append({
                    "row": row_num,
                    "field": "KEY",
                    "value": f"{position}|{location}|{business_unit}",
                    "error": f"Kombinasi POSITION + LOCATION + BUSINESS UNIT sudah ada di database",
                    "expected": "Kombinasi harus unik",
                    "example": "Gunakan POSITION/LOCATION/BU yang berbeda"
                })
            else:
                seen_keys.add(key)
        
        # ============================================================
        # 5. VALIDATE YEAR (OPTIONAL - IF FILLED MUST BE 4 DIGIT)
        # ============================================================
        year = row.get("year")
        if not pd.isna(year):
            try:
                year_int = int(year)
                if year_int < 1900 or year_int > 2100:
                    errors.append({
                        "row": row_num,
                        "field": "YEAR",
                        "value": year,
                        "error": f"Tahun '{year}' tidak valid",
                        "expected": "Tahun antara 1900-2100",
                        "example": "2026"
                    })
            except (ValueError, TypeError):
                errors.append({
                    "row": row_num,
                    "field": "YEAR",
                    "value": year,
                    "error": f"YEAR '{year}' harus angka",
                    "expected": "Format angka 4 digit",
                    "example": "2026"
                })
    
    # ============================================================
    # SUMMARY
    # ============================================================
    if errors:
        error_count = len(errors)
        errors = [e for e in errors if e.get("field") != "SUMMARY"]
        errors.insert(0, {
            "row": 0,
            "field": "SUMMARY",
            "value": "",
            "error": f"Total {error_count} error pada DB Kode Posisi",
            "expected": "Semua POSITION, LOCATION, BUSINESS UNIT harus diisi dan unik",
            "example": "Perbaiki error di bawah"
        })
        return False, errors
    
    return True, []


# ============================================================
# 4. FPTK VALIDATOR (YANG SUDAH ADA - DIUPDATE)
# ============================================================

def validate_fptk_file(
    df: pd.DataFrame,
    db,
    user_id: int,
    is_sto: bool = False
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validasi file FPTK dengan strict rules dari VBA.
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
    
    # ============================================================
    # REQUIRED COLUMNS MAPPING - FPTK
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
        "level_number": ["Level Number", "Level FPTK Number"],
        "alasan_permintaan_fptk": ["Alasan Permintaan FPTK", "Alasan FPTK", "Reason FPTK"],
        "category_fptk": ["Category FPTK", "Kategori FPTK", "Category"],
        "pic_recruiter": ["PIC Recruiter", "PIC Rekruter", "Recruiter"],
        "vacancy": ["Vacancy", "Jumlah Posisi", "Jumlah FPTK"],
        "status": ["Status", "FPTK Status"],
    }
    
    optional_mappings = {
        "fptk_date_kode": ["FPTK Date (Kode)", "FPTK DATE (Kode)", "FPTK Date Kode"],
        "kode_angka": ["Kode Angka", "Kode Angka FPTK"],
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
        "detail_sla": ["Detail SLA
