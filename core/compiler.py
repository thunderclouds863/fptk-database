# core/compiler.py

import pandas as pd
import math
import re
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from core.models import (
    FPTK,
    DBSourcing,
    DBKodePosisi,
    Blacklist,
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
    normalize_text
)
import hashlib


def safe_value_for_db(value, default=None):
    """
    Safely convert ANY value to a database-compatible value.
    This handles pandas NaN, numpy NaN, and other edge cases.
    """
    if value is None:
        return default
    
    # Handle pandas NaN
    if isinstance(value, float) and math.isnan(value):
        return default
    
    # Handle pandas Series
    if isinstance(value, pd.Series):
        if len(value) > 0:
            return safe_value_for_db(value.iloc[0], default)
        return default
    
    # Handle numpy arrays
    if isinstance(value, (list, tuple)):
        if len(value) > 0:
            return safe_value_for_db(value[0], default)
        return default
    
    # Handle pandas Timestamp
    if isinstance(value, pd.Timestamp):
        return value.date()
    
    # Handle datetime
    if isinstance(value, datetime):
        return value
    
    # Handle date
    if isinstance(value, date):
        return value
    
    # Handle string
    if isinstance(value, str):
        return value.strip() if value.strip() else default
    
    # Handle numeric
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return default
        return value
    
    return str(value) if value is not None else default


def safe_string_for_db(value, default='', max_length=None):
    """
    Safely convert to string for database storage with optional truncation.
    
    Args:
        value: Nilai yang akan di-convert
        default: Nilai default jika value invalid
        max_length: Maksimal panjang string (None = tidak dibatasi)
    """
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
    
    # Truncate if max_length is specified
    if max_length is not None and len(result) > max_length:
        result = result[:max_length]
    
    return result


def get_string_value(row, field, max_length=None, default=''):
    """
    Get string value from row with truncation support.
    
    Args:
        row: Dictionary or Series
        field: Field name
        max_length: Max length for truncation
        default: Default value if empty
    """
    val = row.get(field)
    return safe_string_for_db(val, default, max_length)


def safe_numeric_value(value, default=None):
    """Safely convert ANY value to a proper numeric (int/float) or None."""
    if value is None:
        return default
    
    if isinstance(value, float) and math.isnan(value):
        return default
    
    if isinstance(value, pd.Series):
        return safe_numeric_value(value.iloc[0], default) if len(value) > 0 else default
    
    if isinstance(value, str):
        v = value.strip().upper()
        # If it's a status value (V/X/Y/N), return None
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
    """Safely convert to integer or None"""
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
    """Convert to 'V' or 'X' or None"""
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


def compile_fptk(db: Session, rows_or_df, user_id: int, cycle_id: int,
                 file_name: str, file_bytes: bytes, is_sto: bool = False):
    """Compile FPTK dari rows (list of dict) atau DataFrame."""
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


