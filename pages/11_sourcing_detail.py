import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user, is_admin
from datetime import datetime
import time

# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_data(ttl=3600)
def get_pipeline_stages_detail():
    """Pipeline stages lengkap - cache 1 jam"""
    return [
        {"field": "sourcing_freelance", "label": "Sourcing Freelance"},
        {"field": "sourcing_hr", "label": "Sourcing HR"},
        {"field": "shortlist_cv", "label": "Shortlist CV"},
        {"field": "psikotes", "label": "Psikotes"},
        {"field": "hr_interview", "label": "HR Interview"},
        {"field": "technical_test_case_study", "label": "Technical Test"},
        {"field": "market_visit", "label": "Market Visit"},
        {"field": "user_interview", "label": "User Interview"},
        {"field": "panel_interview", "label": "Panel Interview"},
        {"field": "reference_check", "label": "Reference Check"},
        {"field": "mcu", "label": "MCU"},
        {"field": "offering", "label": "Offering"},
        {"field": "day1", "label": "Day 1"}
    ]


@st.cache_data(ttl=3600)
def get_status_options_detail():
    """Status options - cache 1 jam"""
    return ["", "V", "X"]


@st.cache_data(ttl=3600)
def get_pic_options_detail(_db):
    """PIC options - cache 1 jam"""
    try:
        master = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        return sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
    except:
        return []


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show_sourcing_detail():
    st.title("📋 Detail Kandidat")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return
    
    # ============================================================
    # 🔥🔥🔥 LOAD FROM CACHE 🔥🔥🔥
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        pipeline_stages = get_pipeline_stages_detail()
        status_options = get_status_options_detail()
        pic_options = get_pic_options_detail(db)
    
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
        st.markdown(f"**Sumber Sourcing:** {detail.sumber_sourcing or '-'}")
        st.markdown(f"**Model Rekrutmen:** {detail.model_rekrutmen or '-'}")
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
        st.markdown(f"**Jenjang Pendidikan:** {detail.jenjang_pendidikan or '-'}")
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
    # 🔥🔥🔥 PIPELINE STATUS LENGKAP (13 STAGE) 🔥🔥🔥
    # ============================================================
    st.markdown("### 📊 Pipeline Status")
    st.caption("V = Lolos | X = Tidak Lolos | Kosong = Belum diproses")
    
    # Buat tabel pipeline
    pipeline_data = []
    for stage in pipeline_stages:
        field = getattr(detail, stage["field"])
        date_field = getattr(detail, f"tanggal_{stage['field']}")
        detail_field = getattr(detail, f"detail_keterangan_{stage['field']}")
        
        # Status dengan emoji
        if field == "V":
            emoji = "✅"
        elif field == "X":
            emoji = "❌"
        else:
            emoji = "⏳"
        
        tgl_str = date_field.strftime("%d/%m/%Y") if date_field else "-"
        keterangan = detail_field or "-"
        
        pipeline_data.append({
            "Tahap": f"{emoji} {stage['label']}",
            "Status": field or "-",
            "Tanggal": tgl_str,
            "Keterangan": keterangan
        })
    
    # Tampilkan sebagai dataframe
    pipeline_df = pd.DataFrame(pipeline_data)
    st.dataframe(pipeline_df, use_container_width=True, hide_index=True)
    
    # Tampilkan juga sebagai list yang rapi
    st.markdown("---")
    st.markdown("### 📋 Detail Pipeline")
    
    for stage in pipeline_stages:
        field = getattr(detail, stage["field"])
        date_field = getattr(detail, f"tanggal_{stage['field']}")
        detail_field = getattr(detail, f"detail_keterangan_{stage['field']}")
        
        if field == "V":
            emoji, color = "✅", "green"
        elif field == "X":
            emoji, color = "❌", "red"
        else:
            emoji, color = "⏳", "gray"
        
        tgl_str = date_field.strftime("%d/%m/%Y") if date_field else "-"
        alasan_str = f" - {detail_field}" if detail_field else ""
        
        st.markdown(f"{emoji} **{stage['label']}:** {field or 'Belum'} | {tgl_str} {alasan_str}")
    
    st.markdown("---")
    
    # ============================================================
    # NOTES & BLACKLIST
    # ============================================================
    st.markdown("### 📝 Catatan & Blacklist")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Catatan:** {detail.notes or '-'}")
    with col2:
        st.markdown(f"**Blacklist:** {'Ya' if detail.is_blacklisted else 'Tidak'}")
        if detail.is_blacklisted:
            st.markdown(f"**Tgl Blacklist:** {detail.blacklisted_at.strftime('%d/%m/%Y %H:%M') if detail.blacklisted_at else '-'}")
            st.markdown(f"**Alasan Blacklist:** {detail.blacklist_reason or '-'}")
    
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
    # 🔥🔥🔥 ACTION BUTTONS 🔥🔥🔥
    # ============================================================
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("✏️ Edit", type="primary", use_container_width=True):
            st.session_state['edit_id'] = detail.id
            st.session_state['page'] = "sourcing_edit"
            st.rerun()
    
    with col2:
        if st.button("🔙 Kembali", use_container_width=True):
            st.session_state['page'] = "sourcing_list"
            st.rerun()
    
    with col3:
        # Cek apakah user admin atau owner
        is_owner = detail.rekruter == user.pic_recruiter
        can_delete = is_admin(db) or is_owner
        
        if can_delete:
            if st.button("🗑️ Hapus Data Ini", use_container_width=True, type="secondary"):
                st.warning(f"⚠️ Yakin ingin menghapus data **{detail.nama}**?")
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("✅ Ya, Hapus", key="confirm_delete_detail"):
                        try:
                            db.delete(detail)
                            db.commit()
                            st.success("✅ Data berhasil dihapus!")
                            time.sleep(0.5)
                            st.session_state['page'] = "sourcing_list"
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal menghapus: {str(e)}")
                            db.rollback()
                with col_cancel:
                    if st.button("❌ Batal"):
                        st.rerun()
        else:
            st.info("🔒 Anda tidak memiliki akses untuk menghapus data ini.")
    
    # ============================================================
    # LINK KE FPTK (jika ada)
    # ============================================================
    if fptk:
        st.markdown("---")
        st.markdown("### 🔗 Terkait dengan FPTK")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Kode Unik:** {fptk.kode_unik}")
            st.markdown(f"**Posisi:** {fptk.posisi}")
        with col2:
            st.markdown(f"**Status FPTK:** {fptk.status}")
            st.markdown(f"**PIC FPTK:** {fptk.pic_recruiter}")
        
        if st.button("📋 Lihat FPTK Ini", use_container_width=True):
            st.session_state['detail_id'] = None
            st.session_state['page'] = "fptk_view"
            st.rerun()
