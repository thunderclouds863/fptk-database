import pandas as pd
import re
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

def parse_date_dmy(value) -> datetime:
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, datetime):
        return value.date() if hasattr(value, 'date') else value
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
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

# ============================================================
# FUNGSI SLA - MIRIP VBA
# ============================================================

def calculate_sla_days(level_number: int) -> int:
    """
    Hitung SLA days berdasarkan Level Number.
    VBA: Level 1-3 = 30, Level 4 = 45, Level 5 = 60
    """
    if level_number <= 3:
        return 30
    elif level_number == 4:
        return 45
    elif level_number >= 5:
        return 60
    else:
        return 30

def calculate_deadline_sla(fptk_date_real: date, sla_days: int) -> date:
    """Hitung Deadline SLA = FPTK Date Real + SLA Days"""
    if fptk_date_real and sla_days > 0:
        return fptk_date_real + timedelta(days=sla_days)
    return None

def calculate_detail_sla(status: str, deadline_sla, offering_date=None) -> str:
    """
    Hitung Detail SLA berdasarkan Status, Deadline, dan Offering Date.
    Mirip VBA CalculateSLAStatusFPTK
    
    Rules:
    - Status OP + deadline < today → "OP Tidak Lulus SLA"
    - Status OP + deadline >= today → "OP Belum Lewat SLA"
    - Status Closed + deadline < offering → "Closed Tidak Lulus SLA"
    - Status Closed + deadline >= offering → "Closed Lulus SLA"
    - Status Cancel → "Cancel FPTK"
    - Fallback: OP Tidak Lulus SLA / OP Belum Lewat SLA
    """
    # Parse dates jika string
    if isinstance(deadline_sla, str):
        deadline_sla = parse_date_dmy(deadline_sla)
    if isinstance(offering_date, str):
        offering_date = parse_date_dmy(offering_date)
    
    # Pastikan tipe data benar
    if deadline_sla and not isinstance(deadline_sla, date):
        deadline_sla = None
    if offering_date and not isinstance(offering_date, date):
        offering_date = None
    
    status_lower = status.lower() if status else ""
    today = date.today()
    
    # CASE 1: OP / OPEN
    if status_lower in ["op", "open"]:
        if deadline_sla and deadline_sla < today:
            return "OP Tidak Lulus SLA"
        else:
            return "OP Belum Lewat SLA"
    
    # CASE 2: CLOSED / CLOSE
    elif status_lower in ["closed", "close"]:
        if deadline_sla and offering_date and deadline_sla < offering_date:
            return "Closed Tidak Lulus SLA"
        else:
            return "Closed Lulus SLA"
    
    # CASE 3: CANCEL / CANCELLED
    elif status_lower in ["cancel", "cancelled", "cancel fptk"]:
        return "Cancel FPTK"
    
    # CASE 4: FALLBACK (jika status tidak dikenal)
    else:
        if deadline_sla and deadline_sla < today:
            return "OP Tidak Lulus SLA"
        else:
            return "OP Belum Lewat SLA"

def get_sla_option_list() -> list:
    """Daftar pilihan Detail SLA untuk dropdown (mirip VBA)"""
    return [
        "OP Belum Lewat SLA",
        "OP Tidak Lulus SLA",
        "Closed Lulus SLA",
        "Closed Tidak Lulus SLA",
        "Cancel FPTK"
    ]

def is_valid_detail_sla(value: str) -> bool:
    """Cek apakah Detail SLA valid"""
    valid_options = [
        "OP Belum Lewat SLA",
        "OP Tidak Lulus SLA",
        "Closed Lulus SLA",
        "Closed Tidak Lulus SLA",
        "Cancel FPTK"
    ]
    return value in valid_options

def calculate_filter_kategorisasi(posisi: str, level_number: int) -> str:
    """Hitung Filter Kategorisasi FPTK"""
    posisi_lower = posisi.lower() if posisi else ""
    
    # PRIORITY 1: CLAP FGDP (Cimory/Fresh)
    if posisi_lower.startswith('cimory') or posisi_lower.startswith('fresh'):
        return 'CLAP FGDP'
    
    # PRIORITY 2: Level based
    elif level_number in [1, 2]:
        return 'Level 1-2'
    elif level_number == 3:
        return 'Level 3'
    elif level_number == 4:
        return 'Level 4'
    else:
        return ''

def parse_phone(value) -> str:
    """Bersihkan nomor telepon (hanya angka dan +)"""
    if pd.isna(value) or value is None:
        return ""
    s = str(value).strip()
    s = re.sub(r'[^0-9+]', '', s)
    return s

def is_valid_email(value) -> bool:
    """Cek apakah email valid"""
    if pd.isna(value) or value is None:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, str(value).strip()))
