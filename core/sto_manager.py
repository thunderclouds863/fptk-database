import pandas as pd
from sqlalchemy.orm import Session
from core.models import FPTK
from core.utils import normalize_key, parse_date_dmy
from datetime import datetime

def sync_sto_assignments(db: Session, user_id: int, cycle_id: int, file_name: str, file_hash: str):
    """Sync STO V (YES) and X (NO) assignments"""
    
    # Get STO data from uploaded file (already in DB as FPTK with is_sto=True)
    sto_records = db.query(FPTK).filter(
        FPTK.is_sto == True,
        FPTK.source_user_id == user_id,
        FPTK.source_cycle_id == cycle_id
    ).all()
    
    if not sto_records:
        return
    
    # Process V assignments (FPTK Availability = Y)
    v_records = [r for r in sto_records if r.fptk_availability == 'Y']
    for sto in v_records:
        # Find matching FPTK by Posisi + Nama Kandidat (if exists)
        if sto.nama_kandidat:
            existing = db.query(FPTK).filter(
                FPTK.posisi == sto.posisi,
                FPTK.nama_kandidat == sto.nama_kandidat,
                FPTK.is_sto == False
            ).first()
            if existing:
                existing.filter_kategorisasi_fptk = "STO"
                existing.last_updated_at = datetime.now()
            else:
                # Insert new STO record
                new_fptk = FPTK(
                    kode_unik=sto.kode_unik,
                    posisi=sto.posisi,
                    nama_kandidat=sto.nama_kandidat,
                    filter_kategorisasi_fptk="STO",
                    fptk_availability="Y",
                    source_user_id=user_id,
                    source_cycle_id=cycle_id,
                    source_file=file_name,
                    source_file_hash=file_hash,
                    is_sto=False,
                    created_at=datetime.now()
                )
                db.add(new_fptk)
        else:
            # No Nama Kandidat -> try to match by Posisi only
            existing = db.query(FPTK).filter(
                FPTK.posisi == sto.posisi,
                FPTK.nama_kandidat.is_(None),
                FPTK.is_sto == False
            ).first()
            if existing:
                existing.filter_kategorisasi_fptk = "STO"
                existing.last_updated_at = datetime.now()
    
    # Process X assignments (FPTK Availability = N)
    x_records = [r for r in sto_records if r.fptk_availability == 'N']
    for sto in x_records:
        # Check if already exists
        existing = db.query(FPTK).filter(
            FPTK.posisi == sto.posisi,
            FPTK.nama_kandidat == sto.nama_kandidat,
            FPTK.is_sto == False
        ).first()
        
        if existing:
            existing.filter_kategorisasi_fptk = "STO"
            existing.last_updated_at = datetime.now()
        elif sto.nama_kandidat:
            # Insert new X record
            new_fptk = FPTK(
                kode_unik=sto.kode_unik,
                posisi=sto.posisi,
                nama_kandidat=sto.nama_kandidat,
                filter_kategorisasi_fptk="STO",
                fptk_availability="N",
                source_user_id=user_id,
                source_cycle_id=cycle_id,
                source_file=file_name,
                source_file_hash=file_hash,
                is_sto=False,
                created_at=datetime.now()
            )
            db.add(new_fptk)
    
    db.commit()