import pandas as pd
from datetime import datetime
from core.utils import normalize_key, parse_date_dmy, safe_int, safe_float
from core.models import FPTK, MasterDropdown
from sqlalchemy.orm import Session

class ValidationError:
    def __init__(self, row, field, message):
        self.row = row
        self.field = field
        self.message = message

def validate_fptk_file(df: pd.DataFrame, db: Session, user_id: int, is_sto: bool = False):
    """
    Strict validation: if any blocking error -> return None
    Returns: (validated_df, errors_list)
    """
    errors = []
    validated_rows = []
    
    # 1. Check required columns exist
    required_cols = [
        'Kode PIC', 'FPTK Date (Real)', 'Kode Unik', 'Posisi',
        'Business Unit', 'Direktorat', 'Divisi', 'Department',
        'Level FPTK', 'Level Number', 'Alasan Permintaan FPTK',
        'Category FPTK', 'PIC Recruiter', 'Vacancy', 'Status'
    ]
    
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        errors.append(ValidationError(0, "HEADER", f"Kolom tidak ditemukan: {', '.join(missing_cols)}"))
        return None, errors
    
    # 2. Load master data for validation
    master_bu = set()
    master_direktorat = set()
    master_alasan = set()
    master_category = set()
    master_pic = set()
    master_status = {'OP', 'Closed', 'Cancel'}
    
    master_records = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    for m in master_records:
        if m.bu: master_bu.add(m.bu.strip())
        if m.nama_direktorat: master_direktorat.add(m.nama_direktorat.strip())
        if m.alasan: master_alasan.add(m.alasan.strip())
        if m.category_fptk: master_category.add(m.category_fptk.strip())
        if m.pic_recruiter: master_pic.add(m.pic_recruiter.strip())
    
    # 3. Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (header=1)
        row_errors = []
        row_data = {}
        
        # --- Kode PIC ---
        kode_pic = str(row.get('Kode PIC', '')).strip()
        if not kode_pic:
            row_errors.append(ValidationError(row_num, 'Kode PIC', 'Wajib diisi'))
        row_data['kode_pic'] = kode_pic
        
        # --- FPTK Date Real ---
        fptk_date = parse_date_dmy(row.get('FPTK Date (Real)'))
        if not fptk_date:
            row_errors.append(ValidationError(row_num, 'FPTK Date (Real)', 'Wajib diisi dan valid (dd/mm/yyyy)'))
        row_data['fptk_date_real'] = fptk_date
        
        # --- Kode Unik ---
        kode_unik = normalize_key(row.get('Kode Unik'))
        if not kode_unik:
            row_errors.append(ValidationError(row_num, 'Kode Unik', 'Wajib diisi'))
        row_data['kode_unik'] = kode_unik
        
        # --- Posisi ---
        posisi = str(row.get('Posisi', '')).strip()
        if not posisi:
            row_errors.append(ValidationError(row_num, 'Posisi', 'Wajib diisi'))
        row_data['posisi'] = posisi
        
        # --- Business Unit ---
        bu = str(row.get('Business Unit', '')).strip()
        if not bu:
            row_errors.append(ValidationError(row_num, 'Business Unit', 'Wajib diisi'))
        elif bu not in master_bu:
            row_errors.append(ValidationError(row_num, 'Business Unit', f'"{bu}" tidak ada di master dropdown'))
        row_data['business_unit'] = bu
        
        # --- Direktorat ---
        direktorat = str(row.get('Direktorat', '')).strip()
        if not direktorat:
            row_errors.append(ValidationError(row_num, 'Direktorat', 'Wajib diisi'))
        elif direktorat not in master_direktorat:
            row_errors.append(ValidationError(row_num, 'Direktorat', f'"{direktorat}" tidak ada di master dropdown'))
        row_data['direktorat'] = direktorat
        
        # --- Divisi ---
        divisi = str(row.get('Divisi', '')).strip()
        if not divisi:
            row_errors.append(ValidationError(row_num, 'Divisi', 'Wajib diisi'))
        row_data['divisi'] = divisi
        
        # --- Department ---
        department = str(row.get('Department', '')).strip()
        if not department:
            row_errors.append(ValidationError(row_num, 'Department', 'Wajib diisi'))
        row_data['department'] = department
        
        # --- Level FPTK ---
        level_fptk = str(row.get('Level FPTK', '')).strip()
        if not level_fptk:
            row_errors.append(ValidationError(row_num, 'Level FPTK', 'Wajib diisi'))
        elif not re.match(r'^[0-9]+[A-Za-z]$', level_fptk):
            row_errors.append(ValidationError(row_num, 'Level FPTK', f'Format harus seperti 1A, 2B, 3A (input: {level_fptk})'))
        row_data['level_fptk'] = level_fptk
        
        # --- Level Number ---
        level_num = safe_int(row.get('Level Number'))
        if level_num <= 0:
            row_errors.append(ValidationError(row_num, 'Level Number', 'Wajib diisi dan harus angka > 0'))
        # Validate Level Number matches Level FPTK
        if level_fptk and level_num > 0:
            expected = int(re.search(r'^([0-9]+)', level_fptk).group(1)) if re.search(r'^([0-9]+)', level_fptk) else None
            if expected and level_num != expected:
                row_errors.append(ValidationError(row_num, 'Level Number', f'Harus match dengan Level FPTK ({expected})'))
        row_data['level_number'] = level_num
        
        # --- Alasan Permintaan FPTK ---
        alasan = str(row.get('Alasan Permintaan FPTK', '')).strip()
        if not alasan:
            row_errors.append(ValidationError(row_num, 'Alasan Permintaan FPTK', 'Wajib diisi'))
        elif alasan not in master_alasan:
            row_errors.append(ValidationError(row_num, 'Alasan Permintaan FPTK', f'"{alasan}" tidak ada di master dropdown'))
        row_data['alasan_permintaan_fptk'] = alasan
        
        # --- Category FPTK ---
        category = str(row.get('Category FPTK', '')).strip()
        if not category:
            row_errors.append(ValidationError(row_num, 'Category FPTK', 'Wajib diisi'))
        elif category not in master_category:
            row_errors.append(ValidationError(row_num, 'Category FPTK', f'"{category}" tidak ada di master dropdown'))
        row_data['category_fptk'] = category
        
        # --- PIC Recruiter ---
        pic = str(row.get('PIC Recruiter', '')).strip()
        if not pic:
            row_errors.append(ValidationError(row_num, 'PIC Recruiter', 'Wajib diisi'))
        elif pic not in master_pic:
            row_errors.append(ValidationError(row_num, 'PIC Recruiter', f'"{pic}" tidak ada di master dropdown'))
        row_data['pic_recruiter'] = pic
        
        # --- Vacancy ---
        vacancy = safe_int(row.get('Vacancy'))
        if vacancy <= 0:
            row_errors.append(ValidationError(row_num, 'Vacancy', 'Harus angka > 0'))
        row_data['vacancy'] = vacancy
        
        # --- Status ---
        status = str(row.get('Status', '')).strip()
        if not status:
            row_errors.append(ValidationError(row_num, 'Status', 'Wajib diisi'))
        elif status not in master_status:
            row_errors.append(ValidationError(row_num, 'Status', f'Hanya OP, Closed, atau Cancel (input: {status})'))
        row_data['status'] = status
        
        # --- Closed requires Offering Date ---
        if status == 'Closed':
            offering = parse_date_dmy(row.get('Offering Date'))
            if not offering:
                row_errors.append(ValidationError(row_num, 'Offering Date', 'Wajib diisi jika Status = Closed'))
            row_data['offering_date'] = offering
        
        # --- Cancel requires FPTK Cancel Date ---
        if status == 'Cancel':
            cancel = parse_date_dmy(row.get('FPTK Cancel Date'))
            if not cancel:
                row_errors.append(ValidationError(row_num, 'FPTK Cancel Date', 'Wajib diisi jika Status = Cancel'))
            row_data['fptk_cancel_date'] = cancel
        
        # --- If any error in this row, skip row ---
        if row_errors:
            errors.extend(row_errors)
            continue
        
        # Add row data to validated list
        validated_rows.append(row_data)
    
    return validated_rows, errors

def validate_db_sourcing_rows(df: pd.DataFrame):
    """Validate DB Sourcing rows - Sourcing Date mandatory"""
    errors = []
    valid_rows = []
    
    if 'Sourcing Date' not in df.columns:
        errors.append(ValidationError(0, 'HEADER', 'Kolom Sourcing Date tidak ditemukan'))
        return [], errors
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        sourcing_date = parse_date_dmy(row.get('Sourcing Date'))
        if not sourcing_date:
            errors.append(ValidationError(row_num, 'Sourcing Date', 'Wajib diisi dan valid'))
            continue
        valid_rows.append({**row.to_dict(), 'sourcing_date': sourcing_date})
    
    return valid_rows, errors