import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from core.models import FPTK, DBSourcing, DBKodePosisi, MasterDropdown, UploadLog, Evidence, Blacklist
from core.validator import validate_fptk_file, validate_db_sourcing_file
from core.sto_manager import sync_sto_assignments
from core.utils import normalize_key, parse_date_dmy, safe_int
import hashlib

def compile_fptk(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int, 
                 file_name: str, file_data: bytes, is_sto: bool = False):
    """Compile FPTK from uploaded Excel file"""
    
    # Hash file untuk audit
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
            error_details="\n".join([f"Row {e.row} - {e.field}: {e.message}" for e in errors if e.get('row', 0) > 0])
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
                        file_name: str, file_data: bytes, kode_unik_mapping: dict = None):
    """Compile DB Sourcing from uploaded Excel file"""
    
    # HASH FILE (ini yang kurang)
    file_hash = hashlib.sha256(file_data).hexdigest()
    
    valid_rows, errors = validate_db_sourcing_file(df, db, user_id)
    
    if errors:
        log = UploadLog(
            cycle_id=cycle_id,
            user_id=user_id,
            file_name=file_name,
            file_size_bytes=len(file_data),
            file_hash=file_hash,
            status="FAILED",
            record_count=0,
            error_details="\n".join([f"Row {e.row} - {e.field}: {e.message}" for e in errors if e.get('row', 0) > 0])
        )
        db.add(log)
        db.commit()
        return {"success": False, "errors": errors, "log": log}
    
    imported = 0
    updated = 0
    skipped = 0
    
    # Get existing records for update (by kode_unik + nama)
    existing_records = {}
    for record in db.query(DBSourcing).all():
        key = f"{record.kode_unik}|{record.nama}"
        existing_records[key] = record
    
    for _, row in valid_rows.iterrows():
        kode_unik = row.get('kode_unik', '')
        nama = row.get('nama', '')
        
        if not kode_unik or not nama:
            skipped += 1
            continue
        
        # Cari existing
        key = f"{kode_unik}|{nama}"
        
        if key in existing_records:
            # Update existing - hanya update field yang kosong
            existing = existing_records[key]
            updated += 1
            
            # Update hanya jika field target kosong
            if not existing.posisi and row.get('posisi'):
                existing.posisi = row.get('posisi')
            if not existing.rekruter and row.get('rekruter'):
                existing.rekruter = row.get('rekruter')
            if not existing.sumber_sourcing and row.get('sumber_sourcing'):
                existing.sumber_sourcing = row.get('sumber_sourcing')
            if not existing.nomor_hp and row.get('nomor_hp'):
                existing.nomor_hp = row.get('nomor_hp')
            if not existing.email and row.get('email'):
                existing.email = row.get('email')
            if not existing.domisili and row.get('domisili'):
                existing.domisili = row.get('domisili')
            if not existing.jenjang_pendidikan and row.get('jenjang_pendidikan'):
                existing.jenjang_pendidikan = row.get('jenjang_pendidikan')
            if not existing.jurusan and row.get('jurusan'):
                existing.jurusan = row.get('jurusan')
            if not existing.tahun_lulus and row.get('tahun_lulus'):
                existing.tahun_lulus = row.get('tahun_lulus')
            if not existing.ipk and row.get('ipk'):
                existing.ipk = row.get('ipk')
            if not existing.university_tier and row.get('university_tier'):
                existing.university_tier = row.get('university_tier')
            if not existing.ipk_tier and row.get('ipk_tier'):
                existing.ipk_tier = row.get('ipk_tier')
            if not existing.nama_universitas_top10 and row.get('nama_universitas_top10'):
                existing.nama_universitas_top10 = row.get('nama_universitas_top10')
            if not existing.nama_universitas_lainnya and row.get('nama_universitas_lainnya'):
                existing.nama_universitas_lainnya = row.get('nama_universitas_lainnya')
            if not existing.last_position and row.get('last_position'):
                existing.last_position = row.get('last_position')
            if not existing.last_company and row.get('last_company'):
                existing.last_company = row.get('last_company')
            if not existing.last_tenure and row.get('last_tenure'):
                existing.last_tenure = row.get('last_tenure')
            if not existing.total_tenure and row.get('total_tenure'):
                existing.total_tenure = row.get('total_tenure')
            if not existing.pernah_di_fmcg and row.get('pernah_di_fmcg'):
                existing.pernah_di_fmcg = row.get('pernah_di_fmcg')
            if not existing.sourcing_hr and row.get('sourcing_hr'):
                existing.sourcing_hr = row.get('sourcing_hr')
            if not existing.shortlist_cv and row.get('shortlist_cv'):
                existing.shortlist_cv = row.get('shortlist_cv')
            if not existing.psikotes and row.get('psikotes'):
                existing.psikotes = row.get('psikotes')
            if not existing.hr_interview and row.get('hr_interview'):
                existing.hr_interview = row.get('hr_interview')
            if not existing.user_interview and row.get('user_interview'):
                existing.user_interview = row.get('user_interview')
            if not existing.offering and row.get('offering'):
                existing.offering = row.get('offering')
            if not existing.day1 and row.get('day1'):
                existing.day1 = row.get('day1')
            
            existing.last_updated_at = datetime.now()
            existing.last_compile_action = "UPDATE"
            
        else:
            # Insert new
            last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
            next_no = (last_no.no + 1) if last_no and last_no.no else 1
            
            new_sourcing = DBSourcing(
                no=next_no,
                kode_unik=kode_unik,
                nama=nama,
                posisi=row.get('posisi'),
                model_rekrutmen=row.get('model_rekrutmen'),
                rekruter=row.get('rekruter'),
                sumber_sourcing=row.get('sumber_sourcing'),
                nomor_hp=row.get('nomor_hp'),
                email=row.get('email'),
                domisili=row.get('domisili'),
                jenjang_pendidikan=row.get('jenjang_pendidikan'),
                jurusan=row.get('jurusan'),
                tahun_lulus=row.get('tahun_lulus'),
                ipk=row.get('ipk'),
                university_tier=row.get('university_tier'),
                ipk_tier=row.get('ipk_tier'),
                nama_universitas_top10=row.get('nama_universitas_top10'),
                nama_universitas_lainnya=row.get('nama_universitas_lainnya'),
                last_position=row.get('last_position'),
                last_company=row.get('last_company'),
                last_tenure=row.get('last_tenure'),
                total_tenure=row.get('total_tenure'),
                pernah_di_fmcg=row.get('pernah_di_fmcg'),
                sourcing_hr=row.get('sourcing_hr'),
                shortlist_cv=row.get('shortlist_cv'),
                psikotes=row.get('psikotes'),
                hr_interview=row.get('hr_interview'),
                user_interview=row.get('user_interview'),
                offering=row.get('offering'),
                day1=row.get('day1'),
                sourcing_date=row.get('sourcing_date') or datetime.now().date(),
                source_user_id=user_id,
                source_cycle_id=cycle_id,
                source_file=file_name,
                source_file_hash=file_hash,
                created_at=datetime.now(),
                last_compile_action="INSERT"
            )
            db.add(new_sourcing)
            imported += 1
    
    db.commit()
    
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
    
    return {"success": True, "imported": imported, "updated": updated, "skipped": skipped, "log": log}
