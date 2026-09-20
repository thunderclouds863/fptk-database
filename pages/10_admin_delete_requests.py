# pages/10_admin_delete_requests.py
import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import FPTKDeleteRequest, FPTK, SourcingDeleteRequest, DBSourcing, User
from core.auth import get_current_user, is_admin
from datetime import datetime
import time


def show_admin_delete_requests():
    st.title("📩 Request Hapus")
    st.markdown("Kelola request hapus FPTK & Sourcing dari PIC.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    if not is_admin(db):
        st.error("❌ Hanya Admin yang bisa mengakses halaman ini.")
        return

    fptk_pending = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.status == "PENDING"
    ).count()
    src_pending = db.query(SourcingDeleteRequest).filter(
        SourcingDeleteRequest.status == "PENDING"
    ).count()

    col1, col2 = st.columns(2)
    col1.metric("⏳ FPTK Pending", fptk_pending)
    col2.metric("⏳ Sourcing Pending", src_pending)

    st.markdown("---")

    tab_fptk, tab_sourcing = st.tabs(["📋 Request Hapus FPTK", "👤 Request Hapus Sourcing"])

    with tab_fptk:
        render_fptk_tab(db, user)

    with tab_sourcing:
        render_sourcing_tab(db, user)


def render_fptk_tab(db, user):
    pending_count = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.status == "PENDING"
    ).count()
    approved_count = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.status == "APPROVED"
    ).count()
    rejected_count = db.query(FPTKDeleteRequest).filter(
        FPTKDeleteRequest.status == "REJECTED"
    ).count()

    col1, col2, col3 = st.columns(3)
    col1.metric("⏳ Pending", pending_count)
    col2.metric("✅ Approved", approved_count)
    col3.metric("❌ Rejected", rejected_count)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["⏳ Pending", "✅ Approved", "❌ Rejected"])

    with tab1:
        pending_requests = db.query(FPTKDeleteRequest).filter(
            FPTKDeleteRequest.status == "PENDING"
        ).order_by(FPTKDeleteRequest.requested_at.desc()).all()

        if not pending_requests:
            st.info("Tidak ada request pending.")
        else:
            for req in pending_requests:
                with st.container():
                    st.markdown(f"### 📩 Request #{req.id}")

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**FPTK:** {req.kode_unik} | {req.posisi}")
                        st.markdown(f"**PIC:** {req.pic_recruiter}")
                        st.markdown(f"**Requested by:** {req.requested_by_name}")
                        st.markdown(f"**Tanggal:** {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")

                        st.markdown("**Alasan dari PIC:**")
                        st.info(req.reason)

                    with col2:
                        st.markdown("**Aksi:**")

                        if st.button(f"✅ Approve", key=f"approve_{req.id}", type="primary", use_container_width=True):
                            try:
                                fptk = db.query(FPTK).filter(FPTK.id == req.fptk_id).first()
                                if fptk:
                                    try:
                                        from core.models import TransferHistory
                                        db.query(TransferHistory).filter(
                                            TransferHistory.fptk_id == req.fptk_id
                                        ).delete(synchronize_session=False)
                                    except Exception:
                                        pass

                                    db.delete(fptk)

                                req.status = "APPROVED"
                                req.reviewed_by = user.id
                                req.reviewed_by_name = user.display_name
                                req.reviewed_at = datetime.now()
                                db.commit()

                                st.cache_data.clear()
                                st.success(f"✅ FPTK {req.kode_unik} dihapus!")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()

                        if st.button(f"❌ Reject", key=f"reject_{req.id}", use_container_width=True):
                            st.session_state[f"show_reject_{req.id}"] = True

                        if st.session_state.get(f"show_reject_{req.id}", False):
                            with st.form(f"reject_form_{req.id}"):
                                reject_reason = st.text_area(
                                    "Alasan Reject *",
                                    placeholder="Contoh: FPTK masih dibutuhkan, tidak ada duplikasi, dll.",
                                    height=100
                                )
                                if st.form_submit_button("Konfirmasi Reject", type="primary"):
                                    if not reject_reason or len(reject_reason.strip()) < 5:
                                        st.error("Alasan wajib diisi minimal 5 karakter!")
                                    else:
                                        try:
                                            req.status = "REJECTED"
                                            req.reviewed_by = user.id
                                            req.reviewed_by_name = user.display_name
                                            req.reviewed_at = datetime.now()
                                            req.admin_notes = reject_reason.strip()
                                            db.commit()

                                            st.cache_data.clear()
                                            st.success(f"❌ Request #{req.id} ditolak.")
                                            st.session_state[f"show_reject_{req.id}"] = False
                                            time.sleep(0.5)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Error: {str(e)}")
                                            db.rollback()

                    st.markdown("---")

    with tab2:
        approved_requests = db.query(FPTKDeleteRequest).filter(
            FPTKDeleteRequest.status == "APPROVED"
        ).order_by(FPTKDeleteRequest.reviewed_at.desc()).all()

        if not approved_requests:
            st.info("Belum ada request yang di-approve.")
        else:
            data = []
            for req in approved_requests:
                data.append({
                    "ID": req.id,
                    "Kode Unik": req.kode_unik,
                    "Posisi": req.posisi,
                    "PIC": req.pic_recruiter,
                    "Requested By": req.requested_by_name,
                    "Requested At": req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-',
                    "Approved By": req.reviewed_by_name,
                    "Approved At": req.reviewed_at.strftime('%d/%m/%Y %H:%M') if req.reviewed_at else '-',
                    "Alasan": req.reason[:100] + "..." if req.reason and len(req.reason) > 100 else req.reason
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with tab3:
        rejected_requests = db.query(FPTKDeleteRequest).filter(
            FPTKDeleteRequest.status == "REJECTED"
        ).order_by(FPTKDeleteRequest.reviewed_at.desc()).all()

        if not rejected_requests:
            st.info("Belum ada request yang di-reject.")
        else:
            for req in rejected_requests:
                with st.container():
                    st.markdown(f"### ❌ Request #{req.id} - DITOLAK")
                    st.markdown(f"**FPTK:** {req.kode_unik} | {req.posisi}")
                    st.markdown(f"**PIC:** {req.pic_recruiter}")
                    st.markdown(f"**Requested by:** {req.requested_by_name} - {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")
                    st.markdown(f"**Alasan PIC:**")
                    st.info(req.reason)
                    st.markdown(f"**Rejected by:** {req.reviewed_by_name} - {req.reviewed_at.strftime('%d/%m/%Y %H:%M') if req.reviewed_at else '-'}")
                    st.markdown(f"**Alasan Reject Admin:**")
                    st.warning(req.admin_notes or "-")
                    st.markdown("---")


def render_sourcing_tab(db, user):
    pending_count = db.query(SourcingDeleteRequest).filter(
        SourcingDeleteRequest.status == "PENDING"
    ).count()
    approved_count = db.query(SourcingDeleteRequest).filter(
        SourcingDeleteRequest.status == "APPROVED"
    ).count()
    rejected_count = db.query(SourcingDeleteRequest).filter(
        SourcingDeleteRequest.status == "REJECTED"
    ).count()

    col1, col2, col3 = st.columns(3)
    col1.metric("⏳ Pending", pending_count)
    col2.metric("✅ Approved", approved_count)
    col3.metric("❌ Rejected", rejected_count)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["⏳ Pending", "✅ Approved", "❌ Rejected"])

    with tab1:
        pending_requests = db.query(SourcingDeleteRequest).filter(
            SourcingDeleteRequest.status == "PENDING"
        ).order_by(SourcingDeleteRequest.requested_at.desc()).all()

        if not pending_requests:
            st.info("Tidak ada request pending.")
        else:
            for req in pending_requests:
                with st.container():
                    st.markdown(f"### 📩 Request #{req.id}")

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Kandidat:** {req.nama}")
                        st.markdown(f"**Kode Unik:** {req.kode_unik}")
                        st.markdown(f"**Posisi:** {req.posisi or '-'}")
                        st.markdown(f"**PIC:** {req.pic_recruiter or '-'}")
                        st.markdown(f"**Requested by:** {req.requested_by_name}")
                        st.markdown(f"**Tanggal:** {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")

                        st.markdown("**Alasan dari PIC:**")
                        st.info(req.reason)

                    with col2:
                        st.markdown("**Aksi:**")

                        if st.button(f"✅ Approve", key=f"approve_src_{req.id}", type="primary", use_container_width=True):
                            try:
                                src = db.query(DBSourcing).filter(DBSourcing.id == req.sourcing_id).first()
                                if src:
                                    db.delete(src)

                                req.status = "APPROVED"
                                req.reviewed_by = user.id
                                req.reviewed_by_name = user.display_name
                                req.reviewed_at = datetime.now()
                                db.commit()

                                st.cache_data.clear()
                                st.success(f"✅ Kandidat {req.nama} dihapus!")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()

                        if st.button(f"❌ Reject", key=f"reject_src_{req.id}", use_container_width=True):
                            st.session_state[f"show_reject_src_{req.id}"] = True

                        if st.session_state.get(f"show_reject_src_{req.id}", False):
                            with st.form(f"reject_src_form_{req.id}"):
                                reject_reason = st.text_area(
                                    "Alasan Reject *",
                                    placeholder="Contoh: Data masih dibutuhkan, tidak ada duplikasi, dll.",
                                    height=100
                                )
                                if st.form_submit_button("Konfirmasi Reject", type="primary"):
                                    if not reject_reason or len(reject_reason.strip()) < 5:
                                        st.error("Alasan wajib diisi minimal 5 karakter!")
                                    else:
                                        try:
                                            req.status = "REJECTED"
                                            req.reviewed_by = user.id
                                            req.reviewed_by_name = user.display_name
                                            req.reviewed_at = datetime.now()
                                            req.admin_notes = reject_reason.strip()
                                            db.commit()

                                            st.cache_data.clear()
                                            st.success(f"❌ Request #{req.id} ditolak.")
                                            st.session_state[f"show_reject_src_{req.id}"] = False
                                            time.sleep(0.5)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Error: {str(e)}")
                                            db.rollback()

                    st.markdown("---")

    with tab2:
        approved_requests = db.query(SourcingDeleteRequest).filter(
            SourcingDeleteRequest.status == "APPROVED"
        ).order_by(SourcingDeleteRequest.reviewed_at.desc()).all()

        if not approved_requests:
            st.info("Belum ada request yang di-approve.")
        else:
            data = []
            for req in approved_requests:
                data.append({
                    "ID": req.id,
                    "Nama": req.nama,
                    "Kode Unik": req.kode_unik,
                    "Posisi": req.posisi or "-",
                    "PIC": req.pic_recruiter or "-",
                    "Requested By": req.requested_by_name,
                    "Requested At": req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-',
                    "Approved By": req.reviewed_by_name,
                    "Approved At": req.reviewed_at.strftime('%d/%m/%Y %H:%M') if req.reviewed_at else '-',
                    "Alasan": req.reason[:100] + "..." if req.reason and len(req.reason) > 100 else req.reason
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with tab3:
        rejected_requests = db.query(SourcingDeleteRequest).filter(
            SourcingDeleteRequest.status == "REJECTED"
        ).order_by(SourcingDeleteRequest.reviewed_at.desc()).all()

        if not rejected_requests:
            st.info("Belum ada request yang di-reject.")
        else:
            for req in rejected_requests:
                with st.container():
                    st.markdown(f"### ❌ Request #{req.id} - DITOLAK")
                    st.markdown(f"**Kandidat:** {req.nama} | {req.kode_unik}")
                    st.markdown(f"**Posisi:** {req.posisi or '-'}")
                    st.markdown(f"**PIC:** {req.pic_recruiter or '-'}")
                    st.markdown(f"**Requested by:** {req.requested_by_name} - {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")
                    st.markdown(f"**Alasan PIC:**")
                    st.info(req.reason)
                    st.markdown(f"**Rejected by:** {req.reviewed_by_name} - {req.reviewed_at.strftime('%d/%m/%Y %H:%M') if req.reviewed_at else '-'}")
                    st.markdown(f"**Alasan Reject Admin:**")
                    st.warning(req.admin_notes or "-")
                    st.markdown("---")
