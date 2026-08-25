import streamlit as st
import pandas as pd
import time
from core.database import get_db
from core.auth import get_current_user, hash_file, sanitize_filename
from core.upload_cycle import get_current_cycle, mark_user_uploading, mark_user_done
from core.models import UploadStatus
from core.validator import validate_fptk_file
from core.compiler import compile_fptk

def show_upload_compile():
    st.title("📤 Upload & Compile")
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return

    cycle = get_current_cycle(db)
    if not cycle:
        st.error("Belum ada Upload Cycle aktif. Hubungi Admin.")
        return
    st.info(f"📋 Upload Cycle: {cycle.cycle_name}")

    # Cek status user
    status_record = db.query(UploadStatus).filter(
        UploadStatus.user_id == user.id,
        UploadStatus.cycle_id == cycle.id
    ).first()
    current_status = status_record.status if status_record else "Belum Mulai"
    
    # Tampilkan status dengan warna
    if current_status == "Done":
        st.success(f"✅ Status Anda: **{current_status}** (Anda sudah menyelesaikan upload untuk cycle ini)")
    elif current_status == "Sedang Upload":
        st.info(f"⏳ Status Anda: **{current_status}**")
    else:
        st.warning(f"📌 Status Anda: **{current_status}**")

    st.markdown("---")
    st.subheader("📁 Upload File Excel")
    
    # Info penting
    st.caption("💡 **Catatan:** Anda bisa upload beberapa file. Jika sudah selesai, klik tombol **'Saya Selesai Upload'** di bawah. Status akan berubah menjadi **Done**.")
    
    uploaded_files = st.file_uploader(
        "Pilih file Excel (.xlsx, .xlsm)",
        type=["xlsx", "xlsm"],
        accept_multiple_files=True
    )
    
    is_sto = st.checkbox("☑️ File ini adalah file STO (Tulang Punggung)")

    # Container untuk progress
    if st.button("🚀 Compile", type="primary"):
        if not uploaded_files:
            st.warning("Pilih file dulu!")
        else:
            total_files = len(uploaded_files)
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_imported = 0
            total_updated = 0
            total_errors = 0
            
            for idx, file in enumerate(uploaded_files):
                # Update progress
                progress = (idx + 1) / total_files
                progress_bar.progress(progress)
                status_text.info(f"📄 Memproses {idx+1} dari {total_files}: {file.name}")
                
                try:
                    # Baca Excel
                    df = pd.read_excel(file, sheet_name="FPTK", header=None)
                    
                    # Cari baris header
                    header_row = None
                    for i, row in df.iterrows():
                        row_text = " ".join([str(x) for x in row.values if pd.notna(x)])
                        if "Kode Unik" in row_text and "Posisi" in row_text:
                            header_row = i
                            break
                    
                    if header_row is None:
                        st.error(f"❌ {file.name}: Header tidak ditemukan")
                        total_errors += 1
                        continue
                    
                    # Set header
                    df.columns = df.iloc[header_row].astype(str).str.strip()
                    df = df.iloc[header_row + 1:].reset_index(drop=True)
                    
                    # Validasi
                    validated_rows, errors = validate_fptk_file(df, db, user.id, is_sto)
                    
                    if errors:
                        total_errors += 1
                        error_summary = "\n".join([
                            f"Row {e.get('row', 0)} - {e.get('field', 'Unknown')}: {e.get('message', '')}"
                            for e in errors[:10]
                        ])
                        if len(errors) > 10:
                            error_summary += f"\n... dan {len(errors)-10} error lainnya"
                        st.error(f"❌ {file.name}: {len(errors)} error (file ditolak)")
                        with st.expander(f"Detail error {file.name}"):
                            st.code(error_summary)
                        continue
                    
                    # Compile
                    file_bytes = file.read()
                    file_hash = hash_file(file_bytes)
                    file_name = sanitize_filename(file.name)
                    
                    result = compile_fptk(
                        db, validated_rows, user.id, cycle.id,
                        file_name, file_bytes, is_sto
                    )
                    
                    if result.get("success", False):
                        imported = result.get("imported", 0)
                        updated = result.get("updated", 0)
                        total_imported += imported
                        total_updated += updated
                        st.success(f"✅ {file.name}: Imported {imported}, Updated {updated}")
                        
                        # Update status user ke "Sedang Upload"
                        mark_user_uploading(db, user.id, cycle.id)
                    else:
                        total_errors += 1
                        st.error(f"❌ {file.name}: Compile gagal")
                        
                except Exception as e:
                    total_errors += 1
                    st.error(f"❌ {file.name}: Error - {str(e)}")
            
            # Selesai
            progress_bar.progress(1.0)
            status_text.success(f"✅ Selesai! Imported: {total_imported}, Updated: {total_updated}, Errors: {total_errors}")
            
            # Jika berhasil, tampilkan tombol Done
            if total_errors == 0 and total_imported + total_updated > 0:
                st.markdown("---")
                st.subheader("✅ Selesai Upload?")
                st.caption("Klik tombol di bawah jika Anda sudah mengupload **SEMUA** file yang diperlukan untuk cycle ini.")
                st.caption("⚠️ Status akan berubah menjadi **Done**. Anda tetap bisa upload lagi nanti, tapi status akan otomatis kembali ke **Sedang Upload**.")
                
                if st.button("📌 Saya Selesai Upload", type="primary"):
                    mark_user_done(db, user.id, cycle.id)
                    st.success("✅ Status Anda berhasil diupdate menjadi **Done**!")
                    st.balloons()
                    st.rerun()