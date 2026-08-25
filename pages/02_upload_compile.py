import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import UploadCycle, UploadLog, FPTK, DBSourcing, UploadStatus
from core.auth import get_current_user, hash_file, sanitize_filename, is_admin
from core.compiler import compile_fptk, compile_db_sourcing
from core.validator import validate_fptk_file
from core.upload_cycle import get_current_cycle, mark_user_uploading, mark_user_done
from core.sto_manager import sync_sto_assignments
from core.utils import normalize_key

def show_upload_compile():
    st.title("📤 Upload & Compile")
    st.markdown("Upload file Excel recruiter untuk di-compile ke database pusat.")
    
    db = next(get_db())
    user = get_current_user(db)  # <--- FIX: tambahkan 'db'
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # Get current upload cycle
    cycle = get_current_cycle(db)
    if not cycle:
        st.error("Belum ada Upload Cycle aktif. Hubungi Admin untuk membuat cycle baru.")
        return
    
    st.info(f"📋 Upload Cycle: **{cycle.cycle_name}**")
    
    # Check user status
    user_status = db.query(UploadStatus).filter(
        UploadStatus.user_id == user.id,
        UploadStatus.cycle_id == cycle.id
    ).first()
    status_text = user_status.status if user_status else "Belum Mulai"
    st.caption(f"Status Anda: **{status_text}**")
    
    # Upload section
    st.markdown("---")
    st.subheader("📁 Upload File Excel")
    
    uploaded_files = st.file_uploader(
        "Pilih file Excel (.xlsx, .xlsm)",
        type=["xlsx", "xlsm"],
        accept_multiple_files=True,
        key="upload_files"
    )
    
    # STO checkbox
    is_sto = st.checkbox("☑️ File ini adalah file STO (Tulang Punggung)", help="Centang jika file ini berisi data STO untuk sync V/X assignments.")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        compile_btn = st.button("🚀 Compile", type="primary", use_container_width=True)
    
    if compile_btn and uploaded_files:
        results = []
        total_imported = 0
        total_updated = 0
        total_errors = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, file in enumerate(uploaded_files):
            status_text.text(f"Memproses: {file.name} ({idx+1}/{len(uploaded_files)})")
            
            # Read Excel
            try:
                df = pd.read_excel(file, sheet_name="FPTK", header=None)
                # Find header row (look for Kode Unik, Posisi)
                header_row = None
                for i, row in df.iterrows():
                    row_text = " ".join([str(x) for x in row.values if pd.notna(x)])
                    if "Kode Unik" in row_text and "Posisi" in row_text:
                        header_row = i
                        break
                
                if header_row is None:
                    st.error(f"❌ {file.name}: Header tidak ditemukan (cari 'Kode Unik' dan 'Posisi')")
                    continue
                
                # Set header and skip rows before header
                df.columns = df.iloc[header_row].astype(str).str.strip()
                df = df.iloc[header_row + 1:].reset_index(drop=True)
                
                # Validate
                validated, errors = validate_fptk_file(df, db, user.id, is_sto)
                
                if errors:
                    total_errors += 1
                    error_summary = "\n".join([f"Row {e.row} - {e.field}: {e.message}" for e in errors[:10]])
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
                
                result = compile_fptk(db, df, user.id, cycle.id, file_name, file_bytes, is_sto)
                
                if result["success"]:
                    total_imported += result.get("imported", 0)
                    total_updated += result.get("updated", 0)
                    st.success(f"✅ {file.name}: Imported {result.get('imported', 0)}, Updated {result.get('updated', 0)}")
                    
                    # Update user status to "Sedang Upload"
                    mark_user_uploading(db, user.id, cycle.id)
                else:
                    total_errors += 1
                    st.error(f"❌ {file.name}: Compile gagal")
                
            except Exception as e:
                total_errors += 1
                st.error(f"❌ {file.name}: Error - {str(e)}")
            
            progress_bar.progress((idx + 1) / len(uploaded_files))
        
        status_text.text("Selesai!")
        st.success(f"✅ Compile selesai! Imported: {total_imported}, Updated: {total_updated}, Errors: {total_errors}")
        
        # If no errors, show Done button
        if total_errors == 0 and total_imported + total_updated > 0:
            st.markdown("---")
            st.subheader("✅ Upload Selesai")
            if st.button("📌 Saya Selesai Upload", type="primary"):
                mark_user_done(db, user.id, cycle.id)
                st.success("Status Anda telah diupdate menjadi **Done**!")
                st.rerun()
    
    # Show upload history
    st.markdown("---")
    st.subheader("📜 Riwayat Upload")
    logs = db.query(UploadLog).filter(
        UploadLog.user_id == user.id,
        UploadLog.cycle_id == cycle.id
    ).order_by(UploadLog.uploaded_at.desc()).limit(50).all()
    
    if logs:
        data = []
        for log in logs:
            data.append({
                "Tanggal": log.uploaded_at.strftime("%d/%m/%Y %H:%M"),
                "File": log.file_name,
                "Status": log.status,
                "Records": log.record_count or 0,
                "Error": log.error_details[:100] + "..." if log.error_details and len(log.error_details) > 100 else log.error_details
            })
        df_log = pd.DataFrame(data)
        st.dataframe(df_log, use_container_width=True, height=300)
    else:
        st.info("Belum ada riwayat upload.")
    
    # Correction report for failed files
    st.markdown("---")
    st.subheader("📋 Laporan Koreksi")
    failed_logs = db.query(UploadLog).filter(
        UploadLog.user_id == user.id,
        UploadLog.cycle_id == cycle.id,
        UploadLog.status == "FAILED"
    ).order_by(UploadLog.uploaded_at.desc()).limit(10).all()
    
    if failed_logs:
        for log in failed_logs:
            with st.expander(f"❌ {log.file_name} - {log.uploaded_at.strftime('%d/%m/%Y')}"):
                st.code(log.error_details or "Tidak ada detail error")
    else:
        st.info("Tidak ada file gagal.")