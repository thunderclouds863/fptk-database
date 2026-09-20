# core/compiler.py
import pandas as pd
import math
import re
import hashlib
import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime, timedelta, date

from core.models import FPTK, DBSourcing, DBKodePosisi, UploadLog
from core.utils import (
    safe_int, safe_float, safe_string, safe_boolean_char, safe_date,
    sanitize_date_value, calculate_detail_sla, calculate_sla_days,
    parse_date_dmy, normalize_text, get_single_value, normalize_boolean_to_vx
)


def safe_string_for_db(value, default='', max_length=None):
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

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
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

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
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

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
    if val is None:
        return None

    try:
        if pd.isna(val):
            return None
    except Exception:
        pass

    if isinstance(val, bool):
        return 'V' if val else 'X'
    if isinstance(val, (int, float)):
        return 'V' if val else 'X'
    if isinstance(val, str):
        v = val.strip().upper()
        if len(v) > 1:
            if v in ['V', 'Y', 'YA', 'YES', 'TRUE', '1']:
                return 'V'
            if v in ['X', 'N', 'NO', 'FALSE', '0']:
                return 'X'
            first_char = v[0]
            if first_char in ['V', 'Y']:
                return 'V'
            if first_char in ['X', 'N']:
                return 'X'
            return None
        if v in ['V', 'Y']:
            return 'V'
        if v in ['X', 'N']:
            return 'X'
        return None
    if isinstance(val, pd.Series):
        return get_boolean_value(val.iloc[0]) if len(val) > 0 else None
    return None


def safe_level_number(value):
    if value is None or pd.isna(value):
        return 1
    if isinstance(value, (int, float)):
        try:
            int_val = int(value)
            if 1 <= int_val <= 5:
                return int_val
            return 1
        except Exception:
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


def safe_date_fallback(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    class_name = str(value.__class__)
    if 'NaT' in class_name:
        return None

    if isinstance(value, str) and value.upper() == 'NAT':
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, pd.Timestamp):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return value.date()

    if isinstance(value, str):
        return parse_date_dmy(value)

    return None


def _get_kode_bu(kode_pic):
    if not kode_pic:
        return None
    kode = str(kode_pic).strip().upper()
    if kode.startswith('CORP') or kode.startswith('ADM'):
        return 'HO'
    elif kode.startswith('JESS'):
        return 'JESS'
    elif kode.startswith('CMD'):
        return 'CMD'
    elif kode.startswith('BHC') or kode.startswith('BCH'):
        return 'BHC'
    elif kode.startswith('ARC'):
        return 'ARC'
    elif kode.startswith('MS'):
        return 'MS'
    elif kode.startswith('MP'):
        return 'MP'
    elif kode.startswith('MB'):
        return 'MB'
    elif kode.startswith('HO'):
        return 'HO'
    return None


def translate_error_to_friendly(error_msg: str) -> str:
    error_lower = str(error_msg).lower()

    if "duplicate key" in error_lower or "cardinality" in error_lower or "unique constraint" in error_lower:
        return "Ada data duplikat di file. Cek baris dengan Kode Unik + Posisi yang sama."

    if "not null constraint" in error_lower or "null value in column" in error_lower:
        return "Ada kolom wajib yang kosong. Cek kembali kolom yang bertanda * (wajib)."

    if "value too long" in error_lower or "string data right truncation" in error_lower:
        return "Ada teks yang terlalu panjang di salah satu kolom. Persingkat teksnya."

    if "invalid input syntax" in error_lower and "date" in error_lower:
        return "Ada format tanggal yang salah. Pastikan format DD/MM/YYYY (contoh: 15/02/2026)."

    if "invalid input syntax" in error_lower and ("integer" in error_lower or "numeric" in error_lower):
        return "Ada nilai angka yang tidak valid atau di luar batas. Cek kolom angka (No, IPK, dll)."

    if "check constraint" in error_lower:
        return "Ada nilai yang tidak sesuai aturan. Cek kolom Status (OP/Closed/Cancel) dan FPTK Availability (V/X)."

    if "foreign key" in error_lower:
        return "Data referensi tidak ditemukan. Pastikan Kode Unik sudah ada di FPTK."

    if "out of range" in error_lower:
        return "Ada nilai angka yang melebihi batas maksimum. Cek kolom No atau lainnya."

    return "Terjadi kesalahan saat memproses file. Hubungi admin jika masalah berlanjut."


