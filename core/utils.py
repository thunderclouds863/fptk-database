# core/utils.py
import re
import math
import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta


def normalize_key(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    s = str(value).strip().upper()
    s = re.sub(r'[^\w]', '', s)
    return s


def normalize_text(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    s = str(value).strip().upper()
    s = re.sub(r'\s+', ' ', s)
    return s


def parse_date_dmy(value):
    if pd.isna(value) or value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, pd.Timestamp):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, (int, float)):
        try:
            base = datetime(1899, 12, 30).date()
            result = base + timedelta(days=float(value))
            if 1900 <= result.year <= 2100:
                return result
        except Exception:
            pass
        return None

    if isinstance(value, str):
        s = str(value).strip()
        if ' ' in s:
            s = s.split(' ')[0]

        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y-%m-%d', '%Y/%m/%d']:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue

    return None


def safe_int(value, default=0):
    if pd.isna(value) or value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    if pd.isna(value) or value is None:
        return default
    try:
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return default


def safe_string(value, default=''):
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    if isinstance(value, pd.Series):
        value = value.iloc[0] if len(value) > 0 else default
    if isinstance(value, (list, tuple)):
        value = value[0] if len(value) > 0 else default

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return str(value).strip()


def safe_boolean_char(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 'V' if value else 'X'

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, (int, float)):
        return 'V' if value else 'X'
    if isinstance(value, str):
        val = value.strip().upper()
        if val in ['V', 'Y', 'YA', 'YES', 'TRUE', '1']:
            return 'V'
        if val in ['X', 'N', 'NO', 'FALSE', '0']:
            return 'X'
        return None
    if isinstance(value, pd.Series):
        return safe_boolean_char(value.iloc[0]) if len(value) > 0 else None
    return None


def safe_date(value):
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

    if isinstance(value, pd.Series):
        if len(value) > 0:
            return safe_date(value.iloc[0])
        return None

    return None


def sanitize_date_value(val):
    return safe_date(val)


def get_single_value(value):
    if value is None:
        return None

    if isinstance(value, pd.Series):
        if len(value) > 0:
            val = value.iloc[0]
            try:
                if pd.isna(val):
                    return None
            except Exception:
                pass
            return val
        return None

    if isinstance(value, pd.DataFrame):
        if not value.empty:
            val = value.iloc[0, 0] if value.shape[1] > 0 else None
            try:
                if pd.isna(val):
                    return None
            except Exception:
                pass
            return val
        return None

    if isinstance(value, (list, tuple)):
        if len(value) > 0:
            val = value[0]
            try:
                if pd.isna(val):
                    return None
            except Exception:
                pass
            return val
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


def calculate_sla_days(level_number: int) -> int:
    if level_number is None:
        return 30
    if level_number <= 3:
        return 30
    elif level_number == 4:
        return 45
    elif level_number >= 5:
        return 60
    return 30


def calculate_deadline_sla(fptk_date_real, sla_days: int):
    if fptk_date_real and sla_days and sla_days > 0:
        fptk_date_real = _ensure_date(fptk_date_real)
        if isinstance(fptk_date_real, date):
            return fptk_date_real + timedelta(days=sla_days)
    return None


def calculate_detail_sla(status: str, deadline_sla, offering_date=None) -> str:
    deadline_sla = _ensure_date(deadline_sla)
    offering_date = _ensure_date(offering_date)

    today = date.today()
    status_lower = status.lower() if status else ""

    if status_lower in ["op", "open"]:
        if deadline_sla and deadline_sla < today:
            return "OP Tidak Lulus SLA"
        else:
            return "OP Belum Lewat SLA"

    elif status_lower in ["closed", "close"]:
        if deadline_sla and offering_date:
            if offering_date <= deadline_sla:
                return "Closed Lulus SLA"
            else:
                return "Closed Tidak Lulus SLA"
        else:
            if deadline_sla and deadline_sla < today:
                return "Closed Tidak Lulus SLA"
            return "Closed Lulus SLA"

    elif status_lower in ["cancel", "cancelled", "cancel fptk"]:
        return "Cancel FPTK"

    else:
        if deadline_sla and deadline_sla < today:
            return "OP Tidak Lulus SLA"
        else:
            return "OP Belum Lewat SLA"


