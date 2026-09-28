# scripts/migrate_to_r2.py
"""
Migrasi file dari kolom file_data (base64/BYTEA) di Supabase ke Cloudflare R2.
Jalankan dari root repo: python -m scripts.migrate_to_r2
"""
import base64
import mimetypes
from core.database import SessionLocal
from core import models
from scripts.r2_client_local import s3, R2_BUCKET


def guess_type(filename: str) -> str:
    """Tebak content-type dari ekstensi file."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return mimetypes.types_map.get(f".{ext}", "application/octet-stream")


def build_key(prefix: str, identifier: str, filename: str) -> str:
    """Bikin path unik di R2, mis: evidences/FTK-001/bukti.pdf"""
    safe = (filename or "file").replace(" ", "_")
    return f"{prefix}/{identifier}/{safe}"


def to_bytes(raw) -> bytes:
    """
    Konversi file_data dari database ke bytes.
    Mendukung:
    - bytes (kolom BYTEA di Postgres)
    - str base64 (kolom TEXT)
    - str dengan prefix data URI (data:image/png;base64,...)
    """
    if raw is None:
        raise ValueError("file_data kosong (NULL)")

    # Kasus 1: BYTEA -> sudah bytes
    if isinstance(raw, bytes):
        return raw

    # Kasus 2: TEXT base64 (mungkin dengan prefix data URI)
    if isinstance(raw, str):
        if raw.startswith("data:") and "," in raw:
            raw = raw.split(",", 1)[1]
        return base64.b64decode(raw)

    # Kasus 3: memoryview atau tipe lain -> coba konversi
    return bytes(raw)


def migrate_table(
    db,
    model,
    prefix: str,
    id_field: str,
    type_field: str = None,
    name_field: str = "file_name",
):
    """
    Migrasi satu tabel secara generik.
    - model: SQLAlchemy model class
    - prefix: folder di R2 (evidences/templates/cv)
    - id_field: nama kolom untuk identifikasi (kode_unik/template_type)
    - type_field: nama kolom untuk MIME type (opsional)
    - name_field: nama kolom untuk nama file
    """
    rows = db.query(model).filter(model.file_data.isnot(None)).all()
    print(f"📦 {model.__tablename__}: {len(rows)} file menunggu migrasi")

    success, fail = 0, 0
    for row in rows:
        try:
            identifier = str(getattr(row, id_field, None) or row.id)
            filename = getattr(row, name_field, None) or f"file_{row.id}"
            key = build_key(prefix, identifier, filename)

            content_type = (
                getattr(row, type_field, None) if type_field else guess_type(filename)
            )
            if not content_type:
                content_type = guess_type(filename)

            # Konversi file_data -> bytes
            file_bytes = to_bytes(row.file_data)

            # Upload ke R2
            s3.put_object(
                Bucket=R2_BUCKET,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )

            # Update record
            row.file_key = key
            if hasattr(row, "file_size") and not row.file_size:
                row.file_size = len(file_bytes)
            if type_field and not getattr(row, type_field, None):
                setattr(row, type_field, content_type)

            # Coba kosongkan file_data; kalau NOT NULL constraint, skip
            try:
                row.file_data = None
                db.commit()
            except Exception as commit_err:
                db.rollback()
                # Update hanya file_key, biarkan file_data tetap ada
                db.query(model).filter(model.id == row.id).update(
                    {model.file_key: key}
                )
                db.commit()
                print(f"  ⚠️  {row.id}: file_key di-set, tapi file_data tidak bisa di-NULL (constraint). Jalankan ALTER TABLE ... DROP NOT NULL.")

            success += 1
            print(f"  ✅ {row.id} -> {key}")

        except Exception as e:
            db.rollback()
            print(f"  ❌ {row.id}: {e}")
            fail += 1

    print(f"  Selesai: ✅ {success} berhasil, ❌ {fail} gagal\n")
    return success, fail


def main():
    db = SessionLocal()
    try:
        total_ok, total_fail = 0, 0

        # 1. Evidence
        ok, fail = migrate_table(
            db,
            models.Evidence,
            prefix="evidences",
            id_field="kode_unik",
            name_field="file_name",
        )
        total_ok += ok
        total_fail += fail

        # 2. UploadTemplate
        ok, fail = migrate_table(
            db,
            models.UploadTemplate,
            prefix="templates",
            id_field="template_type",
            name_field="file_name",
        )
        total_ok += ok
        total_fail += fail

        # 3. CVAttachment
        ok, fail = migrate_table(
            db,
            models.CVAttachment,
            prefix="cv",
            id_field="kode_unik",
            type_field="file_type",
            name_field="file_name",
        )
        total_ok += ok
        total_fail += fail

        print(f"{'=' * 50}")
        print(f"Total: ✅ {total_ok} berhasil, ❌ {total_fail} gagal")

    finally:
        db.close()


if __name__ == "__main__":
    main()