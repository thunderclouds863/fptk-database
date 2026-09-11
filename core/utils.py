import pandas as pd
import re
import math
from datetime import datetime, date, timedelta
import streamlit as st


# ============================================================
# NORMALIZE FUNCTIONS
# ============================================================

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

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, (int, float)):
        try:
            base = datetime(1899, 12, 30).date()
            return base + timedelta(days=float(value))
        except:
            pass

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
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, pd.Series):
        value = value.iloc[0] if len(value) > 0 else default
    if isinstance(value, (list, tuple)):
        value = value[0] if len(value) > 0 else default
    if value is None:
        return default
    return str(value).strip()


def safe_boolean_char(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 'V' if value else 'X'
    if isinstance(value, float) and math.isnan(value):
        return None
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


# ============================================================
# SAFE DATE - DIPERBAIKI UNTUK HANDLE NaT
# ============================================================

def safe_date(value):
    """
    Safely convert various date formats to date object.
    Returns None for NaT, NaN, None, or invalid values.
    """
    if value is None:
        return None

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

    if isinstance(value, pd.Series):
        if len(value) > 0:
            val = value.iloc[0]
            try:
                if pd.isna(val):
                    return None
            except:
                pass
            if hasattr(val, '__class__') and 'NaT' in str(val.__class__):
                return None
            return safe_date(val)
        return None

    return None


def sanitize_date_value(val):
    return safe_date(val)


# ============================================================
# FUNGSI GET_SINGLE_VALUE
# ============================================================

def get_single_value(value):
    """
    Helper untuk mendapatkan nilai tunggal dari berbagai tipe data.
    """
    if value is None:
        return None

    if isinstance(value, pd.Series):
        if len(value) > 0:
            val = value.iloc[0]
            try:
                if pd.isna(val):
                    return None
            except:
                pass
            return val
        return None

    if isinstance(value, pd.DataFrame):
        if not value.empty:
            val = value.iloc[0, 0] if value.shape[1] > 0 else None
            try:
                if pd.isna(val):
                    return None
            except:
                pass
            return val
        return None

    if isinstance(value, (list, tuple)):
        if len(value) > 0:
            val = value[0]
            try:
                if pd.isna(val):
                    return None
            except:
                pass
            return val
        return None

    try:
        if pd.isna(value):
            return None
    except:
        pass

    return value


# ============================================================
# FUNGSI SLA
# ============================================================

def calculate_sla_days(level_number: int) -> int:
    if level_number <= 3:
        return 30
    elif level_number == 4:
        return 45
    elif level_number >= 5:
        return 60
    else:
        return 30


def calculate_deadline_sla(fptk_date_real, sla_days: int):
    if fptk_date_real and sla_days > 0:
        if isinstance(fptk_date_real, datetime):
            fptk_date_real = fptk_date_real.date()
        elif isinstance(fptk_date_real, pd.Timestamp):
            fptk_date_real = fptk_date_real.date()

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
        if deadline_sla and offering_date and deadline_sla < offering_date:
            return "Closed Tidak Lulus SLA"
        else:
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

    if "keluar" in alasan_lower or "mutasi" in alasan_lower or "promosi" in alasan_lower or "replace" in alasan_lower:
        return "REPLACEMENT"
    elif "penambahan" in alasan_lower or "jabatan baru" in alasan_lower or "new" in alasan_lower:
        return "NEW"
    else:
        return "REPLACEMENT"


def _ensure_date(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except:
        pass

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, pd.Timestamp):
        return value.date()

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
    valid_options = [
        "OP Belum Lewat SLA",
        "OP Tidak Lulus SLA",
        "Closed Lulus SLA",
        "Closed Tidak Lulus SLA",
        "Cancel FPTK"
    ]
    return value in valid_options


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
    else:
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


# ============================================================
# FUNGSI DB KODE POSISI (AUTO-FILL)
# ============================================================

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
    """
    Normalisasi nilai boolean ke 'V' atau 'X' saja.
    """
    if value is None:
        return None

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


# ============================================================
# ⭐ FILTER OPTIONS FROM DB (DINAMIS) — DIPERBAIKI
# ============================================================
# Prioritas ambil dari tabel FPTK (karena berisi data real).
# Fallback ke master_dropdown / users kalau FPTK kosong.
# ============================================================

@st.cache_data(ttl=3600)
def get_filter_options_from_db():
    """
    Ambil semua opsi filter dari database (DINAMIS).
    Cache 1 jam, refresh manual via sidebar.

    Returns:
        dict: {
            "pic_options": list,
            "bu_options": list,
            "direktorat_options": list,
            "filter_kategorisasi_options": list,
            "sumber_options": list,
            "model_options": list,
            "divisi_options": list,
            "dept_options": list,
            "rekruter_options": list,
            "level_options": list,
            "status_options": list,
        }
    """
    from core.database import SessionLocal
    from core.models import User, MasterDropdown, FPTK, DBSourcing

    db = SessionLocal()
    try:
        # ============================================================
        # 1. PIC RECRUITER — ambil dari FPTK dulu
        # ============================================================
        pic_rows = db.query(FPTK.pic_recruiter).filter(
            FPTK.pic_recruiter.isnot(None),
            FPTK.pic_recruiter != ""
        ).distinct().all()
        pic_options = sorted(set([r[0] for r in pic_rows if r[0]]))

        # Fallback ke tabel users kalau FPTK kosong
        if not pic_options:
            pic_rows = db.query(User.pic_recruiter).filter(
                User.pic_recruiter.isnot(None),
                User.pic_recruiter != ""
            ).distinct().all()
            pic_options = sorted(set([r[0] for r in pic_rows if r[0]]))

        # ============================================================
        # 2. BUSINESS UNIT — ambil dari FPTK dulu
        # ============================================================
        bu_rows = db.query(FPTK.business_unit).filter(
            FPTK.business_unit.isnot(None),
            FPTK.business_unit != ""
        ).distinct().all()
        bu_options = sorted(set([r[0] for r in bu_rows if r[0]]))

        # Fallback ke master_dropdown
        if not bu_options:
            bu_rows = db.query(MasterDropdown.bu).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.bu.isnot(None),
                MasterDropdown.bu != ""
            ).distinct().all()
            bu_options = sorted(set([r[0] for r in bu_rows if r[0]]))

        # ============================================================
        # 3. DIREKTORAT — ambil dari FPTK dulu
        # ============================================================
        dir_rows = db.query(FPTK.direktorat).filter(
            FPTK.direktorat.isnot(None),
            FPTK.direktorat != ""
        ).distinct().all()
        direktorat_options = sorted(set([r[0] for r in dir_rows if r[0]]))

        # Fallback ke master_dropdown
        if not direktorat_options:
            dir_rows = db.query(MasterDropdown.nama_direktorat).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.nama_direktorat.isnot(None),
                MasterDropdown.nama_direktorat != ""
            ).distinct().all()
            direktorat_options = sorted(set([r[0] for r in dir_rows if r[0]]))

        # ============================================================
        # 4. FILTER KATEGORISASI FPTK — ambil dari FPTK dulu
        # ============================================================
        filter_kat_rows = db.query(FPTK.filter_kategorisasi_fptk).filter(
            FPTK.filter_kategorisasi_fptk.isnot(None),
            FPTK.filter_kategorisasi_fptk != ""
        ).distinct().all()
        filter_kategorisasi_options = sorted(set([r[0] for r in filter_kat_rows if r[0]]))

        # Fallback ke master_dropdown
        if not filter_kategorisasi_options:
            filter_kat_rows = db.query(MasterDropdown.filter_fptk).filter(
                MasterDropdown.is_active == True,
                MasterDropdown.filter_fptk.isnot(None),
                MasterDropdown.filter_fptk != ""
            ).distinct().all()
            filter_kategorisasi_options = sorted(set([r[0] for r in filter_kat_rows if r[0]]))

        # ============================================================
        # 5. SUMBER SOURCING — dari master_dropdown
        # ============================================================
        sumber_rows = db.query(MasterDropdown.sumber_sourcing).filter(
            MasterDropdown.is_active == True,
            MasterDropdown.sumber_sourcing.isnot(None),
            MasterDropdown.sumber_sourcing != ""
        ).distinct().all()
        sumber_options = sorted(set([r[0] for r in sumber_rows if r[0]]))

        # ============================================================
        # 6. MODEL REKRUTMEN — dari master_dropdown
        # ============================================================
        model_rows = db.query(MasterDropdown.model).filter(
            MasterDropdown.is_active == True,
            MasterDropdown.model.isnot(None),
            MasterDropdown.model != ""
        ).distinct().all()
        model_options = sorted(set([r[0] for r in model_rows if r[0]]))

        # ============================================================
        # 7. DIVISI — dari master_dropdown
        # ============================================================
        divisi_rows = db.query(MasterDropdown.divisi).filter(
            MasterDropdown.is_active == True,
            MasterDropdown.divisi.isnot(None),
            MasterDropdown.divisi != ""
        ).distinct().all()
        divisi_options = sorted(set([r[0] for r in divisi_rows if r[0]]))

        # ============================================================
        # 8. DEPARTMENT — dari master_dropdown
        # ============================================================
        dept_rows = db.query(MasterDropdown.department).filter(
            MasterDropdown.is_active == True,
            MasterDropdown.department.isnot(None),
            MasterDropdown.department != ""
        ).distinct().all()
        dept_options = sorted(set([r[0] for r in dept_rows if r[0]]))

        # ============================================================
        # 9. REKRUTER — dari DBSourcing
        # ============================================================
        rekruter_rows = db.query(DBSourcing.rekruter).filter(
            DBSourcing.rekruter.isnot(None),
            DBSourcing.rekruter != ""
        ).distinct().all()
        rekruter_options = sorted(set([r[0] for r in rekruter_rows if r[0]]))

        # ============================================================
        # 10. LEVEL FPTK — hardcoded enum
        # ============================================================
        level_options = ["1A", "1B", "1C", "2A", "2B", "2C",
                         "3A", "3B", "3C", "4A", "4B", "5A", "5B"]

        # ============================================================
        # 11. STATUS — hardcoded enum
        # ============================================================
        status_options = ["OP", "Closed", "Cancel"]

        return {
            "pic_options": pic_options,
            "bu_options": bu_options,
            "direktorat_options": direktorat_options,
            "filter_kategorisasi_options": filter_kategorisasi_options,
            "sumber_options": sumber_options,
            "model_options": model_options,
            "divisi_options": divisi_options,
            "dept_options": dept_options,
            "rekruter_options": rekruter_options,
            "level_options": level_options,
            "status_options": status_options,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "pic_options": [],
            "bu_options": [],
            "direktorat_options": [],
            "filter_kategorisasi_options": [],
            "sumber_options": [],
            "model_options": [],
            "divisi_options": [],
            "dept_options": [],
            "rekruter_options": [],
            "level_options": ["1A", "1B", "1C", "2A", "2B", "2C",
                              "3A", "3B", "3C", "4A", "4B", "5A", "5B"],
            "status_options": ["OP", "Closed", "Cancel"],
        }
    finally:
        db.close()


@st.cache_data(ttl=3600)
def get_filter_options_from_db_simple():
    """
    Versi simple — hanya PIC, BU, Direktorat (untuk backward compatibility).
    """
    opts = get_filter_options_from_db()
    return (
        ["Semua"] + opts["pic_options"],
        ["Semua"] + opts["bu_options"],
        ["Semua"] + opts["direktorat_options"],
    )