def determine_category_fptk(alasan: str) -> str:
    alasan_lower = alasan.lower() if alasan else ""

    if any(k in alasan_lower for k in ["keluar", "mutasi", "promosi", "replace"]):
        return "REPLACEMENT"
    elif any(k in alasan_lower for k in ["penambahan", "jabatan baru", "new"]):
        return "NEW"
    return "REPLACEMENT"


def _ensure_date(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, pd.Timestamp):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return parse_date_dmy(value)

    return None


def get_sla_option_list() -> list:
    return [
        "OP Belum Lewat SLA",
        "OP Tidak Lulus SLA",
        "Closed Lulus SLA",
        "Closed Tidak Lulus SLA",
        "Cancel FPTK"
    ]


def is_valid_detail_sla(value: str) -> bool:
    return value in get_sla_option_list()


def calculate_filter_kategorisasi(posisi: str, level_number: int) -> str:
    posisi_lower = posisi.lower() if posisi else ""

    if posisi_lower.startswith('cimory') or posisi_lower.startswith('fresh'):
        return 'CLAP FGDP'
    elif level_number in [1, 2]:
        return 'Level 1-2'
    elif level_number == 3:
        return 'Level 3'
    elif level_number == 4:
        return 'Level 4'
    return ''


def parse_phone(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    s = str(value).strip()
    s = re.sub(r'[^0-9+]', '', s)
    return s


def is_valid_email(value) -> bool:
    if pd.isna(value) or value is None:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, str(value).strip()))


def get_position_details(db, posisi: str, direktorat: str = None):
    if not posisi:
        return None

    from core.models import DBKodePosisi
    from sqlalchemy import func

    query = db.query(DBKodePosisi).filter(
        func.lower(DBKodePosisi.position) == func.lower(posisi.strip())
    )

    result = None
    if direktorat:
        result = query.filter(
            func.lower(DBKodePosisi.directorate) == func.lower(direktorat.strip())
        ).first()

    if not result:
        result = query.first()

    if result:
        return {
            "kode": result.kode,
            "position": result.position,
            "location": result.location,
            "business_unit": result.business_unit,
            "division_chris": result.division_chris,
            "department_chris": result.department_chris,
            "user_manager": result.user_manager,
            "indirect_user": result.indirect_user,
            "directorate": result.directorate,
            "year": result.year
        }
    return None


