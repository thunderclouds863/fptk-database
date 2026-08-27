# core/compiler.py

import pandas as pd
import math
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from core.models import FPTK, UploadLog
from core.utils import safe_int, calculate_detail_sla, parse_date_dmy
import hashlib


def sanitize_date_value(val):
    """Konversi nan/NaT ke None untuk SQLAlchemy, return date object"""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return parse_date_dmy(val)
    return val


def ensure_date(val):
    """Pastikan value adalah date object"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return parse_date_dmy(val)
    return None


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

        kode_unik = row.get('kode_unik', '')
        posisi = row.get('posisi', '')
        status = row.get('status', '')
        
        # Sanitize dates
        fptk_date_real = sanitize_date_value(row.get('fptk_date_real'))
        offering_date = sanitize_date_value(row.get('offering_date'))
        fptk_cancel_date = sanitize_date_value(row.get('fptk_cancel_date'))
        deadline_sla_input = sanitize_date_value(row.get('deadline_sla'))

        if not kode_unik or not posisi:
            skipped += 1
            continue

        # Cek existing
        existing = db.query(FPTK).filter(
            FPTK.kode_unik == kode_unik,
            FPTK.posisi == posisi
        ).first()

        if existing and existing.source_user_id != user_id:
            skipped += 1
            continue

        if existing and existing.fptk_date_real != fptk_date_real:
            skipped += 1
            continue

        level_num = row.get('level_number', 0)
        if level_num <= 3:
            sla_days = 30
        elif level_num == 4:
            sla_days = 45
        elif level_num >= 5:
            sla_days = 60
        else:
            sla_days = 30

        # Hitung deadline SLA
        if fptk_date_real:
            if isinstance(fptk_date_real, date):
                deadline_sla = fptk_date_real + timedelta(days=sla_days)
            elif isinstance(fptk_date_real, datetime):
                deadline_sla = fptk_date_real.date() + timedelta(days=sla_days)
            else:
                deadline_sla = None
        else:
            deadline_sla = deadline_sla_input

        # Pastikan semua tanggal adalah date object
        if deadline_sla and isinstance(deadline_sla, datetime):
            deadline_sla = deadline_sla.date()
        if offering_date and isinstance(offering_date, datetime):
            offering_date = offering_date.date()
        if fptk_cancel_date and isinstance(fptk_cancel_date, datetime):
            fptk_cancel_date = fptk_cancel_date.date()
        if fptk_date_real and isinstance(fptk_date_real, datetime):
            fptk_date_real = fptk_date_real.date()

        # Hitung Detail SLA
        detail_sla = calculate_detail_sla(
            status=status,
            deadline_sla=deadline_sla,
            offering_date=offering_date
        )

        week_num = fptk_date_real.isocalendar()[1] if fptk_date_real else None
        month_name = fptk_date_real.strftime("%B") if fptk_date_real else None
        kode_bu = row.get('kode_pic', '')[:4] if row.get('kode_pic') else ''

        filter_kat = row.get('filter_kategorisasi_fptk', '')
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

        avail = row.get('fptk_availability', '')
        if avail and str(avail).upper() in ['V', 'Y', 'YA', 'YES', 'TRUE', '1']:
            avail = 'Y'
        elif avail and str(avail).upper() in ['X', 'N', 'TIDAK', 'NO', 'FALSE', '0']:
            avail = 'N'
        else:
            avail = None

        # Jumlah SLA
        jumlah_sla = row.get('jumlah_sla')
        if pd.isna(jumlah_sla) or jumlah_sla is None:
            jumlah_sla = sla_days

        if existing:
            # UPDATE
            existing.kode_pic = row.get('kode_pic')
            existing.fptk_date_real = fptk_date_real
            existing.fptk_date_kode = fptk_date_real
            existing.posisi = posisi
            existing.business_unit = row.get('business_unit')
            existing.direktorat = row.get('direktorat')
            existing.divisi = row.get('divisi')
            existing.department = row.get('department')
            existing.level_fptk = row.get('level_fptk')
            existing.level_number = level_num
            existing.alasan_permintaan_fptk = row.get('alasan_permintaan_fptk')
            existing.category_fptk = row.get('category_fptk')
            existing.pic_recruiter = row.get('pic_recruiter')
            existing.vacancy = row.get('vacancy')
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
            updated += 1
        else:
            # INSERT
            kode_angka = row.get('kode_angka')
            if pd.isna(kode_angka) or not kode_angka:
                kode_angka = (row.get('kode_pic', '')[:4] + str(safe_int(row.get('vacancy', 1))))

            new_fptk = FPTK(
                kode_unik=kode_unik,
                posisi=posisi,
                kode_pic=row.get('kode_pic'),
                fptk_date_real=fptk_date_real,
                fptk_date_kode=fptk_date_real,
                kode_angka=kode_angka,
                business_unit=row.get('business_unit'),
                direktorat=row.get('direktorat'),
                divisi=row.get('divisi'),
                department=row.get('department'),
                level_fptk=row.get('level_fptk'),
                level_number=level_num,
                alasan_permintaan_fptk=row.get('alasan_permintaan_fptk'),
                category_fptk=row.get('category_fptk'),
                pic_recruiter=row.get('pic_recruiter'),
                vacancy=row.get('vacancy'),
                status=status,
                offering_date=offering_date,
                fptk_cancel_date=fptk_cancel_date,
                jumlah_sla=jumlah_sla,
                deadline_sla=deadline_sla,
                detail_sla=detail_sla,
                week_fptk_date=week_num,
                month_fptk_date=month_name,
                kode_bu=kode_bu,
                filter_kategorisasi_fptk=filter_kat,
                fptk_availability=avail,
                source_user_id=user_id,
                source_cycle_id=cycle_id,
                source_file=file_name,
                source_file_hash=file_hash,
                is_sto=is_sto,
                created_at=datetime.now(),
                last_compile_action="INSERT"
            )
            db.add(new_fptk)
            imported += 1

    db.commit()

    log = UploadLog(
        cycle_id=cycle_id,
        user_id=user_id,
        file_name=file_name,
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


def compile_db_sourcing(db, df, user_id, cycle_id, file_name, file_hash, kode_unik_mapping):
    """Stub function for DB Sourcing compile."""
    return {"success": True, "imported": 0, "errors": []}
