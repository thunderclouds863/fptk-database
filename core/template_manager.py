# core/template_manager.py
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from core.models import UploadTemplate
from core.r2_storage import get_r2


# Content type untuk file Excel
EXCEL_CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "xls": "application/vnd.ms-excel",
}


def _guess_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXCEL_CONTENT_TYPES.get(ext, "application/octet-stream")


def save_template(db: Session, template_file, user_id: int, template_type: str = "FPTK"):
    """
    Save template baru. Otomatis:
    - Upload file ke R2
    - Set template lama dengan type yang sama jadi is_active = False
    - Set template baru is_active = True
    - Version auto increment dari template terakhir dengan type yang sama
    """
    try:
        file_bytes = template_file.getvalue()
        file_name = template_file.name
        content_type = _guess_content_type(file_name)

        # Upload ke R2
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"
        r2_key = f"templates/{template_type}/{uuid.uuid4().hex}.{ext}"

        r2 = get_r2()
        r2.upload_bytes(
            file_bytes=file_bytes,
            key=r2_key,
            content_type=content_type,
        )

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
            file_key=r2_key,
            file_type=content_type,
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
        # Kalau upload R2 berhasil tapi DB gagal, hapus file dari R2
        if 'r2_key' in locals():
            try:
                get_r2().delete(r2_key)
            except Exception:
                pass
        raise e


def get_active_template(db: Session, template_type: str = "FPTK"):
    """Ambil template aktif dengan type tertentu"""
    return db.query(UploadTemplate).filter(
        UploadTemplate.template_type == template_type,
        UploadTemplate.is_active == True
    ).order_by(UploadTemplate.version.desc()).first()


def get_template_bytes(template) -> bytes:
    """Download template dari R2, kembalikan bytes"""
    if not template or not template.file_key:
        return b""
    try:
        r2 = get_r2()
        return r2.download_bytes(template.file_key)
    except Exception:
        return b""


def get_template_presigned_url(template, expires_in: int = 3600) -> str:
    """Dapatkan URL download sementara untuk template"""
    if not template or not template.file_key:
        return ""
    try:
        r2 = get_r2()
        return r2.get_presigned_url(template.file_key, expires_in=expires_in)
    except Exception:
        return ""


def delete_template(db: Session, template_id: int) -> bool:
    """Hapus template dari DB dan R2"""
    template = db.query(UploadTemplate).filter(UploadTemplate.id == template_id).first()
    if not template:
        return False

    try:
        r2_key = template.file_key

        db.delete(template)
        db.commit()

        # Hapus dari R2 setelah DB commit berhasil
        if r2_key:
            try:
                get_r2().delete(r2_key)
            except Exception:
                pass  # File mungkin sudah tidak ada di R2, tidak masalah

        return True
    except Exception as e:
        db.rollback()
        raise e


def get_template_history(db: Session, template_type: str = "FPTK", limit: int = 10):
    """Ambil history template dengan type tertentu"""
    return db.query(UploadTemplate).filter(
        UploadTemplate.template_type == template_type
    ).order_by(UploadTemplate.version.desc()).limit(limit).all()