import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from core.models import FPTK, DBSourcing, DBKodePosisi, MasterDropdown, UploadLog
from core.validator import validate_fptk_file, validate_db_sourcing_rows
from core.sto_manager import sync_sto_assignments
from core.utils import normalize_key, parse_date_dmy, safe_int
import hashlib

def compile_fptk(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int, 
                 file_name: str, file_data: bytes, is_sto: bool = False):
    """Compile FPTK from uploaded Excel file"""
    
    # Hash file for audit
    file_hash = hashlib.sha256(file_data).hexdigest()
    
    # Strict validation
    validated_rows, errors = validate_fptk_file(df, db, user_id, is_sto)
    
    if errors:
        # Log failure
        log = UploadLog(
            cycle_id=cycle_id,
            user_id=user_id,
            file_name=file_name,
            file_size_bytes=len(file_data),
            file_hash=file_hash,
            status="FAILED",
            record_count=0,
            error_details="\n".join([f"Row {e.row} - {e.field}: {e.message}" for e in errors])
        )
        db.add(log)
        db.commit()
        return {
            "success": False,
            "errors": errors,
            "log": log
        }
    
    # Process each row
    imported = 0
    updated = 0
    skipped = 0
    
    # Get existing Kode Unik ownership map
    existing_codes = {}
    for fptk in db.query(FPTK).filter(FPTK.source_user_id == user_id).all():
        existing_codes[fptk.kode_unik] = fptk
    
    for row in validated_rows:
        kode_unik = row['kode_unik']
        posisi = row['posisi']
        fptk_date_real = row['fptk_date_real']
        
        # Check if Kode Unik exists AND is owned by another user
        existing = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
        if existing and existing.source_user_id != user_id:
            # Conflict: Kode Unik owned by another user
            skipped += 1
            continue
        
        # Check Kode Unik conflict: same Kode Unik but different FPTK Date Real
        if existing and existing.fptk_date_real != fptk_date_real:
            skipped += 1
            continue
        
        # Determine SLA
        level_num = row['level_number']
        if level_num <= 3:
            sla_days = 30
        elif level_num == 4:
            sla_days = 45
        elif level_num >= 5:
            sla_days = 60
        else:
            sla_days = 30
        
        # Calculate derived values
        deadline_sla = fptk_date_real + timedelta(days=sla_days) if fptk_date_real else None
        week_num = fptk_date_real.isocalendar()[1] if fptk_date_real else None
        month_name = fptk_date_real.strftime("%B") if fptk_date_real else None
        kode_bu = row.get('kode_pic', '')[:4] if row.get('kode_pic') else ''
        
        if existing:
            # Update existing
            existing.kode_pic = row.get('kode_pic')
            existing.fptk_date_real = fptk_date_real
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
            existing.status = row.get('status')
            existing.offering_date = row.get('offering_date')
            existing.fptk_cancel_date = row.get('fptk_cancel_date')
            existing.jumlah_sla = sla_days
            existing.deadline_sla = deadline_sla
            existing.week_fptk_date = week_num
            existing.month_fptk_date = month_name
            existing.kode_bu = kode_bu
            existing.last_updated_at = datetime.now()
            existing.last_compile_action = "UPDATE"
            existing.is_sto = is_sto
            updated += 1
        else:
            # Insert new
            new_fptk = FPTK(
                kode_unik=kode_unik,
                posisi=posisi,
                kode_pic=row.get('kode_pic'),
                fptk_date_real=fptk_date_real,
                fptk_date_kode=fptk_date_real,
                kode_angka=row.get('kode_pic', '')[:4] + str(safe_int(row.get('vacancy', 1))),
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
                status=row.get('status'),
                offering_date=row.get('offering_date'),
                fptk_cancel_date=row.get('fptk_cancel_date'),
                jumlah_sla=sla_days,
                deadline_sla=deadline_sla,
                week_fptk_date=week_num,
                month_fptk_date=month_name,
                kode_bu=kode_bu,
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
    
    # If STO, run STO sync after normal compile
    if is_sto:
        sync_sto_assignments(db, user_id, cycle_id, file_name, file_hash)
    
    # Log success
    log = UploadLog(
        cycle_id=cycle_id,
        user_id=user_id,
        file_name=file_name,
        file_size_bytes=len(file_data),
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
        "log": log
    }

def compile_db_sourcing(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                        file_name: str, file_hash: str, kode_unik_mapping: dict):
    """Compile DB Sourcing from uploaded Excel file"""
    
    valid_rows, errors = validate_db_sourcing_rows(df)
    
    if errors:
        return {"success": False, "errors": errors}
    
    imported = 0
    for row in valid_rows:
        kode_unik = normalize_key(row.get('Kode Unik (copy value dari FPTK)', ''))
        if not kode_unik:
            continue
        # Link to FPTK
        fptk = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
        if not fptk:
            continue
        
        sourcing = DBSourcing(
            kode_unik=kode_unik,
            posisi=row.get('Posisi'),
            nama=row.get('Nama'),
            sourcing_date=row.get('sourcing_date'),
            # ... map all columns from Excel
            source_user_id=user_id,
            source_cycle_id=cycle_id,
            source_file=file_name,
            source_file_hash=file_hash
        )
        db.add(sourcing)
        imported += 1
    
    db.commit()
    return {"success": True, "imported": imported}