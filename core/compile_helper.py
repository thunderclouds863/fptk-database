import time
import hashlib
import pandas as pd

from core.compiler import (
    compile_fptk,
    compile_db_sourcing,
    compile_db_kode_posisi
)

from core.auth import sanitize_filename


def compile_with_progress(
    file,
    df,
    _db,
    user,
    cycle,
    is_sto,
    progress_placeholder,
    status_placeholder
):

    status_placeholder.info("📋 Step 1/5: Validasi struktur file...")
    progress_placeholder.progress(10)

    time.sleep(0.3)

    file_bytes = file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    if _db.is_active:
        _db.rollback()

    result = compile_fptk(
        _db,
        df,
        user.id,
        cycle.id,
        sanitize_filename(file.name),
        file_bytes,
        is_sto
    )

    return result["success"], result