def compile_fptk(db: Session, rows_or_df, user_id: int, cycle_id: int,
                 file_name: str, file_bytes: bytes, is_sto: bool = False):
    if isinstance(rows_or_df, list):
        df = pd.DataFrame(rows_or_df)
    else:
        df = rows_or_df

    file_hash = hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""

    if df.empty:
        return {
            "success": False, "imported": 0, "updated": 0, "skipped": 0,
            "errors": ["Tidak ada data valid"]
        }

    rows_to_upsert = []
    skipped = 0

    for idx, row in df.iterrows():
        kode_unik = safe_string_for_db(row.get('kode_unik', ''), max_length=100)
        posisi = safe_string_for_db(row.get('posisi', ''), max_length=500)
        status = safe_string_for_db(row.get('status', ''), max_length=50)

        if not kode_unik or not posisi:
            skipped += 1
            continue

        fptk_date_real = safe_date(row.get('fptk_date_real'))
        offering_date = safe_date(row.get('offering_date'))
        fptk_cancel_date = safe_date(row.get('fptk_cancel_date'))
        deadline_sla_input = safe_date(row.get('deadline_sla'))

        if fptk_date_real and isinstance(fptk_date_real, datetime):
            fptk_date_real = fptk_date_real.date()
        if offering_date and isinstance(offering_date, datetime):
            offering_date = offering_date.date()
        if fptk_cancel_date and isinstance(fptk_cancel_date, datetime):
            fptk_cancel_date = fptk_cancel_date.date()
        if deadline_sla_input and isinstance(deadline_sla_input, datetime):
            deadline_sla_input = deadline_sla_input.date()

        level_num = safe_level_number(row.get('level_number'))
        if level_num == 1:
            raw_level_fptk = row.get('level_fptk')
            if raw_level_fptk:
                m = re.search(r'(\d+)', str(raw_level_fptk))
                if m:
                    n = int(m.group(1))
                    if 1 <= n <= 5:
                        level_num = n

        level_fptk = safe_level_fptk(row.get('level_fptk'))
        if level_fptk == "1A" and level_num > 1:
            level_fptk = f"{level_num}A"

        sla_days = calculate_sla_days(level_num)
        deadline_sla = fptk_date_real + timedelta(days=sla_days) if fptk_date_real else deadline_sla_input

        detail_sla = calculate_detail_sla(
            status=status, deadline_sla=deadline_sla, offering_date=offering_date
        )

        week_num = fptk_date_real.isocalendar()[1] if fptk_date_real else None
        month_name = fptk_date_real.strftime("%B") if fptk_date_real else None

        kode_bu = _get_kode_bu(row.get('kode_pic', ''))

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

        kode_angka = row.get('kode_angka')
        if pd.isna(kode_angka) or not kode_angka:
            kode_angka = safe_string_for_db(row.get('kode_pic', ''), max_length=50)[:4] + str(vacancy)

        rows_to_upsert.append({
            'kode_unik': kode_unik,
            'posisi': posisi,
            'kode_pic': safe_string_for_db(row.get('kode_pic'), max_length=50),
            'fptk_date_real': fptk_date_real,
            'fptk_date_kode': fptk_date_real,
            'kode_angka': safe_string_for_db(kode_angka, max_length=50),
            'business_unit': safe_string_for_db(row.get('business_unit'), max_length=100),
            'direktorat': safe_string_for_db(row.get('direktorat'), max_length=100),
            'divisi': safe_string_for_db(row.get('divisi'), max_length=100),
            'department': safe_string_for_db(row.get('department'), max_length=100),
            'level_fptk': level_fptk,
            'level_number': level_number,
            'alasan_permintaan_fptk': safe_string_for_db(row.get('alasan_permintaan_fptk'), max_length=200),
            'category_fptk': safe_string_for_db(row.get('category_fptk'), max_length=100),
            'pic_recruiter': safe_string_for_db(row.get('pic_recruiter'), max_length=100),
            'filter_kategorisasi_fptk': filter_kat,
            'vacancy': vacancy,
            'status': status,
            'offering_date': offering_date,
            'fptk_cancel_date': fptk_cancel_date,
            'jumlah_sla': jumlah_sla,
            'deadline_sla': deadline_sla,
            'detail_sla': detail_sla,
            'week_fptk_date': week_num,
            'month_fptk_date': month_name,
            'kode_bu': kode_bu,
            'fptk_availability': avail,
            'source_user_id': user_id,
            'source_cycle_id': cycle_id,
            'source_file': safe_string_for_db(file_name, max_length=255),
            'source_file_hash': file_hash,
            'is_sto': is_sto,
        })

    if rows_to_upsert:
        seen_keys = {}
        duplicate_details = []

        for r in rows_to_upsert:
            key = (r['kode_unik'], r['posisi'])
            if key in seen_keys:
                duplicate_details.append({
                    "kode_unik": r['kode_unik'],
                    "posisi": r['posisi'],
                    "first_row": seen_keys[key],
                    "duplicate_row": len(seen_keys) + len(duplicate_details) + 1,
                })
            else:
                seen_keys[key] = len(seen_keys) + 1

        if duplicate_details:
            db.rollback()

            pesan = f"File ditolak karena ada {len(duplicate_details)} baris duplikat.\n\n"
            pesan += "Baris duplikat artinya: ada 2+ baris dengan Kode Unik + Posisi yang SAMA.\n\n"
            pesan += "Daftar duplikat:\n"
            for dup in duplicate_details[:10]:
                pesan += f"  - Kode Unik: {dup['kode_unik']}\n"
                pesan += f"    Posisi: {dup['posisi']}\n"
                pesan += f"    Muncul di baris ke-{dup['first_row']} dan ke-{dup['duplicate_row']}\n\n"

            if len(duplicate_details) > 10:
                pesan += f"  ... dan {len(duplicate_details) - 10} duplikat lainnya\n\n"

            pesan += "Solusi:\n"
            pesan += "1. Buka file Excel-nya\n"
            pesan += "2. Cari baris dengan Kode Unik + Posisi yang sama\n"
            pesan += "3. Hapus salah satu (yang lama atau yang duplikat)\n"
            pesan += "4. Upload ulang file-nya"

            try:
                log = UploadLog(
                    cycle_id=cycle_id,
                    user_id=user_id,
                    file_name=safe_string_for_db(file_name, max_length=255),
                    file_size_bytes=len(file_bytes) if file_bytes else 0,
                    file_hash=file_hash,
                    status="REJECTED",
                    record_count=0,
                    error_details=pesan
                )
                db.add(log)
                db.commit()
            except Exception:
                db.rollback()

            return {
                "success": False,
                "imported": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [pesan],
                "duplicate_count": len(duplicate_details),
                "duplicate_details": duplicate_details,
                "rejection_type": "DUPLICATE"
            }

    if not rows_to_upsert:
        return {
            "success": False, "imported": 0, "updated": 0, "skipped": skipped,
            "errors": ["Tidak ada row valid untuk di-compile"]
        }

    imported = 0
    updated = 0

    try:
        kode_list = [r['kode_unik'] for r in rows_to_upsert]
        existing_records = db.query(FPTK.kode_unik, FPTK.posisi).filter(
            FPTK.kode_unik.in_(kode_list)
        ).all()
        existing_keys = {(r.kode_unik, r.posisi) for r in existing_records}

        for r in rows_to_upsert:
            key = (r['kode_unik'], r['posisi'])
            if key in existing_keys:
                updated += 1
            else:
                imported += 1

        now = datetime.now()
        for r in rows_to_upsert:
            r['created_at'] = now
            r['last_updated_at'] = now
            r['last_compile_action'] = 'UPSERT'

        stmt = pg_insert(FPTK).values(rows_to_upsert)

        update_columns = {
            'kode_pic': stmt.excluded.kode_pic,
            'fptk_date_real': stmt.excluded.fptk_date_real,
            'fptk_date_kode': stmt.excluded.fptk_date_kode,
            'kode_angka': stmt.excluded.kode_angka,
            'business_unit': stmt.excluded.business_unit,
            'direktorat': stmt.excluded.direktorat,
            'divisi': stmt.excluded.divisi,
            'department': stmt.excluded.department,
            'level_fptk': stmt.excluded.level_fptk,
            'level_number': stmt.excluded.level_number,
            'alasan_permintaan_fptk': stmt.excluded.alasan_permintaan_fptk,
            'category_fptk': stmt.excluded.category_fptk,
            'pic_recruiter': stmt.excluded.pic_recruiter,
            'filter_kategorisasi_fptk': stmt.excluded.filter_kategorisasi_fptk,
            'vacancy': stmt.excluded.vacancy,
            'status': stmt.excluded.status,
            'offering_date': stmt.excluded.offering_date,
            'fptk_cancel_date': stmt.excluded.fptk_cancel_date,
            'jumlah_sla': stmt.excluded.jumlah_sla,
            'deadline_sla': stmt.excluded.deadline_sla,
            'detail_sla': stmt.excluded.detail_sla,
            'week_fptk_date': stmt.excluded.week_fptk_date,
            'month_fptk_date': stmt.excluded.month_fptk_date,
            'kode_bu': stmt.excluded.kode_bu,
            'fptk_availability': stmt.excluded.fptk_availability,
            'source_user_id': stmt.excluded.source_user_id,
            'source_cycle_id': stmt.excluded.source_cycle_id,
            'source_file': stmt.excluded.source_file,
            'source_file_hash': stmt.excluded.source_file_hash,
            'is_sto': stmt.excluded.is_sto,
            'last_updated_at': now,
            'last_compile_action': 'UPDATE',
        }

        stmt = stmt.on_conflict_do_update(
            index_elements=['kode_unik', 'posisi'],
            set_=update_columns
        )

        db.execute(stmt)
        db.flush()

        log = UploadLog(
            cycle_id=cycle_id,
            user_id=user_id,
            file_name=safe_string_for_db(file_name, max_length=255),
            file_size_bytes=len(file_bytes) if file_bytes else 0,
            file_hash=file_hash,
            status="SUCCESS",
            record_count=imported + updated,
            error_details=f"Imported: {imported}, Updated: {updated}, Skipped: {skipped}"
        )
        db.add(log)
        db.commit()

        return {
            "success": True,
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "errors": []
        }

    except Exception as e:
        db.rollback()
        error_msg = str(e)

        try:
            log = UploadLog(
                cycle_id=cycle_id,
                user_id=user_id,
                file_name=safe_string_for_db(file_name, max_length=255),
                file_size_bytes=len(file_bytes) if file_bytes else 0,
                file_hash=file_hash,
                status="FAILED",
                record_count=0,
                error_details=error_msg[:2000]
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "success": False,
            "imported": 0, "updated": 0, "skipped": skipped,
            "errors": [error_msg]
        }