def compile_db_sourcing(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                        file_name: str, file_hash: str):
    """
    Compile DB Sourcing dari uploaded file.
    
    CRITICAL FIX: Semua nilai di-truncate sesuai batas kolom database.
    """
    from core.validator import validate_db_sourcing_file
    
    errors = []
    imported = 0
    updated = 0
    
    # Clear any pending transaction before starting
    if db.is_active:
        db.rollback()
    
    valid_rows, val_errors = validate_db_sourcing_file(
        df,
        db,
        user_id
    )
    
    if val_errors:
        return {
            "success": False,
            "imported": 0,
            "errors": val_errors
        }
    
    # PAKAI DATA YANG SUDAH VALIDATED
    if isinstance(valid_rows, pd.DataFrame):
        df = valid_rows.copy()
    
    for idx, row in df.iterrows():
        kode_unik = safe_string_for_db(row.get('kode_unik', ''), max_length=100)
        nama = safe_string_for_db(row.get('nama', ''), max_length=255)
        
        if not kode_unik or not nama:
            continue
        
        try:
            # Cek existing (optional, untuk update)
            existing = db.query(DBSourcing).filter(
                DBSourcing.kode_unik == kode_unik,
                DBSourcing.nama == nama
            ).first()
            
            sourcing_date = safe_date(row.get('sourcing_date'))
            if not sourcing_date:
                sourcing_date = datetime.now().date()
            
            # ============================================================
            # SAFE CONVERSIONS - WITH TRUNCATION
            # ============================================================
            
            # --- NUMERIC FIELDS ---
            no_val = safe_int_value(row.get('no'), imported + 1)
            tahun_lulus_val = safe_int_value(row.get('tahun_lulus'))
            ipk_val = safe_numeric_value(row.get('ipk'))
            
            # --- STRING FIELDS - WITH PROPER MAX LENGTH ---
            # VARCHAR(255)
            posisi_val = safe_string_for_db(row.get('posisi'), max_length=255)
            nama_univ_top10_val = safe_string_for_db(row.get('nama_universitas_top10'), max_length=255)
            nama_univ_lain_val = safe_string_for_db(row.get('nama_universitas_lainnya'), max_length=255)
            email_val = safe_string_for_db(row.get('email'), max_length=255)
            last_position_val = safe_string_for_db(row.get('last_position'), max_length=255)
            last_company_val = safe_string_for_db(row.get('last_company'), max_length=255)
            
            # VARCHAR(100)
            model_rekrutmen_val = safe_string_for_db(row.get('model_rekrutmen'), max_length=100)
            rekruter_val = safe_string_for_db(row.get('rekruter'), max_length=100)
            sumber_sourcing_val = safe_string_for_db(row.get('sumber_sourcing'), max_length=100)
            jurusan_val = safe_string_for_db(row.get('jurusan'), max_length=100)
            domisili_val = safe_string_for_db(row.get('domisili'), max_length=100)
            
            # VARCHAR(50)
            jenjang_val = safe_string_for_db(row.get('jenjang_pendidikan'), max_length=50)
            skor_inggris_val = safe_string_for_db(row.get('skor_bahasa_inggris'), max_length=50)
            last_tenure_val = safe_string_for_db(row.get('last_tenure'), max_length=50)
            total_tenure_val = safe_string_for_db(row.get('total_tenure'), max_length=50)
            
            # CRITICAL: VARCHAR(20) - THESE ARE THE PROBLEM CHILDREN!
            university_tier_val = safe_string_for_db(row.get('university_tier'), max_length=20)
            ipk_tier_val = safe_string_for_db(row.get('ipk_tier'), max_length=20)
            
            # VARCHAR(20) - NOMOR HP
            nomor_hp_val = safe_string_for_db(row.get('nomor_hp'), max_length=20)
            
            # VARCHAR(10) - PERNAH DI FMCG
            pernah_di_fmcg_val = safe_string_for_db(row.get('pernah_di_fmcg'), max_length=10)
            
            # ============================================================
            # BOOLEAN-LIKE FIELDS (V/X) - VARCHAR(3)
            # ============================================================
            sourcing_hr_val = get_boolean_value(row.get('sourcing_hr'))
            shortlist_cv_val = get_boolean_value(row.get('shortlist_cv'))
            psikotes_val = get_boolean_value(row.get('psikotes'))
            hr_interview_val = get_boolean_value(row.get('hr_interview'))
            user_interview_val = get_boolean_value(row.get('user_interview'))
            offering_val = get_boolean_value(row.get('offering'))
            day1_val = get_boolean_value(row.get('day1'))
            
            if existing:
                # Update existing record
                existing.no = no_val
                existing.sourcing_date = sourcing_date
                existing.kode_unik = kode_unik
                existing.posisi = posisi_val
                existing.model_rekrutmen = model_rekrutmen_val
                existing.rekruter = rekruter_val
                existing.sumber_sourcing = sumber_sourcing_val
                existing.nama = nama
                existing.nama_universitas_top10 = nama_univ_top10_val
                existing.nama_universitas_lainnya = nama_univ_lain_val
                existing.jenjang_pendidikan = jenjang_val
                existing.jurusan = jurusan_val
                existing.tahun_lulus = tahun_lulus_val
                existing.ipk = ipk_val
                existing.skor_bahasa_inggris = skor_inggris_val
                existing.university_tier = university_tier_val
                existing.ipk_tier = ipk_tier_val
                existing.nomor_hp = nomor_hp_val
                existing.email = email_val
                existing.domisili = domisili_val
                existing.last_position = last_position_val
                existing.last_company = last_company_val
                existing.last_tenure = last_tenure_val
                existing.total_tenure = total_tenure_val
                existing.pernah_di_fmcg = pernah_di_fmcg_val
                existing.sourcing_hr = sourcing_hr_val
                existing.shortlist_cv = shortlist_cv_val
                existing.psikotes = psikotes_val
                existing.hr_interview = hr_interview_val
                existing.user_interview = user_interview_val
                existing.offering = offering_val
                existing.day1 = day1_val
                existing.last_updated_at = datetime.now()
                existing.last_compile_action = "UPDATE"
                updated += 1
            else:
                # Insert new record
                new_sourcing = DBSourcing(
                    no=no_val,
                    sourcing_date=sourcing_date,
                    kode_unik=kode_unik,
                    posisi=posisi_val,
                    model_rekrutmen=model_rekrutmen_val,
                    rekruter=rekruter_val,
                    sumber_sourcing=sumber_sourcing_val,
                    nama=nama,
                    nama_universitas_top10=nama_univ_top10_val,
                    nama_universitas_lainnya=nama_univ_lain_val,
                    jenjang_pendidikan=jenjang_val,
                    jurusan=jurusan_val,
                    tahun_lulus=tahun_lulus_val,
                    ipk=ipk_val,
                    skor_bahasa_inggris=skor_inggris_val,
                    university_tier=university_tier_val,
                    ipk_tier=ipk_tier_val,
                    nomor_hp=nomor_hp_val,
                    email=email_val,
                    domisili=domisili_val,
                    last_position=last_position_val,
                    last_company=last_company_val,
                    last_tenure=last_tenure_val,
                    total_tenure=total_tenure_val,
                    pernah_di_fmcg=pernah_di_fmcg_val,
                    sourcing_hr=sourcing_hr_val,
                    shortlist_cv=shortlist_cv_val,
                    psikotes=psikotes_val,
                    hr_interview=hr_interview_val,
                    user_interview=user_interview_val,
                    offering=offering_val,
                    day1=day1_val,
                    source_user_id=user_id,
                    source_cycle_id=cycle_id,
                    source_file=safe_string_for_db(file_name, max_length=255),
                    source_file_hash=safe_string_for_db(file_hash, max_length=64),
                    created_at=datetime.now(),
                    last_compile_action="COMPILE"
                )
                db.add(new_sourcing)
                imported += 1
                
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
            db.rollback()
    
    if errors:
        db.rollback()
        return {"success": False, "imported": imported, "updated": updated, "errors": errors}
    
    try:
        db.commit()
        return {"success": True, "imported": imported, "updated": updated, "errors": []}
    except Exception as e:
        db.rollback()
        return {"success": False, "imported": imported, "updated": updated, "errors": [str(e)]}


