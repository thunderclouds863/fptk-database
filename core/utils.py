import pandas as pd
import re
import math
from datetime import datetime, date, timedelta
import streamlit as st

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

def safe_date(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, str):
        return parse_date_dmy(value)
    return None

def sanitize_date_value(val):
    return safe_date(val)

# ============================================================
# FUNGSI GET_SINGLE_VALUE - DIPERBAIKI
# ============================================================

def get_single_value(value):
    """
    Helper untuk mendapatkan nilai tunggal dari berbagai tipe data.
    - Jika pd.Series, ambil nilai pertama
    - Jika pd.DataFrame, ambil nilai pertama
    - Jika list/tuple, ambil nilai pertama
    - Jika None/NaN, return None
    """
    # Handle None
    if value is None:
        return None
    
    # Handle pandas Series
    if isinstance(value, pd.Series):
        if len(value) > 0:
            val = value.iloc[0]
            if pd.isna(val):
                return None
            return val
        return None
    
    # Handle pandas DataFrame
    if isinstance(value, pd.DataFrame):
        if not value.empty:
            val = value.iloc[0, 0] if value.shape[1] > 0 else None
            if pd.isna(val):
                return None
            return val
        return None
    
    # Handle list/tuple
    if isinstance(value, (list, tuple)):
        if len(value) > 0:
            val = value[0]
            if pd.isna(val):
                return None
            return val
        return None
    
    # Handle NaN (pandas)
    try:
        if pd.isna(value):
            return None
    except:
        # Jika pd.isna gagal, lanjutkan
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
    if value is None or pd.isna(value):
        return None
    
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
