# core/template_manager.py
import base64
from datetime import datetime
from sqlalchemy.orm import Session
from core.models import UploadTemplate


def save_template(db: Session, template_file, user_id: int, template_type: str = "FPTK"):
    """
    Save template baru. Otomatis:
    - Set template lama dengan type yang sama jadi is_active = False
    - Set template baru is_active = True
    - Version auto increment dari template terakhir dengan type yang sama
    """
    try:
        file_bytes = template_file.getvalue()
        file_b64 = base64.b64encode(file_bytes).decode('utf-8')
        file_name = template_file.name

        # Cari template terakhir dengan type yang sama
        last_template = db.query(UploadTemplate).filter(
            UploadTemplate.template_type == template_type
        ).order_by(UploadTemplate.version.desc()).first()

        new_version = (last_template.version + 1) if last_template else 1

        # Non-aktifkan semua template lama dengan type yang sama
        db.query(UploadTemplate).filter(
            UploadTemplate.template_type == template_type,
            UploadTemplate.is_active == True
        ).update({"is_active": False}, synchronize_session=False)

        # Insert template baru
        new_template = UploadTemplate(
            file_name=file_name,
            file_data=file_b64,
            uploaded_by=user_id,
            version=new_version,
            is_active=True,
            template_type=template_type,
            created_at=datetime.now()
        )
        db.add(new_template)
        db.commit()
        db.refresh(new_template)

        return new_template

    except Exception as e:
        db.rollback()
        raise e


def get_active_template(db: Session, template_type: str = "FPTK"):
    """Ambil template aktif dengan type tertentu"""
    return db.query(UploadTemplate).filter(
        UploadTemplate.template_type == template_type,
        UploadTemplate.is_active == True
    ).order_by(UploadTemplate.version.desc()).first()


def get_template_bytes(template):
    """Decode base64 template jadi bytes"""
    if not template or not template.file_data:
        return b""
    try:
        return base64.b64decode(template.file_data)
    except Exception:
        return b""


def get_template_history(db: Session, template_type: str = "FPTK", limit: int = 10):
    """Ambil history template dengan type tertentu"""
    return db.query(UploadTemplate).filter(
        UploadTemplate.template_type == template_type
    ).order_by(UploadTemplate.version.desc()).limit(limit).all()
