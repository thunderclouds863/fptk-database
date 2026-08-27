import base64

from core.models import UploadTemplate


def save_template(db, uploaded_file, user_id):
    """
    Simpan template Excel baru.
    Template lama otomatis dinonaktifkan.
    """

    file_bytes = uploaded_file.read()

    encoded_file = base64.b64encode(
        file_bytes
    ).decode("utf-8")


    # Nonaktifkan template sebelumnya
    db.query(
        UploadTemplate
    ).filter(
        UploadTemplate.is_active == True
    ).update(
        {
            UploadTemplate.is_active: False
        }
    )


    # Ambil versi terakhir
    last_template = (
        db.query(UploadTemplate)
        .order_by(
            UploadTemplate.version.desc()
        )
        .first()
    )


    new_version = 1

    if last_template:
        new_version = last_template.version + 1


    template = UploadTemplate(
        file_name=uploaded_file.name,
        file_data=encoded_file,
        uploaded_by=user_id,
        version=new_version,
        is_active=True
    )


    db.add(template)
    db.commit()
    db.refresh(template)

    return template



def get_active_template(db):
    """
    Mengambil template yang sedang aktif.
    """

    return (
        db.query(UploadTemplate)
        .filter(
            UploadTemplate.is_active == True
        )
        .order_by(
            UploadTemplate.version.desc()
        )
        .first()
    )



def get_template_bytes(template):
    """
    Convert Base64 kembali menjadi file Excel.
    """

    if not template:
        return None

    return base64.b64decode(
        template.file_data
    )



def delete_template(db, template_id):
    """
    Hapus template.
    """

    template = (
        db.query(UploadTemplate)
        .filter(
            UploadTemplate.id == template_id
        )
        .first()
    )

    if template:

        db.delete(template)
        db.commit()

        return True

    return False