def compile_db_sourcing(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                        file_name: str, file_hash: str):
    errors = []
    imported = 0
    updated = 0
    warnings = []

    if db.is_active:
        db.rollback()

    if 'kode_unik' not in df.columns:
        for col in df.columns:
            col_str = str(col).strip().lower()
            if col_str in ['kode unik', 'kode_unik', 'kodeunik', 'unique code',
                           'kode unik (copy value dari fptk)']:
                df.rename(columns={col: 'kode_unik'}, inplace=True)
                break

    if 'nama' not in df.columns:
        for col in df.columns:
            col_str = str(col).strip().lower()
            if col_str in ['nama', 'nama kandidat', 'name', 'nama lengkap',
                           'candidate name', 'nama pelamar']:
                df.rename(columns={col: 'nama'}, inplace=True)
                break

    if 'sourcing_date' not in df.columns:
        for col in df.columns:
            col_str = str(col).strip().lower()
            if col_str in ['sourcing date', 'sourcing_date', 'tanggal sourcing',
                           'tanggal input', 'tgl sourcing']:
                df.rename(columns={col: 'sourcing_date'}, inplace=True)
                break

    if 'kode_unik' not in df.columns:
        db.rollback()
        error_msg = (
            f"Kolom 'Kode Unik' TIDAK DITEMUKAN di file DB Sourcing!\n\n"
            f"Kolom yang ada: {list(df.columns)}\n\n"
            f"Pastikan file DB Sourcing Anda memiliki kolom bernama 'Kode Unik'."
        )
        return {
            "success": False,
            "imported": 0,
            "updated": 0,
            "errors": [error_msg],
            "warnings": warnings
        }

    for idx, row in df.iterrows():
        row_num = idx + 2

        kode_unik = safe_string_for_db(row.get('kode_unik', ''), max_length=100)
        nama = safe_string_for_db(row.get('nama', ''), max_length=255)

        sourcing_date_raw = row.get('sourcing_date')

        is_nat = False
        if sourcing_date_raw is not None:
            try:
                if pd.isna(sourcing_date_raw):
                    is_nat = True
            except Exception:
                pass

            class_name = str(sourcing_date_raw.__class__)
            if 'NaT' in class_name:
                is_nat = True

            if isinstance(sourcing_date_raw, str) and sourcing_date_raw.upper() == 'NAT':
                is_nat = True

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
            except Exception:
                sourcing_date = datetime.now().date()
                warnings.append({
                    "row": row_num,
                    "field": "Sourcing Date",
                    "value": str(sourcing_date_raw),
                    "warning": True,
                    "error": f"Error parsing Sourcing Date, otomatis diisi {sourcing_date.strftime('%d/%m/%Y')}"
                })

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

            no_raw = row.get('no')
            no_val = safe_int_value(no_raw)

            if no_val is None or no_val < 0:
                no_val = imported + updated + 1
            elif no_val > 2147483647:
                no_val = imported + updated + 1
                warnings.append({
                    "row": row_num,
                    "field": "No",
                    "value": no_raw,
                    "warning": True,
                    "error": f"Nilai 'no' {no_raw} melebihi INTEGER max, di-replace auto-increment: {no_val}"
                })

            tahun_lulus_val = safe_int_value(row.get('tahun_lulus'))
            if tahun_lulus_val is not None:
                if tahun_lulus_val < 1900 or tahun_lulus_val > 2100:
                    tahun_lulus_val = None

            ipk_raw = row.get('ipk')
            ipk_val = safe_numeric_value(ipk_raw)

            if ipk_val is not None:
                if ipk_val < 0:
                    ipk_val = None
                    warnings.append({
                        "row": row_num,
                        "field": "IPK",
                        "value": ipk_raw,
                        "warning": True,
                        "error": f"IPK {ipk_raw} negatif, di-set None"
                    })
                elif ipk_val > 4 and ipk_val <= 100:
                    original = ipk_val
                    ipk_val = round(ipk_val / 25, 2)
                    warnings.append({
                        "row": row_num,
                        "field": "IPK",
                        "value": ipk_raw,
                        "warning": True,
                        "error": f"IPK {original} terdeteksi sebagai persen, dikonversi ke GPA: {ipk_val}"
                    })
                elif ipk_val > 100:
                    ipk_val = None
                    warnings.append({
                        "row": row_num,
                        "field": "IPK",
                        "value": ipk_raw,
                        "warning": True,
                        "error": f"IPK {ipk_raw} tidak valid (> 100), di-set None"
                    })

            posisi_val = safe_string_for_db(row.get('posisi'), max_length=255)
            model_rekrutmen_val = safe_string_for_db(row.get('model_rekrutmen'), max_length=100)
            rekruter_val = safe_string_for_db(row.get('rekruter'), max_length=100)
            sumber_sourcing_val = safe_string_for_db(row.get('sumber_sourcing'), max_length=100)
            nama_univ_top10_val = safe_string_for_db(row.get('nama_universitas_top10'), max_length=255)
            nama_univ_lain_val = safe_string_for_db(row.get('nama_universitas_lainnya'), max_length=255)
            jenjang_val = safe_string_for_db(row.get('jenjang_pendidikan'), max_length=50)
            jurusan_val = safe_string_for_db(row.get('jurusan'), max_length=100)
            jurusan_lainnya_val = safe_string_for_db(row.get('jurusan_lainnya'), max_length=100)
            skor_inggris_val = safe_string_for_db(row.get('skor_bahasa_inggris'), max_length=50)
            university_tier_val = safe_string_for_db(row.get('university_tier'), max_length=20)
            ipk_tier_val = safe_string_for_db(row.get('ipk_tier'), max_length=20)
            nomor_hp_val = safe_string_for_db(row.get('nomor_hp'), max_length=20)
            email_val = safe_string_for_db(row.get('email'), max_length=255)
            domisili_val = safe_string_for_db(row.get('domisili'), max_length=100)
            last_position_val = safe_string_for_db(row.get('last_position'), max_length=255)
            last_company_val = safe_string_for_db(row.get('last_company'), max_length=255)
            last_tenure_val = safe_string_for_db(row.get('last_tenure'), max_length=50)
            total_tenure_val = safe_string_for_db(row.get('total_tenure'), max_length=50)

            raw_fmcg = row.get('pernah_di_fmcg')
            if raw_fmcg and isinstance(raw_fmcg, str):
                v = raw_fmcg.strip().upper()
                if v in ['YA', 'Y', 'YES', 'TRUE', '1']:
                    pernah_di_fmcg_val = 'Ya'
                elif v in ['TIDAK', 'N', 'NO', 'FALSE', '0']:
                    pernah_di_fmcg_val = 'Tidak'
                else:
                    pernah_di_fmcg_val = safe_string_for_db(raw_fmcg, max_length=50)
            else:
                pernah_di_fmcg_val = safe_string_for_db(raw_fmcg, max_length=50)

            sourcing_freelance_val = normalize_boolean_to_vx(row.get('sourcing_freelance'))
            sourcing_hr_val = normalize_boolean_to_vx(row.get('sourcing_hr'))
            shortlist_cv_val = normalize_boolean_to_vx(row.get('shortlist_cv'))
            psikotes_val = normalize_boolean_to_vx(row.get('psikotes'))
            hr_interview_val = normalize_boolean_to_vx(row.get('hr_interview'))
            user_interview_val = normalize_boolean_to_vx(row.get('user_interview'))
            offering_val = normalize_boolean_to_vx(row.get('offering'))
            day1_val = normalize_boolean_to_vx(row.get('day1'))
            technical_test_case_study_val = normalize_boolean_to_vx(row.get('technical_test_case_study'))
            market_visit_val = normalize_boolean_to_vx(row.get('market_visit'))
            panel_interview_val = normalize_boolean_to_vx(row.get('panel_interview'))
            reference_check_val = normalize_boolean_to_vx(row.get('reference_check'))
            mcu_val = normalize_boolean_to_vx(row.get('mcu'))

            tanggal_sourcing_freelance = safe_date_fallback(row.get('tanggal_sourcing_freelance'))
            tanggal_sourcing = safe_date_fallback(row.get('tanggal_sourcing'))
            tanggal_shortlist_cv = safe_date_fallback(row.get('tanggal_shortlist_cv'))
            tanggal_psikotes = safe_date_fallback(row.get('tanggal_psikotes'))
            tanggal_hr_interview = safe_date_fallback(row.get('tanggal_hr_interview'))
            tanggal_user_interview = safe_date_fallback(row.get('tanggal_user_interview'))
            tanggal_offering = safe_date_fallback(row.get('tanggal_offering'))
            tanggal_day1 = safe_date_fallback(row.get('tanggal_day1'))
            tanggal_technical_test = safe_date_fallback(row.get('tanggal_technical_test'))
            tanggal_market_visit = safe_date_fallback(row.get('tanggal_market_visit'))
            tanggal_panel_interview = safe_date_fallback(row.get('tanggal_panel_interview'))
            tanggal_reference_check = safe_date_fallback(row.get('tanggal_reference_check'))
            tanggal_mcu = safe_date_fallback(row.get('tanggal_mcu'))

            detail_keterangan_sourcing_hr = safe_string_for_db(row.get('detail_keterangan_sourcing_hr'), max_length=500)
            detail_keterangan_shortlist_cv = safe_string_for_db(row.get('detail_keterangan_shortlist_cv'), max_length=500)
            detail_keterangan_psikotes = safe_string_for_db(row.get('detail_keterangan_psikotes'), max_length=500)
            detail_keterangan_hr_interview = safe_string_for_db(row.get('detail_keterangan_hr_interview'), max_length=500)
            detail_keterangan_user_interview = safe_string_for_db(row.get('detail_keterangan_user_interview'), max_length=500)
            detail_keterangan_offering = safe_string_for_db(row.get('detail_keterangan_offering'), max_length=500)
            detail_keterangan_day1 = safe_string_for_db(row.get('detail_keterangan_day1'), max_length=500)
            notes_val = safe_string_for_db(row.get('notes'), max_length=500)

            kode_psikotes_val = safe_string_for_db(row.get('kode_psikotes'), max_length=50)
            nilai_logika_val = safe_string_for_db(row.get('nilai_logika'), max_length=20)
            nilai_iq_val = safe_string_for_db(row.get('nilai_iq'), max_length=20)
            nilai_daya_tangkap_val = safe_string_for_db(row.get('nilai_daya_tangkap'), max_length=20)
            nilai_ra_val = safe_string_for_db(row.get('nilai_ra'), max_length=20)
            disc_val = safe_string_for_db(row.get('disc'), max_length=20)

            detail_keterangan_technical_test = safe_string_for_db(row.get('detail_keterangan_technical_test'), max_length=500)
            detail_market_visit = safe_string_for_db(row.get('detail_market_visit'), max_length=500)
            detail_keterangan_panel_interview = safe_string_for_db(row.get('detail_keterangan_panel_interview'), max_length=500)
            detail_keterangan_reference_check = safe_string_for_db(row.get('detail_keterangan_reference_check'), max_length=500)
            detail_keterangan_mcu = safe_string_for_db(row.get('detail_keterangan_mcu'), max_length=500)

            is_blacklisted = False
            blacklist_raw = row.get('is_blacklisted')
            if blacklist_raw is not None:
                if isinstance(blacklist_raw, bool):
                    is_blacklisted = blacklist_raw
                elif isinstance(blacklist_raw, str):
                    is_blacklisted = blacklist_raw.strip().upper() in ['YES', 'TRUE', 'Y', '1']
                elif isinstance(blacklist_raw, (int, float)):
                    is_blacklisted = bool(blacklist_raw)

            blacklist_reason = safe_string_for_db(row.get('blacklist_reason'), max_length=500)

            if existing:
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
                existing.jurusan_lainnya = jurusan_lainnya_val
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
                existing.sourcing_freelance = sourcing_freelance_val
                existing.sourcing_hr = sourcing_hr_val
                existing.shortlist_cv = shortlist_cv_val
                existing.psikotes = psikotes_val
                existing.hr_interview = hr_interview_val
                existing.user_interview = user_interview_val
                existing.offering = offering_val
                existing.day1 = day1_val
                existing.tanggal_sourcing_freelance = tanggal_sourcing_freelance
                existing.tanggal_sourcing = tanggal_sourcing
                existing.tanggal_shortlist_cv = tanggal_shortlist_cv
                existing.tanggal_psikotes = tanggal_psikotes
                existing.tanggal_hr_interview = tanggal_hr_interview
                existing.tanggal_user_interview = tanggal_user_interview
                existing.tanggal_offering = tanggal_offering
                existing.tanggal_day1 = tanggal_day1
                existing.detail_keterangan_sourcing_hr = detail_keterangan_sourcing_hr
                existing.detail_keterangan_shortlist_cv = detail_keterangan_shortlist_cv
                existing.detail_keterangan_psikotes = detail_keterangan_psikotes
                existing.detail_keterangan_hr_interview = detail_keterangan_hr_interview
                existing.detail_keterangan_user_interview = detail_keterangan_user_interview
                existing.detail_keterangan_offering = detail_keterangan_offering
                existing.detail_keterangan_day1 = detail_keterangan_day1
                existing.notes = notes_val
                existing.kode_psikotes = kode_psikotes_val
                existing.nilai_logika = nilai_logika_val
                existing.nilai_iq = nilai_iq_val
                existing.nilai_daya_tangkap = nilai_daya_tangkap_val
                existing.nilai_ra = nilai_ra_val
                existing.disc = disc_val
                existing.technical_test_case_study = technical_test_case_study_val
                existing.detail_keterangan_technical_test = detail_keterangan_technical_test
                existing.tanggal_technical_test = tanggal_technical_test
                existing.market_visit = market_visit_val
                existing.detail_market_visit = detail_market_visit
                existing.tanggal_market_visit = tanggal_market_visit
                existing.panel_interview = panel_interview_val
                existing.detail_keterangan_panel_interview = detail_keterangan_panel_interview
                existing.tanggal_panel_interview = tanggal_panel_interview
                existing.reference_check = reference_check_val
                existing.detail_keterangan_reference_check = detail_keterangan_reference_check
                existing.tanggal_reference_check = tanggal_reference_check
                existing.mcu = mcu_val
                existing.detail_keterangan_mcu = detail_keterangan_mcu
                existing.tanggal_mcu = tanggal_mcu

                if is_blacklisted and not existing.is_blacklisted:
                    existing.is_blacklisted = True
                    existing.blacklisted_at = datetime.now()
                    existing.blacklisted_by = user_id
                    existing.blacklist_reason = blacklist_reason or 'Dari file upload'
                elif not is_blacklisted and existing.is_blacklisted:
                    existing.is_blacklisted = False
                    existing.blacklisted_at = None
                    existing.blacklisted_by = None
                    existing.blacklist_reason = None

                existing.last_updated_at = datetime.now()
                existing.last_compile_action = "UPDATE"
                updated += 1
            else:
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
                    jurusan_lainnya=jurusan_lainnya_val,
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
                    sourcing_freelance=sourcing_freelance_val,
                    sourcing_hr=sourcing_hr_val,
                    shortlist_cv=shortlist_cv_val,
                    psikotes=psikotes_val,
                    hr_interview=hr_interview_val,
                    user_interview=user_interview_val,
                    offering=offering_val,
                    day1=day1_val,
                    tanggal_sourcing_freelance=tanggal_sourcing_freelance,
                    tanggal_sourcing=tanggal_sourcing,
                    tanggal_shortlist_cv=tanggal_shortlist_cv,
                    tanggal_psikotes=tanggal_psikotes,
                    tanggal_hr_interview=tanggal_hr_interview,
                    tanggal_user_interview=tanggal_user_interview,
                    tanggal_offering=tanggal_offering,
                    tanggal_day1=tanggal_day1,
                    detail_keterangan_sourcing_hr=detail_keterangan_sourcing_hr,
                    detail_keterangan_shortlist_cv=detail_keterangan_shortlist_cv,
                    detail_keterangan_psikotes=detail_keterangan_psikotes,
                    detail_keterangan_hr_interview=detail_keterangan_hr_interview,
                    detail_keterangan_user_interview=detail_keterangan_user_interview,
                    detail_keterangan_offering=detail_keterangan_offering,
                    detail_keterangan_day1=detail_keterangan_day1,
                    notes=notes_val,
                    kode_psikotes=kode_psikotes_val,
                    nilai_logika=nilai_logika_val,
                    nilai_iq=nilai_iq_val,
                    nilai_daya_tangkap=nilai_daya_tangkap_val,
                    nilai_ra=nilai_ra_val,
                    disc=disc_val,
                    technical_test_case_study=technical_test_case_study_val,
                    detail_keterangan_technical_test=detail_keterangan_technical_test,
                    tanggal_technical_test=tanggal_technical_test,
                    market_visit=market_visit_val,
                    detail_market_visit=detail_market_visit,
                    tanggal_market_visit=tanggal_market_visit,
                    panel_interview=panel_interview_val,
                    detail_keterangan_panel_interview=detail_keterangan_panel_interview,
                    tanggal_panel_interview=tanggal_panel_interview,
                    reference_check=reference_check_val,
                    detail_keterangan_reference_check=detail_keterangan_reference_check,
                    tanggal_reference_check=tanggal_reference_check,
                    mcu=mcu_val,
                    detail_keterangan_mcu=detail_keterangan_mcu,
                    tanggal_mcu=tanggal_mcu,
                    is_blacklisted=is_blacklisted,
                    blacklisted_at=datetime.now() if is_blacklisted else None,
                    blacklisted_by=user_id if is_blacklisted else None,
                    blacklist_reason=blacklist_reason if is_blacklisted else None,
                    source_user_id=user_id,
                    source_cycle_id=cycle_id,
                    source_file=safe_string_for_db(file_name, max_length=255),
                    source_file_hash=safe_string_for_db(file_hash, max_length=64),
                    created_at=datetime.now(),
                    last_compile_action="INSERT"
                )
                db.add(new_sourcing)
                imported += 1

        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
            db.rollback()

    if errors:
        db.rollback()
        return {
            "success": False,
            "imported": imported,
            "updated": updated,
            "errors": errors,
            "warnings": warnings
        }

    try:
        db.commit()
        return {
            "success": True,
            "imported": imported,
            "updated": updated,
            "errors": [],
            "warnings": warnings
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "imported": imported,
            "updated": updated,
            "errors": [str(e)],
            "warnings": warnings
        }