def compile_db_kode_posisi(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                           file_name: str, file_hash: str):
    """Compile DB Kode Posisi dari uploaded file"""
    from core.validator import validate_db_kode_posisi_file
    
    errors = []
    imported = 0
    
    # Clear any pending transaction
    if db.is_active:
        db.rollback()
    
    valid_rows, val_errors = validate_db_kode_posisi_file(
        df,
        db,
        user_id
    )
    if val_errors:
        return {"success": False, "imported": 0, "errors": val_errors}
    
    for _, row in df.iterrows():
        position = safe_string_for_db(row.get('position', ''), max_length=255)
        if not position:
            continue
        
        try:
            existing = db.query(DBKodePosisi).filter(
                DBKodePosisi.position == position
            ).first()
            
            if existing:
                existing.kode = safe_string_for_db(row.get('kode'), max_length=50)
                existing.location = safe_string_for_db(row.get('location'), max_length=100)
                existing.business_unit = safe_string_for_db(row.get('business_unit'), max_length=100)
                existing.division_chris = safe_string_for_db(row.get('division_chris'), max_length=100)
                existing.department_chris = safe_string_for_db(row.get('department_chris'), max_length=100)
                existing.user_manager = safe_string_for_db(row.get('user_manager'), max_length=100)
                existing.indirect_user = safe_string_for_db(row.get('indirect_user'), max_length=100)
                existing.directorate = safe_string_for_db(row.get('directorate'), max_length=100)
                existing.year = safe_int_value(row.get('year'), datetime.now().year)
            else:
                new_pos = DBKodePosisi(
                    kode=safe_string_for_db(row.get('kode'), max_length=50),
                    position=position,
                    location=safe_string_for_db(row.get('location'), max_length=100),
                    business_unit=safe_string_for_db(row.get('business_unit'), max_length=100),
                    division_chris=safe_string_for_db(row.get('division_chris'), max_length=100),
                    department_chris=safe_string_for_db(row.get('department_chris'), max_length=100),
                    user_manager=safe_string_for_db(row.get('user_manager'), max_length=100),
                    indirect_user=safe_string_for_db(row.get('indirect_user'), max_length=100),
                    directorate=safe_string_for_db(row.get('directorate'), max_length=100),
                    year=safe_int_value(row.get('year'), datetime.now().year)
                )
                db.add(new_pos)
            imported += 1
        except Exception as e:
            errors.append(str(e))
            db.rollback()
    
    if errors:
        db.rollback()
        return {"success": False, "imported": 0, "errors": errors}
    
    try:
        db.commit()
        return {"success": True, "imported": imported, "errors": []}
    except Exception as e:
        db.rollback()
        return {"success": False, "imported": 0, "errors": [str(e)]}


def compile_blacklist(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                      file_name: str, file_hash: str):
    """Compile Blacklist Candidate dari uploaded file"""
    from core.validator import validate_blacklist_file
    
    errors = []
    imported = 0
    
    # Clear any pending transaction
    if db.is_active:
        db.rollback()
    
    valid_rows, val_errors = validate_blacklist_file(
        df,
        db,
        user_id
    )
    if val_errors:
        return {"success": False, "imported": 0, "errors": val_errors}
    
    for _, row in df.iterrows():
        key = safe_string_for_db(row.get('key_value', ''), max_length=255)
        if not key:
            continue
        
        try:
            existing = db.query(Blacklist).filter(Blacklist.key_value == key).first()
            if not existing:
                new_bl = Blacklist(key_value=key)
                db.add(new_bl)
                imported += 1
        except Exception as e:
            errors.append(str(e))
            db.rollback()
    
    if errors:
        db.rollback()
        return {"success": False, "imported": 0, "errors": errors}
    
    try:
        db.commit()
        return {"success": True, "imported": imported, "errors": []}
    except Exception as e:
        db.rollback()
        return {"success": False, "imported": 0, "errors": [str(e)]}
