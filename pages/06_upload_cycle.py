import streamlit as st
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import UploadCycle, UploadStatus, User
from core.upload_cycle import create_upload_cycle, get_cycle_progress, close_cycle
from core.auth import (
    get_current_user, is_admin, is_it, is_editor,
    invalidate_filter_cache
)
from core.utils import get_filter_options_from_db
import pandas as pd


# ============================================================
# HELPER: REFRESH FILTER CACHE
# ============================================================

def refresh_filter_cache():
    """Clear cache filter options supaya data cycle baru langsung muncul."""
    try:
        get_filter_options_from_db.clear()
    except Exception:
        pass
    try:
        invalidate_filter_cache()
    except Exception:
        pass


def show_upload_cycle():
    st.title("🔄 Upload Cycle Management")
    st.markdown("Kelola siklus upload untuk setiap periode.")

    db = next(get_db())

    # ============================================================
    # MODE VIEW-ONLY (IT)
    # ============================================================
    if is_it(db):
        st.info("🔍 Mode View-Only (IT)")
        cycles = db.query(UploadCycle).order_by(UploadCycle.created_at.desc()).all()
        if cycles:
            data = [{
                "ID": c.id,
                "Nama Cycle": c.cycle_name,
                "Dibuat": c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else "-",
                "Status": "Aktif" if not c.ended_at else "Selesai"
            } for c in cycles]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("Belum ada upload cycle.")
        return

    # ============================================================
    # CHECK ACCESS - ADMIN ONLY
    # ============================================================
    if not is_admin(db):
        st.error("Hanya Admin yang bisa mengelola Upload Cycle.")
        return

    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    # ============================================================
    # LIST CYCLES
    # ============================================================
    st.subheader("📋 Riwayat Upload Cycle")
    cycles = db.query(UploadCycle).order_by(UploadCycle.created_at.desc()).all()

    if cycles:
        data = []
        for cycle in cycles:
            progress = get_cycle_progress(db, cycle.id)
            data.append({
                "ID": cycle.id,
                "Nama Cycle": cycle.cycle_name,
                "Dibuat": cycle.created_at.strftime("%d/%m/%Y %H:%M"),
                "Status": "Aktif" if not cycle.ended_at else "Selesai",
                "Progress": f"{progress['done']}/{progress['total']} ({progress['progress_pct']:.0f}%)"
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada upload cycle.")

    # ============================================================
    # CREATE NEW CYCLE
    # ============================================================
    st.markdown("---")
    st.subheader("➕ Buat Upload Cycle Baru")

    with st.form("create_cycle"):
        cycle_name = st.text_input("Nama Cycle", placeholder="Contoh: Periode Januari 2026")
        submitted = st.form_submit_button("Buat Cycle")

        if submitted and cycle_name:
            new_cycle = create_upload_cycle(db, cycle_name, user.id)

            # ============================================================
            # REFRESH FILTER CACHE
            # ============================================================
            refresh_filter_cache()
            st.cache_data.clear()

            st.success(f"✅ Cycle '{cycle_name}' berhasil dibuat!")
            st.rerun()
        elif submitted and not cycle_name:
            st.error("Nama Cycle wajib diisi")

    # ============================================================
    # CURRENT CYCLE PROGRESS DETAIL
    # ============================================================
    st.markdown("---")
    st.subheader("📊 Progress Cycle Aktif")

    active_cycle = db.query(UploadCycle).filter(
        UploadCycle.ended_at.is_(None)
    ).order_by(UploadCycle.created_at.desc()).first()

    if active_cycle:
        statuses = db.query(UploadStatus).filter(
            UploadStatus.cycle_id == active_cycle.id
        ).all()

        if statuses:
            progress_data = []
            for s in statuses:
                user_obj = db.query(User).filter(User.id == s.user_id).first()
                progress_data.append({
                    "User": user_obj.display_name if user_obj else s.user_id,
                    "PIC": user_obj.pic_recruiter if user_obj else "-",
                    "Status": s.status,
                    "First Compile": s.first_compile_at.strftime("%d/%m/%Y") if s.first_compile_at else "-",
                    "Done At": s.done_at.strftime("%d/%m/%Y %H:%M") if s.done_at else "-"
                })
            df_progress = pd.DataFrame(progress_data)

            # Summary
            total = len(df_progress)
            done = len(df_progress[df_progress['Status'] == 'Done'])
            uploading = len(df_progress[df_progress['Status'] == 'Sedang Upload'])
            belum = len(df_progress[df_progress['Status'] == 'Belum Mulai'])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total User", total)
            col2.metric("Done", done, delta=f"{done/total*100:.0f}%" if total else "0%")
            col3.metric("Sedang Upload", uploading)
            col4.metric("Belum Mulai", belum)

            st.dataframe(df_progress, use_container_width=True)

            # ============================================================
            # CLOSE CYCLE
            # ============================================================
            if done == total:
                if st.button("🔒 Tutup Cycle", type="primary"):
                    close_cycle(db, active_cycle.id)

                    # Refresh filter cache
                    refresh_filter_cache()
                    st.cache_data.clear()

                    st.success("Cycle berhasil ditutup!")
                    st.rerun()
        else:
            st.info("Belum ada user yang terdaftar di cycle ini.")
    else:
        st.info("Tidak ada cycle aktif.")