def add_to_db_kode_posisi(db, posisi: str, direktorat: str = None, business_unit: str = None,
                          location: str = None, division: str = None, department: str = None,
                          user_manager: str = None, indirect_user: str = None, kode: str = None):
    if not posisi:
        return None

    from core.models import DBKodePosisi
    from sqlalchemy import func

    existing = db.query(DBKodePosisi).filter(
        func.lower(DBKodePosisi.position) == func.lower(posisi.strip())
    ).first()

    if existing:
        if direktorat:
            existing.directorate = direktorat
        if business_unit:
            existing.business_unit = business_unit
        if location:
            existing.location = location
        if division:
            existing.division_chris = division
        if department:
            existing.department_chris = department
        if user_manager:
            existing.user_manager = user_manager
        if indirect_user:
            existing.indirect_user = indirect_user
        if kode:
            existing.kode = kode
        db.commit()
        db.refresh(existing)
        return existing

    new_entry = DBKodePosisi(
        kode=kode or "",
        position=posisi.strip(),
        location=location or "",
        business_unit=business_unit or "",
        division_chris=division or "",
        department_chris=department or "",
        user_manager=user_manager or "",
        indirect_user=indirect_user or "",
        directorate=direktorat or "",
        year=datetime.now().year
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry


def normalize_boolean_to_vx(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, bool):
        return 'V' if value else 'X'

    if isinstance(value, (int, float)):
        return 'V' if value else 'X'

    if isinstance(value, str):
        v = value.strip().upper()
        if v in ['V', 'Y', 'YA', 'YES', 'TRUE', '1', 'LOLOS', 'LULUS']:
            return 'V'
        if v in ['X', 'N', 'NO', 'FALSE', '0', 'TIDAK', 'GAGAL']:
            return 'X'
        if len(v) > 0:
            first = v[0]
            if first in ['V', 'Y']:
                return 'V'
            if first in ['X', 'N']:
                return 'X'
        return None

    return None


def extract_label_value_pairs(text: str) -> dict:
    if not text:
        return {}

    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [l.strip() for l in text.split('\n')]

    label_indicators = [
        "nama jabatan yang dicari", "jabatan yang dicari", "nama jabatan",
        "posisi", "position",
        "alasan permintaan fptk", "alasan fptk", "alasan",
        "pt/business unit", "pt / business unit", "business unit",
        "divisi", "division",
        "departemen", "department", "dept",
        "level posisi", "level fptk", "level",
        "lokasi kerja", "lokasi hr", "penempatan",
        "jumlah posisi yang dicari", "jumlah posisi", "vacancy",
        "status karyawan",
        "status offering", "status join",
        "nama kandidat",
        "tanggal offering", "start date",
        "nik kandidat", "email kandidat",
        "email pic rekruter", "pic rekruter", "pic recruiter",
        "direkrut oleh", "catatan", "remark", "notes",
        "fptk date", "tanggal fptk",
        "range gaji", "tanggal dibutuhkan",
        "pendidikan minimal", "fakultas/jurusan", "jurusan",
        "total pengalaman", "usia",
        "job summary", "outcomes", "capability", "character",
        "status revisi", "log", "struktur organisasi", "sign-off",
        "attachments", "detail fptk", "approval status",
    ]

    stop_values = [
        "enter value here", "-", "add or remove attachments",
        "read only", "see more"
    ]

    result = {}
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        clean_label = re.sub(r'[\*\:]+$', '', line).strip()
        clean_label = re.sub(r'\s*\(Read only\)\s*', '', clean_label, flags=re.IGNORECASE).strip()

        is_label = any(ind == clean_label.lower() or ind in clean_label.lower() for ind in label_indicators)

        if is_label and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                value = lines[j].strip()
                value_clean = re.sub(r'[\*\:]+$', '', value).strip().lower()

                if value and value_clean not in stop_values:
                    next_label_check = value_clean
                    is_next_label = any(ind == next_label_check or ind in next_label_check for ind in label_indicators)

                    if not is_next_label:
                        result[clean_label.lower()] = value
                        i = j + 1
                        continue

        i += 1

    return result


@st.cache_data(ttl=600, show_spinner=False)
def get_filter_options_from_db():
    from core.database import SessionLocal
    from core.models import User, MasterDropdown, FPTK, DBSourcing, DBKodePosisi

    db = SessionLocal()
    try:
        pic_rows = db.query(FPTK.pic_recruiter).filter(
            FPTK.pic_recruiter.isnot(None),
            FPTK.pic_recruiter != ""
        ).distinct().all()
        pic_options = sorted(set([r[0] for r in pic_rows if r[0]]))

        if not pic_options:
            pic_rows = db.query(User.pic_recruiter).filter(
                User.pic_recruiter.isnot(None),
                User.pic_recruiter != ""
            ).distinct().all()
            pic_options = sorted(set([r[0] for r in pic_rows if r[0]]))

        bu_rows = db.query(FPTK.business_unit).filter(
            FPTK.business_unit.isnot(None),
            FPTK.business_unit != ""
        ).distinct().all()
        bu_options = sorted(set([r[0] for r in bu_rows if r[0]]))

        if not bu_options:
            bu_rows = db.query(MasterDropdown.bu).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.bu.isnot(None),
                MasterDropdown.bu != ""
            ).distinct().all()
            bu_options = sorted(set([r[0] for r in bu_rows if r[0]]))

        dir_rows = db.query(FPTK.direktorat).filter(
            FPTK.direktorat.isnot(None),
            FPTK.direktorat != ""
        ).distinct().all()
        direktorat_options = sorted(set([r[0] for r in dir_rows if r[0]]))

        if not direktorat_options:
            dir_rows = db.query(MasterDropdown.nama_direktorat).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.nama_direktorat.isnot(None),
                MasterDropdown.nama_direktorat != ""
            ).distinct().all()
            direktorat_options = sorted(set([r[0] for r in dir_rows if r[0]]))

        filter_kat_rows = db.query(FPTK.filter_kategorisasi_fptk).filter(
            FPTK.filter_kategorisasi_fptk.isnot(None),
            FPTK.filter_kategorisasi_fptk != ""
        ).distinct().all()
        filter_kategorisasi_options = sorted(set([r[0] for r in filter_kat_rows if r[0]]))

        if not filter_kategorisasi_options:
            filter_kat_rows = db.query(MasterDropdown.filter_fptk).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.filter_fptk.isnot(None),
                MasterDropdown.filter_fptk != ""
            ).distinct().all()
            filter_kategorisasi_options = sorted(set([r[0] for r in filter_kat_rows if r[0]]))

        divisi_rows = db.query(FPTK.divisi).filter(
            FPTK.divisi.isnot(None),
            FPTK.divisi != ""
        ).distinct().all()
        divisi_options = sorted(set([r[0] for r in divisi_rows if r[0]]))

        if not divisi_options:
            divisi_rows = db.query(MasterDropdown.divisi).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.divisi.isnot(None),
                MasterDropdown.divisi != ""
            ).distinct().all()
            divisi_options = sorted(set([r[0] for r in divisi_rows if r[0]]))

        if not divisi_options:
            divisi_rows = db.query(DBKodePosisi.division_chris).filter(
                DBKodePosisi.division_chris.isnot(None),
                DBKodePosisi.division_chris != ""
            ).distinct().all()
            divisi_options = sorted(set([r[0] for r in divisi_rows if r[0]]))

        dept_rows = db.query(FPTK.department).filter(
            FPTK.department.isnot(None),
            FPTK.department != ""
        ).distinct().all()
        dept_options = sorted(set([r[0] for r in dept_rows if r[0]]))

        if not dept_options:
            dept_rows = db.query(MasterDropdown.department).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.department.isnot(None),
                MasterDropdown.department != ""
            ).distinct().all()
            dept_options = sorted(set([r[0] for r in dept_rows if r[0]]))

        if not dept_options:
            dept_rows = db.query(DBKodePosisi.department_chris).filter(
                DBKodePosisi.department_chris.isnot(None),
                DBKodePosisi.department_chris != ""
            ).distinct().all()
            dept_options = sorted(set([r[0] for r in dept_rows if r[0]]))

        sumber_rows = db.query(MasterDropdown.sumber_sourcing).filter(
            MasterDropdown.is_active == True,
            MasterDropdown.sumber_sourcing.isnot(None),
            MasterDropdown.sumber_sourcing != ""
        ).distinct().all()
        sumber_options = sorted(set([r[0] for r in sumber_rows if r[0]]))

        model_rows = db.query(MasterDropdown.model).filter(
            MasterDropdown.is_active == True,
            MasterDropdown.model.isnot(None),
            MasterDropdown.model != ""
        ).distinct().all()
        model_options = sorted(set([r[0] for r in model_rows if r[0]]))

        rekruter_rows = db.query(DBSourcing.rekruter).filter(
            DBSourcing.rekruter.isnot(None),
            DBSourcing.rekruter != ""
        ).distinct().all()
        rekruter_options = sorted(set([r[0] for r in rekruter_rows if r[0]]))

        level_options = ["1A", "1B", "1C", "2A", "2B", "2C",
                         "3A", "3B", "3C", "4A", "4B", "5A", "5B"]
        status_options = ["OP", "Closed", "Cancel"]

        return {
            "pic_options": pic_options,
            "bu_options": bu_options,
            "direktorat_options": direktorat_options,
            "filter_kategorisasi_options": filter_kategorisasi_options,
            "divisi_options": divisi_options,
            "dept_options": dept_options,
            "sumber_options": sumber_options,
            "model_options": model_options,
            "rekruter_options": rekruter_options,
            "level_options": level_options,
            "status_options": status_options,
        }
    except Exception:
        import traceback
        traceback.print_exc()
        return {
            "pic_options": [],
            "bu_options": [],
            "direktorat_options": [],
            "filter_kategorisasi_options": [],
            "divisi_options": [],
            "dept_options": [],
            "sumber_options": [],
            "model_options": [],
            "rekruter_options": [],
            "level_options": ["1A", "1B", "1C", "2A", "2B", "2C",
                              "3A", "3B", "3C", "4A", "4B", "5A", "5B"],
            "status_options": ["OP", "Closed", "Cancel"],
        }
    finally:
        db.close()


@st.cache_data(ttl=600, show_spinner=False)
def get_filter_options_from_db_simple():
    opts = get_filter_options_from_db()
    return (
        ["Semua"] + opts["pic_options"],
        ["Semua"] + opts["bu_options"],
        ["Semua"] + opts["direktorat_options"],
    )
