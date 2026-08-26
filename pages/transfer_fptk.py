import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import FPTK, User, AuditLog
from core.auth import get_current_user, is_admin

def show_transfer_fptk():
    st.title("🔄 Transfer FPTK")
    st.markdown("Transfer FPTK dari satu PIC ke PIC lain.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # PILIH FPTK YANG AKAN DITRANSFER
    # ============================================================
    
    st.subheader("📋 Pilih FPTK")
    
    # Filter FPTK berdasarkan user (hanya FPTK milik user)
    if is_admin(db):
        fptk_list = db.query(FPTK).order_by(FPTK.kode_unik).all()
    else:
        fptk_list = db.query(FPTK).filter(
            FPTK.pic_recruiter == user.pic_recruiter
        ).order_by(FPTK.kode_unik).all()
    
    if not fptk_list:
        st.warning("Tidak ada FPTK yang bisa ditransfer.")
        return
    
    # Dropdown pilih FPTK
    fptk_options = {
        f"{f.kode_unik} - {f.posisi} ({f.pic_recruiter})": f.id 
        for f in fptk_list
    }
    
    selected_label = st.selectbox("Pilih FPTK yang akan ditransfer", list(fptk_options.keys()))
    selected_fptk_id = fptk_options[selected_label]
    
    # Ambil detail FPTK
    fptk = db.query(FPTK).filter(FPTK.id == selected_fptk_id).first()
    
    if fptk:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Kode Unik:** {fptk.kode_unik}")
            st.markdown(f"**Posisi:** {fptk.posisi}")
        with col2:
            st.markdown(f"**PIC Saat Ini:** {fptk.pic_recruiter}")
            st.markdown(f"**Status:** {fptk.status}")
    
    # ============================================================
    # PILIH PIC TUJUAN
    # ============================================================
    
    st.markdown("---")
    st.subheader("👤 Transfer Ke")
    
    # Daftar PIC (dari User)
    pic_list = db.query(User).filter(
        User.role == "user",
        User.pic_recruiter != fptk.pic_recruiter
    ).all()
    
    if not pic_list:
        st.warning("Tidak ada PIC lain untuk ditransfer.")
        return
    
    pic_options = {u.pic_recruiter: u.id for u in pic_list}
    target_pic = st.selectbox("Pilih PIC Tujuan", list(pic_options.keys()))
    
    # Catatan transfer
    transfer_note = st.text_area("Catatan Transfer (opsional)", placeholder="Alasan transfer, dll")
    
    # ============================================================
    # PROSES TRANSFER
    # ============================================================
    
    if st.button("🚀 Transfer FPTK", type="primary"):
        if not target_pic:
            st.error("Pilih PIC tujuan!")
        else:
            try:
                # Simpan log transfer (audit)
                audit = AuditLog(
                    user_id=user.id,
                    action="TRANSFER_FPTK",
                    table_name="fptk",
                    record_id=fptk.id,
                    old_value={"pic_recruiter": fptk.pic_recruiter},
                    new_value={"pic_recruiter": target_pic},
                    created_at=datetime.now()
                )
                db.add(audit)
                
                # Update PIC Recruiter
                fptk.pic_recruiter = target_pic
                fptk.last_updated_at = datetime.now()
                fptk.last_compile_action = "TRANSFER"
                
                # Tambahkan remark
                if transfer_note:
                    old_remark = fptk.remark or ""
                    fptk.remark = f"{old_remark}\n[TRANSFER] {datetime.now().strftime('%d/%m/%Y')} - {user.pic_recruiter} → {target_pic}: {transfer_note}"
                
                db.commit()
                
                st.success(f"✅ FPTK berhasil ditransfer ke {target_pic}!")
                st.info(f"📋 Kode Unik: {fptk.kode_unik}")
                st.info(f"👤 PIC Baru: {target_pic}")
                st.balloons()
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error transfer: {str(e)}")
                db.rollback()
    
    # ============================================================
    # RIWAYAT TRANSFER
    # ============================================================
    
    st.markdown("---")
    st.subheader("📜 Riwayat Transfer")
    
    # Query audit log untuk transfer
    logs = db.query(AuditLog).filter(
        AuditLog.table_name == "fptk",
        AuditLog.action == "TRANSFER_FPTK"
    ).order_by(AuditLog.created_at.desc()).limit(50).all()
    
    if logs:
        data = []
        for log in logs:
            old_pic = log.old_value.get("pic_recruiter", "-") if log.old_value else "-"
            new_pic = log.new_value.get("pic_recruiter", "-") if log.new_value else "-"
            
            # Ambil user yang melakukan transfer
            transfer_user = db.query(User).filter(User.id == log.user_id).first()
            transfer_by = transfer_user.pic_recruiter if transfer_user else "-"
            
            data.append({
                "Tanggal": log.created_at.strftime("%d/%m/%Y %H:%M"),
                "Kode Unik": log.record_id,
                "Dari": old_pic,
                "Ke": new_pic,
                "Oleh": transfer_by
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada riwayat transfer.")
