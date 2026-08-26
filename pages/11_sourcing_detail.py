import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user, is_admin
from datetime import datetime

def show_sourcing_detail():
    st.title("📋 Detail Kandidat")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # Ambil ID dari session state atau parameter
    if "detail_id" in st.session_state:
        detail_id = st.session_state.detail_id
    else:
        detail_id = st.query_params.get("id", None)
        if detail_id:
            try:
                detail_id = int(detail_id)
            except:
                detail_id = None
    
    if not detail_id:
        st.info("Silakan pilih kandidat dari daftar terlebih dahulu.")
        if st.button("🔙 Kembali ke Daftar"):
            st.session_state['page'] = "sourcing_list"
            st.rerun()
        return
    
    # Load data
    detail = db.query(DBSourcing).filter(DBSourcing.id == detail_id).first()
    if not detail:
        st.error(f"Data dengan ID {detail_id} tidak ditemukan.")
        return
    
    # Load FPTK jika ada kode_unik
    fptk = None
    if detail.kode_unik:
        fptk = db.query(FPTK).filter(FPTK.kode_unik == detail.kode_unik).first()
    
    # ============================================================
    # HEADER CARD
    # ============================================================
    st.markdown(f"## {detail.nama or 'Nama tidak tersedia'}")
    st.caption(f"ID: {detail.id} | No: {detail.no} | PIC: {detail.rekruter or '-'}")
    
    st.markdown("---")
    
    # ============================================================
    # DATA KANDIDAT
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Data Kandidat")
        st.markdown(f"**Nama:** {detail.nama}")
        st.markdown(f"**Posisi:** {detail.posisi or '-'}")
        st.markdown(f"**Kode Unik:** {detail.kode_unik or '-'}")
        if fptk:
            st.markdown(f"**FPTK Status:** {fptk.status or '-'}")
            st.markdown(f"**FPTK PIC:** {fptk.pic_recruiter or '-'}")
        st.markdown(f"**Sumber:** {detail.sumber_sourcing or '-'}")
        st.markdown(f"**Model:** {detail.model_rekrutmen or '-'}")
        st.markdown(f"**Rekruter:** {detail.rekruter or '-'}")
        st.markdown(f"**Sourcing Date:** {detail.sourcing_date.strftime('%d/%m/%Y') if detail.sourcing_date else '-'}")
    
    with col2:
        st.markdown("### 📞 Kontak & Lokasi")
        st.markdown(f"**Email:** {detail.email or '-'}")
        st.markdown(f"**Nomor HP:** {detail.nomor_hp or '-'}")
        st.markdown(f"**Domisili:** {detail.domisili or '-'}")
        st.markdown(f"**Last Position:** {detail.last_position or '-'}")
        st.markdown(f"**Last Company:** {detail.last_company or '-'}")
        st.markdown(f"**Last Tenure:** {detail.last_tenure or '-'}")
        st.markdown(f"**Total Tenure:** {detail.total_tenure or '-'}")
        st.markdown(f"**Pernah di FMCG:** {detail.pernah_di_fmcg or '-'}")
    
    st.markdown("---")
    
    # ============================================================
    # PENDIDIKAN
    # ============================================================
    st.markdown("### 🎓 Pendidikan")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Jenjang:** {detail.jenjang_pendidikan or '-'}")
        st.markdown(f"**Universitas (TOP 10):** {detail.nama_universitas_top10 or '-'}")
    with col2:
        st.markdown(f"**Universitas Lainnya:** {detail.nama_universitas_lainnya or '-'}")
        st.markdown(f"**Jurusan:** {detail.jurusan or '-'}")
    with col3:
        st.markdown(f"**Tahun Lulus:** {detail.tahun_lulus or '-'}")
        st.markdown(f"**IPK:** {detail.ipk or '-'}")
        st.markdown(f"**University Tier:** {detail.university_tier or '-'}")
        st.markdown(f"**IPK Tier:** {detail.ipk_tier or '-'}")
    
    st.markdown("---")
    
    # ============================================================
    # PIPELINE STATUS
    # ============================================================
    st.markdown("### 📊 Pipeline Status")
    
    pipeline = [
        ("Sourcing HR", detail.sourcing_hr, detail.tanggal_sourcing, detail.detail_keterangan_sourcing_hr),
        ("Shortlist CV", detail.shortlist_cv, detail.tanggal_shortlist_cv, detail.detail_keterangan_shortlist_cv),
        ("Psikotes", detail.psikotes, detail.tanggal_psikotes, detail.detail_keterangan_psikotes),
        ("HR Interview", detail.hr_interview, detail.tanggal_hr_interview, detail.detail_keterangan_hr_interview),
        ("User Interview", detail.user_interview, detail.tanggal_user_interview, detail.detail_keterangan_user_interview),
        ("Offering", detail.offering, detail.tanggal_offering, detail.detail_keterangan_offering),
        ("Day 1", detail.day1, detail.tanggal_day1, detail.detail_keterangan_day1),
    ]
    
    for stage, status, tgl, alasan in pipeline:
        if status == "V":
            emoji, color = "✅", "green"
        elif status == "X":
            emoji, color = "❌", "red"
        else:
            emoji, color = "⏳", "gray"
        
        tgl_str = tgl.strftime("%d/%m/%Y") if tgl else "-"
        alasan_str = f" - {alasan}" if alasan else ""
        
        st.markdown(f"{emoji} **{stage}:** {status or 'Belum'} | {tgl_str} {alasan_str}")
    
    st.markdown("---")
    
    # ============================================================
    # METADATA & AUDIT
    # ============================================================
    st.markdown("### 📋 Metadata")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Created At:** {detail.created_at.strftime('%d/%m/%Y %H:%M') if detail.created_at else '-'}")
        st.markdown(f"**Last Updated:** {detail.last_updated_at.strftime('%d/%m/%Y %H:%M') if detail.last_updated_at else '-'}")
    with col2:
        st.markdown(f"**Source File:** {detail.source_file or '-'}")
        st.markdown(f"**Last Compile Action:** {detail.last_compile_action or '-'}")
    
    st.markdown("---")
    
    # ============================================================
    # ACTION BUTTONS
    # ============================================================
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("✏️ Edit", type="primary"):
            st.session_state['edit_id'] = detail.id
            st.session_state['page'] = "sourcing_edit"
            st.rerun()
    
    with col2:
        if st.button("🔙 Kembali", use_container_width=True):
            st.session_state['page'] = "sourcing_list"
            st.rerun()
    
    with col3:
        if is_admin(db):
            if st.button("🗑️ Hapus Data Ini", type="secondary"):
                confirm = st.warning("Yakin ingin menghapus data ini?")
                if st.button("Ya, Hapus", key="confirm_delete_detail"):
                    db.delete(detail)
                    db.commit()
                    st.success("Data berhasil dihapus!")
                    st.session_state['page'] = "sourcing_list"
                    st.rerun()