def compile_db_kode_posisi(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                           file_name: str, file_hash: str):
    errors = []
    imported = 0

    if db.is_active:
        db.rollback()

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


def tag_blacklist(db: Session, kode_unik: str, user_id: int, reason: str = None):
    candidate = db.query(DBSourcing).filter(DBSourcing.kode_unik == kode_unik).first()
    if not candidate:
        return {"success": False, "error": f"Kandidat dengan kode_unik '{kode_unik}' tidak ditemukan"}

    candidate.is_blacklisted = True
    candidate.blacklisted_at = datetime.now()
    candidate.blacklisted_by = user_id
    if reason:
        candidate.blacklist_reason = safe_string_for_db(reason, max_length=500)
    candidate.last_updated_at = datetime.now()

    db.commit()
    return {"success": True, "message": f"Kandidat {candidate.nama} berhasil di-blacklist"}


def untag_blacklist(db: Session, kode_unik: str, user_id: int):
    candidate = db.query(DBSourcing).filter(DBSourcing.kode_unik == kode_unik).first()
    if not candidate:
        return {"success": False, "error": f"Kandidat dengan kode_unik '{kode_unik}' tidak ditemukan"}

    candidate.is_blacklisted = False
    candidate.blacklisted_at = None
    candidate.blacklisted_by = None
    candidate.blacklist_reason = None
    candidate.last_updated_at = datetime.now()

    db.commit()
    return {"success": True, "message": f"Kandidat {candidate.nama} berhasil di-unblacklist"}


def get_blacklisted_candidates(db: Session, limit: int = 100):
    return db.query(DBSourcing).filter(
        DBSourcing.is_blacklisted == True
    ).order_by(
        DBSourcing.blacklisted_at.desc()
    ).limit(limit).all()
