import pandas as pd
import re
from datetime import datetime
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
    s = str(value).strip()
    # Try dd/mm/yyyy or dd-mm-yyyy
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

def get_current_cycle(db):
    """Get current active upload cycle"""
    from core.models import UploadCycle
    cycle = db.query(UploadCycle).filter(UploadCycle.ended_at.is_(None)).order_by(UploadCycle.created_at.desc()).first()
    return cycle

def get_user_status(db, user_id, cycle_id):
    from core.models import UploadStatus
    status = db.query(UploadStatus).filter(
        UploadStatus.user_id == user_id,
        UploadStatus.cycle_id == cycle_id
    ).first()
    return status.status if status else "Belum Mulai"

def update_user_status(db, user_id, cycle_id, status):
    from core.models import UploadStatus
    record = db.query(UploadStatus).filter(
        UploadStatus.user_id == user_id,
        UploadStatus.cycle_id == cycle_id
    ).first()
    if record:
        record.status = status
        if status == "Done":
            record.done_at = datetime.now()
    else:
        record = UploadStatus(
            user_id=user_id,
            cycle_id=cycle_id,
            status=status
        )
        db.add(record)
    db.commit()
    return record

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
