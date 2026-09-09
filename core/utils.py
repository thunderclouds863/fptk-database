# core/compiler.py

import pandas as pd
import math
import re
import hashlib
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from core.models import (
    FPTK,
    DBSourcing,
    DBKodePosisi,
    UploadLog
)
from core.utils import (
    safe_int, 
    safe_float, 
    safe_string, 
    safe_boolean_char, 
    safe_date,
    sanitize_date_value, 
    calculate_detail_sla, 
    calculate_sla_days,
    parse_date_dmy,
    normalize_text,
    get_single_value
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_string_for_db(value, default='', max_length=None):
    """Safely convert to string with truncation."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, pd.Series):
        return safe_string_for_db(value.iloc[0], default, max_length) if len(value) > 0 else default
    if isinstance(value, (list, tuple)):
        return safe_string_for_db(value[0], default, max_length) if len(value) > 0 else default
    if isinstance(value, str):
        result = value.strip()
    elif isinstance(value, (int, float)):
        result = str(value)
    else:
        result = str(value) if value is not None else default
    
    if max_length is not None and len(result) > max_length:
        result = result[:max_length]
    
    return result


def safe_numeric_value(value, default=None):
    """Safely convert to numeric or None."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, pd.Series):
        return safe_numeric_value(value.iloc[0], default) if len(value) > 0 else default
    if isinstance(value, str):
        v = value.strip().upper()
        if v in ['V', 'X', 'Y', 'N', 'YES', 'NO', 'TRUE', 'FALSE']:
            return default
        v = v.replace(',', '.').replace(' ', '')
        v = re.sub(r'[^\d.]', '', v)
        if not v:
            return default
        try:
            return float(v)
        except ValueError:
            return default
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return default
        return float(value)
    return default


def safe_int_value(value, default=None):
    """Safely convert to integer or None."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, pd.Series):
        return safe_int_value(value.iloc[0], default) if len(value) > 0 else default
    if isinstance(value, str):
        v = value.strip().upper()
        if v in ['V', 'X', 'Y', 'N', 'YES', 'NO', 'TRUE', 'FALSE']:
            return default
        v = re.sub(r'[^\d]', '', v)
        if not v:
            return default
        try:
            return int(v)
        except ValueError:
            return default
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return default
        return int(value)
    return default


def get_boolean_value(val):
    """Convert to 'V' or 'X' or None."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, bool):
        return 'V' if val else 'X'
    if isinstance(val, (int, float)):
        return 'V' if val else 'X'
    if isinstance(val, str):
        v = val.strip().upper()
        if v in ['V', 'Y', 'YA', 'YES', 'TRUE', '1']:
            return 'V'
        if v in ['X', 'N', 'NO', 'FALSE', '0']:
            return 'X'
        return None
    return None


def safe_level_number(value):
    """Ambil angka dari level_number, handle string seperti 'STO Chilled'"""
    if value is None or pd.isna(value):
        return 1
    
    if isinstance(value, (int, float)):
        try:
            int_val = int(value)
            if 1 <= int_val <= 5:
                return int_val
            return 1
        except:
            return 1
    
    if isinstance(value, str):
        match = re.search(r'(\d+)', value)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 5:
                return num
        return 1
    
    return 1


def safe_level_fptk(value):
    """Pastikan level_fptk formatnya 1A-5B"""
    if value is None or pd.isna(value):
        return "1A"
    
    value_str = str(value).strip().upper()
    
    if re.match(r'^[1-5][A-B]$', value_str):
        return value_str
    
    match = re.search(r'(\d+)', value_str)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 5:
            return f"{num}A"
    
    return "1A"


# ============================================================
# SAFE DATE FALLBACK - HANDLE NaT
# ============================================================

def safe_date_fallback(value):
    """
    Safe date conversion with NaT handling.
    Returns None for NaT, NaN, None, or invalid values.
    """
    if value is None:
        return None
    
    # CEK NaT (Pandas Not a Time)
    try:
        if pd.isna(value):
            return None
    except:
        pass
    
    if hasattr(value, '__class__') and 'NaT' in str(value.__class__):
        return None
    
    if isinstance(value, str) and value.upper() == 'NAT':
        return None
    
    if isinstance(value, float) and math.isnan(value):
        return None
    
    if isinstance(value, datetime):
        return value.date()
    
    if isinstance(value, date):
        return value
    
    if isinstance(value, pd.Timestamp):
        try:
            if pd.isna(value):
                return None
        except:
            pass
        return value.date()
    
    if isinstance(value, str):
        return parse_date_dmy(value)
    
    return None


# ============================================================
# COMPILE FPTK
# ============================================================

def compile_fptk(db: Session, rows_or_df, user_id: int, cycle_id: int,
                 file_name: str, file_bytes: bytes, is_sto: bool = False):
    """
    Compile FPTK dari rows (list of dict) atau DataFrame.
    """
    if isinstance(rows_or_df, list):
        df = pd.DataFrame(rows_or_df)
    else:
        df = rows_or_df

    file_hash = hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""

    imported = 0
    updated = 0
    skipped = 0
    errors = []

    if df.empty:
        return {"success": False, "imported": 0, "updated": 0, "skipped": 0, "errors": ["Tidak ada data valid"]}

    for idx, row in df.iterrows():
        row_num = idx + 2

        kode_unik = safe_string_for_db(row.get('kode_unik', ''), max_length=100)
        posisi = safe_string_for_db(row.get('posisi', ''), max_length=500)
        status = safe_string_for_db(row.get('status', ''), max_length=50)

        fptk_date_real = safe_date(row.get('fptk_date_real'))
        offering_date = safe_date(row.get('offering_date'))
        fptk_cancel_date = safe_date(row.get('fptk_cancel_date'))
        deadline_sla_input = safe_date(row.get('deadline_sla'))

        if not kode_unik or not posisi:
            skipped += 1
            continue

        existing = db.query(FPTK).filter(
            FPTK.kode_unik == kode_unik,
            FPTK.posisi == posisi
        ).first()

        raw_level_number = row.get('level_number')
        level_num = safe_level_number(raw_level_number)
        
        if level_num == 1:
            raw_level_fptk = row.get('level_fptk')
            if raw_level_fptk:
                match = re.search(r'(\d+)', str(raw_level_fptk))
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 5:
                        level_num = num

        raw_level_fptk = row.get('level_fptk')
        level_fptk = safe_level_fptk(raw_level_fptk)
        
        if level_fptk == "1A" and level_num > 1:
            level_fptk = f"{level_num}A"

        sla_days = calculate_sla_days(level_num)

        if fptk_date_real:
            if isinstance(fptk_date_real, date):
                deadline_sla = fptk_date_real + timedelta(days=sla_days)
            elif isinstance(fptk_date_real, datetime):
                deadline_sla = fptk_date_real.date() + timedelta(days=sla_days)
            else:
                deadline_sla = deadline_sla_input
        else:
            deadline_sla = deadline_sla_input

        if deadline_sla and isinstance(deadline_sla, datetime):
            deadline_sla = deadline_sla.date()
        if offering_date and isinstance(offering_date, datetime):
            offering_date = offering_date.date()
        if fptk_cancel_date and isinstance(fptk_cancel_date, datetime):
            fptk_cancel_date = fptk_cancel_date.date()
        if fptk_date_real and isinstance(fptk_date_real, datetime):
            fptk_date_real = fptk_date_real.date()

        detail_sla = calculate_detail_sla(
            status=status,
            deadline_sla=deadline_sla,
            offering_date=offering_date
        )

        week_num = fptk_date_real.isocalendar()[1] if fptk_date_real else None
        month_name = fptk_date_real.strftime("%B") if fptk_date_real else None
        kode_bu = safe_string_for_db(row.get('kode_pic', ''), max_length=50)[:4] if row.get('kode_pic') else ''

        filter_kat = safe_string_for_db(row.get('filter_kategorisasi_fptk', ''), max_length=100)
        
        posisi_lower = posisi.lower()
        if not filter_kat:
            if posisi_lower.startswith('cimory') or posisi_lower.startswith('fresh'):
                filter_kat = 'CLAP FGDP'
            elif level_num in [1, 2]:
                filter_kat = 'Level 1-2'
            elif level_num == 3:
                filter_kat = 'Level 3'
            elif level_num == 4:
                filter_kat = 'Level 4'

        avail = get_boolean_value(row.get('fptk_availability', ''))

        jumlah_sla = safe_int_value(row.get('jumlah_sla'), sla_days)
        vacancy = safe_int_value(row.get('vacancy'), 1)
        level_number = int(level_num) if level_num else 1

        if existing:
            existing.kode_pic = safe_string_for_db(row.get('kode_pic'), max_length=50)
            existing.fptk_date_real = fptk_date_real
            existing.fptk_date_kode = fptk_date_real
            existing.posisi = posisi
            existing.business_unit = safe_string_for_db(row.get('business_unit'), max_length=100)
            existing.direktorat = safe_string_for_db(row.get('direktorat'), max_length=100)
            existing.divisi = safe_string_for_db(row.get('divisi'), max_length=100)
            existing.department = safe_string_for_db(row.get('department'), max_length=100)
            existing.level_fptk = level_fptk
            existing.level_number = level_number
            existing.alasan_permintaan_fptk = safe_string_for_db(row.get('alasan_permintaan_fptk'), max_length=200)
            existing.category_fptk = safe_string_for_db(row.get('category_fptk'), max_length=100)
            existing.pic_recruiter = safe_string_for_db(row.get('pic_recruiter'), max_length=100)
            existing.vacancy = vacancy
            existing.status = status
            existing.offering_date = offering_date
            existing.fptk_cancel_date = fptk_cancel_date
            existing.jumlah_sla = jumlah_sla
            existing.deadline_sla = deadline_sla
            existing.detail_sla = detail_sla
            existing.week_fptk_date = week_num
            existing.month_fptk_date = month_name
            existing.kode_bu = kode_bu
            existing.filter_kategorisasi_fptk = filter_kat
            existing.fptk_availability = avail
            existing.is_sto = is_sto
            existing.last_updated_at = datetime.now()
            existing.last_compile_action = "UPDATE"
            existing.source_user_id = user_id
            existing.source_cycle_id = cycle_id
            existing.source_file = safe_string_for_db(file_name, max_length=255)
            existing.source_file_hash = file_hash
            existing.is_sto = is_sto
            updated += 1
        else:
            kode_angka = row.get('kode_angka')
            if pd.isna(kode_angka) or not kode_angka:
                kode_angka = (safe_string_for_db(row.get('kode_pic', ''), max_length=50)[:4] + str(vacancy))

            new_fptk = FPTK(
                kode_unik=kode_unik,
                posisi=posisi,
                kode_pic=safe_string_for_db(row.get('kode_pic'), max_length=50),
                fptk_date_real=fptk_date_real,
                fptk_date_kode=fptk_date_real,
                kode_angka=safe_string_for_db(kode_angka, max_length=50),
                business_unit=safe_string_for_db(row.get('business_unit'), max_length=100),
                direktorat=safe_string_for_db(row.get('direktorat'), max_length=100),
                divisi=safe_string_for_db(row.get('divisi'), max_length=100),
                department=safe_string_for_db(row.get('department'), max_length=100),
                level_fptk=level_fptk,
                level_number=level_number,
                alasan_permintaan_fptk=safe_string_for_db(row.get('alasan_permintaan_fptk'), max_length=200),
                category_fptk=safe_string_for_db(row.get('category_fptk'), max_length=100),
                pic_recruiter=safe_string_for_db(row.get('pic_recruiter'), max_length=100),
                filter_kategorisasi_fptk=filter_kat,
                vacancy=vacancy,
                status=status,
                offering_date=offering_date,
                fptk_cancel_date=fptk_cancel_date,
                jumlah_sla=jumlah_sla,
                deadline_sla=deadline_sla,
                detail_sla=detail_sla,
                week_fptk_date=week_num,
                month_fptk_date=month_name,
                kode_bu=kode_bu,
                fptk_availability=avail,
                source_user_id=user_id,
                source_cycle_id=cycle_id,
                source_file=safe_string_for_db(file_name, max_length=255),
                source_file_hash=file_hash,
                is_sto=is_sto,
                created_at=datetime.now(),
                last_compile_action="INSERT"
            )
            db.add(new_fptk)
            imported += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(str(e))
        return {"success": False, "imported": 0, "updated": 0, "skipped": 0, "errors": [str(e)]}

    log = UploadLog(
        cycle_id=cycle_id,
        user_id=user_id,
        file_name=safe_string_for_db(file_name, max_length=255),
        file_size_bytes=len(file_bytes) if file_bytes else 0,
        file_hash=file_hash,
        status="SUCCESS" if not errors else "PARTIAL",
        record_count=imported + updated,
        error_details="\n".join(errors) if errors else f"Imported: {imported}, Updated: {updated}, Skipped: {skipped}"
    )
    db.add(log)
    db.commit()

    return {
        "success": True,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors
    }


# ============================================================
# COMPILE DB SOURCING - DIPERBAIKI DENGAN NaT HANDLING
# ============================================================

def compile_db_sourcing(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                        file_name: str, file_hash: str):
    """
    Compile DB Sourcing dari uploaded file.
    - TETAP SIMPAN data meskipun ada warning
    - NaT otomatis diganti dengan None atau date.today()
    """
    from core.validator import validate_db_sourcing_file
    
    errors = []
    imported = 0
    updated = 0
    warnings = []
    
    if db.is_active:
        db.rollback()
    
    # ============================================================
    # VALIDASI - TAPI TIDAK LANGSUNG RETURN
    # ============================================================
    valid_rows, val_errors = validate_db_sourcing_file(df, db, user_id)
    
    # Pisahkan warning dan error kritis
    critical_errors = []
    for err in val_errors:
        if err.get("warning", False):
            warnings.append(err)
        elif err.get("field") == "SUMMARY":
            continue
        else:
            critical_errors.append(err)
    
    real_critical = []
    for err in critical_errors:
        if err.get("field") == "Sourcing Date" and "kosong" in str(err.get("error", "")):
            warnings.append(err)
        else:
            real_critical.append(err)
    
    if real_critical:
        db.rollback()
        return {
            "success": False,
            "imported": 0,
            "updated": 0,
            "errors": real_critical,
            "warnings": warnings
        }
    
    if isinstance(valid_rows, pd.DataFrame):
        df = valid_rows.copy()
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        kode_unik = safe_string_for_db(row.get('kode_unik', ''), max_length=100)
        nama = safe_string_for_db(row.get('nama', ''), max_length=255)
        
        # ============================================================
        # PERBAIKAN: SOURCING DATE - DETEKSI NaT SECARA MANUAL
        # ============================================================
        sourcing_date_raw = row.get('sourcing_date')
        
        # CEK NaT SECARA MANUAL
        is_nat = False
        if sourcing_date_raw is not None:
            # Cek dengan pd.isna
            try:
                if pd.isna(sourcing_date_raw):
                    is_nat = True
            except:
                pass
            
            # Cek class name
            if hasattr(sourcing_date_raw, '__class__'):
                class_name = str(sourcing_date_raw.__class__)
                if 'NaT' in class_name or 'nat' in class_name.lower():
                    is_nat = True
            
            # Cek string
            if isinstance(sourcing_date_raw, str) and sourcing_date_raw.upper() == 'NAT':
                is_nat = True
        
        # Jika NaT, None, atau kosong → pakai tanggal hari ini
        if is_nat or sourcing_date_raw is None:
            sourcing_date = datetime.now().date()
            warnings.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": str(sourcing_date_raw),
                "warning": True,
                "error": f"Sourcing Date NaT/kosong, otomatis diisi {sourcing_date.strftime('%d/%m/%Y')}"
            })
        else:
            # Coba parse
            try:
                parsed = safe_date(sourcing_date_raw)
                if parsed:
                    sourcing_date = parsed
                else:
                    sourcing_date = datetime.now().date()
                    warnings.append({
                        "row": row_num,
                        "field": "Sourcing Date",
                        "value": str(sourcing_date_raw),
                        "warning": True,
                        "error": f"Format Sourcing Date tidak valid, otomatis diisi {sourcing_date.strftime('%d/%m/%Y')}"
                    })
            except:
                sourcing_date = datetime.now().date()
                warnings.append({
                    "row": row_num,
                    "field": "Sourcing Date",
                    "value": str(sourcing_date_raw),
                    "warning": True,
                    "error": f"Error parsing Sourcing Date, otomatis diisi {sourcing_date.strftime('%d/%m/%Y')}"
                })
        
        # ============================================================
        # CEK KODE UNIK
        # ============================================================
        if not kode_unik:
            kode_unik = f"UNKNOWN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}"
            warnings.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": row.get('kode_unik'),
                "warning": True,
                "error": f"Kode Unik kosong, auto-generated: {kode_unik}"
            })
        
        if not nama:
            warnings.append({
                "row": row_num,
                "field": "Nama",
                "value": nama,
                "warning": True,
                "error": "Nama kosong, row di-skip"
            })
            continue
        
        try:
            existing = db.query(DBSourcing).filter(
                DBSourcing.kode_unik == kode_unik,
                DBSourcing.nama == nama
            ).first()
            
            # ============================================================
           
