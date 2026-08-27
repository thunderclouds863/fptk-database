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

        kode_unik = safe_string(row.get('kode_unik', ''))
        posisi = safe_string(row.get('posisi', ''))
        status = safe_string(row.get('status', ''))

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
        kode_bu = safe_string(row.get('kode_pic', ''))[:4] if row.get('kode_pic') else ''

        filter_kat = safe_string(row.get('filter_kategorisasi_fptk', ''))
        
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

        avail = safe_boolean_char(row.get('fptk_availability', ''))

        jumlah_sla = safe_int(row.get('jumlah_sla'), sla_days)
        vacancy = safe_int(row.get('vacancy'), 1)
        level_number = int(level_num) if level_num else 1

        if existing:
            existing.kode_pic = safe_string(row.get('kode_pic'))
            existing.fptk_date_real = fptk_date_real
            existing.fptk_date_kode = fptk_date_real
            existing.posisi = posisi
            existing.business_unit = safe_string(row.get('business_unit'))
            existing.direktorat = safe_string(row.get('direktorat'))
            existing.divisi = safe_string(row.get('divisi'))
            existing.department = safe_string(row.get('department'))
            existing.level_fptk = level_fptk
            existing.level_number = level_number
            existing.alasan_permintaan_fptk = safe_string(row.get('alasan_permintaan_fptk'))
            existing.category_fptk = safe_string(row.get('category_fptk'))
            existing.pic_recruiter = safe_string(row.get('pic_recruiter'))
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
            existing.source_file = safe_string(file_name)
            existing.source_file_hash = file_hash
            existing.is_sto = is_sto
            updated += 1
        else:
            kode_angka = row.get('kode_angka')
            if pd.isna(kode_angka) or not kode_angka:
                kode_angka = (safe_string(row.get('kode_pic', ''))[:4] + str(vacancy))

            new_fptk = FPTK(
                kode_unik=kode_unik,
                posisi=posisi,
                kode_pic=safe_string(row.get('kode_pic')),
                fptk_date_real=fptk_date_real,
                fptk_date_kode=fptk_date_real,
                kode_angka=safe_string(kode_angka),
                business_unit=safe_string(row.get('business_unit')),
                direktorat=safe_string(row.get('direktorat')),
                divisi=safe_string(row.get('divisi')),
                department=safe_string(row.get('department')),
                level_fptk=level_fptk,
                level_number=level_number,
                alasan_permintaan_fptk=safe_string(row.get('alasan_permintaan_fptk')),
                category_fptk=safe_string(row.get('category_fptk')),
                pic_recruiter=safe_string(row.get('pic_recruiter')),
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
                source_file=safe_string(file_name),
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
        file_name=safe_string(file_name),
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
    
    CRITICAL FIX: This function now properly converts all values before inserting
    into the database. The error "invalid input syntax for type double precision: 'V'"
    occurred because string values like 'V' were being inserted into numeric columns.
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
        kode_unik = safe_string(row.get('kode_unik', ''))
        nama = safe_string(row.get('nama', ''))
        
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
            
            # --- CRITICAL: SAFE CONVERSIONS FOR ALL FIELDS ---
            # Numeric fields - these MUST NOT receive string values like 'V'
            no_val = safe_int(row.get('no'), imported + 1)
            tahun_lulus_val = safe_int(row.get('tahun_lulus'))  # Will return 0 if invalid
            ipk_val = safe_float(row.get('ipk'))  # Will return 0.0 if invalid
            
            # String fields - safe conversion
            posisi_val = safe_string(row.get('posisi'))
            model_rekrutmen_val = safe_string(row.get('model_rekrutmen'))
            rekruter_val = safe_string(row.get('rekruter'))
            sumber_sourcing_val = safe_string(row.get('sumber_sourcing'))
            nama_univ_top10_val = safe_string(row.get('nama_universitas_top10'))
            nama_univ_lain_val = safe_string(row.get('nama_universitas_lainnya'))
            jenjang_val = safe_string(row.get('jenjang_pendidikan'))
            jurusan_val = safe_string(row.get('jurusan'))
            skor_inggris_val = safe_string(row.get('skor_bahasa_inggris'))
            university_tier_val = safe_string(row.get('university_tier'))
            ipk_tier_val = safe_string(row.get('ipk_tier'))
            nomor_hp_val = safe_string(row.get('nomor_hp'))
            email_val = safe_string(row.get('email'))
            domisili_val = safe_string(row.get('domisili'))
            last_position_val = safe_string(row.get('last_position'))
            last_company_val = safe_string(row.get('last_company'))
            last_tenure_val = safe_string(row.get('last_tenure'))
            total_tenure_val = safe_string(row.get('total_tenure'))
            pernah_di_fmcg_val = safe_string(row.get('pernah_di_fmcg'))
            
            # Boolean-like fields (V/X) - These are STRINGS, not numeric
            # CRITICAL: These should be stored in VARCHAR columns, not numeric columns
            sourcing_hr_val = safe_boolean_char(row.get('sourcing_hr'))
            shortlist_cv_val = safe_boolean_char(row.get('shortlist_cv'))
            psikotes_val = safe_boolean_char(row.get('psikotes'))
            hr_interview_val = safe_boolean_char(row.get('hr_interview'))
            user_interview_val = safe_boolean_char(row.get('user_interview'))
            offering_val = safe_boolean_char(row.get('offering'))
            day1_val = safe_boolean_char(row.get('day1'))
            
            if existing:
                # Update existing record
                existing.posisi = posisi_val
                existing.model_rekrutmen = model_rekrutmen_val
                existing.rekruter = rekruter_val
                existing.sumber_sourcing = sumber_sourcing_val
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
                print("DEBUG PIPELINE VALUES")
                for field in [
                    "sourcing_hr",
                    "shortlist_cv",
                    "psikotes",
                    "hr_interview",
                    "user_interview",
                    "offering",
                    "day1",
                    "nilai_logika",
                    "nilai_iq",
                    "nilai_ra"
                ]:
                    print(
                        field,
                        row.get(field),
                        type(row.get(field))
                    )
                print("========== DB COLUMN TYPE CHECK ==========")

                for col in DBSourcing.__table__.columns:
                    print(
                        col.name,
                        "=>",
                        col.type
                    )
                
                print("==========================================")
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
                    source_file=safe_string(file_name),
                    source_file_hash=safe_string(file_hash),
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
        position = safe_string(row.get('position', ''))
        if not position:
            continue
        
        try:
            existing = db.query(DBKodePosisi).filter(
                DBKodePosisi.position == position
            ).first()
            
            if existing:
                existing.kode = safe_string(row.get('kode'))
                existing.location = safe_string(row.get('location'))
                existing.business_unit = safe_string(row.get('business_unit'))
                existing.division_chris = safe_string(row.get('division_chris'))
                existing.department_chris = safe_string(row.get('department_chris'))
                existing.user_manager = safe_string(row.get('user_manager'))
                existing.indirect_user = safe_string(row.get('indirect_user'))
                existing.directorate = safe_string(row.get('directorate'))
                existing.year = safe_int(row.get('year'), datetime.now().year)
            else:
                new_pos = DBKodePosisi(
                    kode=safe_string(row.get('kode')),
                    position=position,
                    location=safe_string(row.get('location')),
                    business_unit=safe_string(row.get('business_unit')),
                    division_chris=safe_string(row.get('division_chris')),
                    department_chris=safe_string(row.get('department_chris')),
                    user_manager=safe_string(row.get('user_manager')),
                    indirect_user=safe_string(row.get('indirect_user')),
                    directorate=safe_string(row.get('directorate')),
                    year=safe_int(row.get('year'), datetime.now().year)
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
        key = safe_string(row.get('key_value', ''))
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
