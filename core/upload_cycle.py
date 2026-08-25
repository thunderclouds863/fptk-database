from sqlalchemy.orm import Session
from core.models import UploadCycle, UploadStatus, User
from datetime import datetime

def create_upload_cycle(db: Session, cycle_name: str, created_by: int):
    """Create new upload cycle"""
    cycle = UploadCycle(
        cycle_name=cycle_name,
        created_by=created_by
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    
    # Initialize status for all users
    users = db.query(User).filter(User.role == "user").all()
    for user in users:
        status = UploadStatus(
            cycle_id=cycle.id,
            user_id=user.id,
            status="Belum Mulai"
        )
        db.add(status)
    db.commit()
    return cycle

def mark_user_done(db: Session, user_id: int, cycle_id: int):
    """User clicks Done Uploading"""
    status = db.query(UploadStatus).filter(
        UploadStatus.user_id == user_id,
        UploadStatus.cycle_id == cycle_id
    ).first()
    if status:
        status.status = "Done"
        status.done_at = datetime.now()
        db.commit()
    return status

def mark_user_uploading(db: Session, user_id: int, cycle_id: int):
    """User uploads successfully"""
    status = db.query(UploadStatus).filter(
        UploadStatus.user_id == user_id,
        UploadStatus.cycle_id == cycle_id
    ).first()
    if status:
        if status.status == "Done":
            # User was done, but uploaded again -> reopen
            status.status = "Sedang Upload"
        else:
            status.status = "Sedang Upload"
            if not status.first_compile_at:
                status.first_compile_at = datetime.now()
        db.commit()
    return status

def get_cycle_progress(db: Session, cycle_id: int):
    """Get progress for all users in a cycle"""
    statuses = db.query(UploadStatus).filter(
        UploadStatus.cycle_id == cycle_id
    ).all()
    total = len(statuses)
    done = len([s for s in statuses if s.status == "Done"])
    uploading = len([s for s in statuses if s.status == "Sedang Upload"])
    belum = len([s for s in statuses if s.status == "Belum Mulai"])
    return {
        "total": total,
        "done": done,
        "uploading": uploading,
        "belum": belum,
        "progress_pct": (done / total * 100) if total > 0 else 0
    }

def get_current_cycle(db: Session):
    """Get current active cycle"""
    return db.query(UploadCycle).filter(
        UploadCycle.ended_at.is_(None)
    ).order_by(UploadCycle.created_at.desc()).first()

def close_cycle(db: Session, cycle_id: int):
    """Close current cycle"""
    cycle = db.query(UploadCycle).filter(UploadCycle.id == cycle_id).first()
    if cycle:
        cycle.ended_at = datetime.now()
        db.commit()
    return cycle