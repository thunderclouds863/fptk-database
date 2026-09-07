import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import FPTK, User, TransferHistory
from core.auth import get_current_user, is_admin, is_it, is_editor
from datetime import datetime

def show_transfer_fptk():
    st.title("🔄 Transfer FPTK")
    st.markdown("Transfer FPTK dari satu PIC ke PIC lain.")
    
    db = next(get_db())
    
    # Cek akses
    if is_it(db):
        st.info("🔍 Mode View-Only (IT) - Anda hanya bisa melihat history transfer.")
        show_transfer_history(db)
        db.close()
        return
    
    if not is_editor(db):
        st.error("❌ Anda tidak memiliki akses untuk transfer FPTK. Hubungi Admin.")
        db.close()
        return
    
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        db.close()
        return
    
    # ============================================================
    # TAB: TRANSFER & HISTORY
    # ============================================================
    tab1, tab2 = st.tabs(["🔄 Transfer FPTK", "📜 History Transfer"])
    
    with tab1:
        show_transfer_form(db, user)
    
    with tab2:
        show_transfer_history(db)
    
    db.close()


# ============================================================
# FORM TRANSFER
# ============================================================
def show_transfer_form(db, user):
    st.subheader("Pilih FPTK yang akan ditransfer")
    
    # Filter FPTK by PIC
    pic_options = ["Semua"] + [p[0] for p in db.query(FPTK.pic_recruiter).distinct().all() if p[0]]
    pic_filter = st.selectbox("PIC Saat Ini", pic_options)
    
    search = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
    
    query = db.query(FPTK)
    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)
    if search:
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{search}%")) |
            (FPTK.posisi.ilike(f"%{search}%"))
        )
    query = query.limit(100)
    
    df = pd.read_sql(query.statement, db.bind)
    
    if df.empty:
        st.warning("Tidak ada data FPTK.")
        return
    
    st.dataframe(
        df[['id', 'kode_unik', 'posisi', 'pic_recruiter', 'status']],
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("Transfer")
    
    selected_id = st.selectbox("Pilih ID FPTK yang akan ditransfer", df['id'].tolist())
    
    if selected_id:
        fptk = db.query(FPTK).filter(FPTK.id == selected_id).first()
        if fptk:
            st.info(f"📋 Data: **{fptk.kode_unik}** | {fptk.posisi} | PIC: **{fptk.pic_recruiter}**")
            
            # Pilih PIC tujuan (user aktif, bukan IT)
            target_users = db.query(User).filter(
                User.role.in_(['user', 'admin']),
                User.pic_recruiter.isnot(None),
                User.pic_recruiter != fptk.pic_recruiter
            ).all()
            
            target_options = {f"{u.pic_recruiter} ({u.username})": u.pic_recruiter for u in target_users}
            
            if not target_options:
                st.warning("Tidak ada PIC tujuan yang tersedia.")
            else:
                target_pic = st.selectbox(
                    "PIC Tujuan",
                    list(target_options.keys())
                )
                target_pic_value = target_options[target_pic]
                
                reason = st.text_area("Alasan Transfer", placeholder="Isi alasan transfer...")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("🔄 Transfer FPTK", type="primary", use_container_width=True):
                        if target_pic_value and reason:
                            old_pic = fptk.pic_recruiter
                            
                            # Update FPTK
                            fptk.pic_recruiter = target_pic_value
                            fptk.last_updated_at = datetime.now()
                            fptk.last_compile_action = "TRANSFER"
                            
                            # Simpan history
                            history = TransferHistory(
                                fptk_id=fptk.id,
                                kode_unik=fptk.kode_unik,
                                posisi=fptk.posisi,
                                from_pic=old_pic,
                                to_pic=target_pic_value,
                                reason=reason,
                                transferred_by=user.id,
                                transferred_by_name=user.display_name or user.username
                            )
                            db.add(history)
                            db.commit()
                            
                            st.success(f"✅ FPTK berhasil ditransfer!")
                            st.info(f"📋 {fptk.kode_unik} | {old_pic} → {target_pic_value}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Pilih PIC tujuan dan isi alasan transfer!")


# ============================================================
# HISTORY TRANSFER
# ============================================================
def show_transfer_history(db):
    st.subheader("📜 History Transfer FPTK")
    
    # Filter by PIC
    col1, col2 = st.columns(2)
    with col1:
        pic_filter = st.selectbox(
            "Filter PIC", 
            ["Semua"] + [p[0] for p in db.query(FPTK.pic_recruiter).distinct().all() if p[0]]
        )
    with col2:
        search = st.text_input("Cari Kode Unik / Posisi", placeholder="Ketik keyword...")
    
    query = db.query(TransferHistory).order_by(TransferHistory.created_at.desc()).limit(500)
    
    if pic_filter != "Semua":
        query = query.filter(
            (TransferHistory.from_pic == pic_filter) | 
            (TransferHistory.to_pic == pic_filter)
        )
    if search:
        query = query.filter(
            (TransferHistory.kode_unik.ilike(f"%{search}%")) |
            (TransferHistory.posisi.ilike(f"%{search}%"))
        )
    
    histories = query.all()
    
    if not histories:
        st.info("Belum ada history transfer.")
        return
    
    data = []
    for h in histories:
        data.append({
            "Tanggal": h.created_at.strftime("%d/%m/%Y %H:%M"),
            "Kode Unik": h.kode_unik,
            "Posisi": h.posisi,
            "From": h.from_pic,
            "To": h.to_pic,
            "Alasan": h.reason or "-",
            "Oleh": h.transferred_by_name or "-"
        })
    
    df = pd.DataFrame(data)
    st.dataframe(
        df,
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    # Statistik
    st.markdown("---")
    st.subheader("📊 Statistik Transfer")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transfer", len(histories))
    
    # PIC paling sering menerima
    to_counts = {}
    for h in histories:
        to_counts[h.to_pic] = to_counts.get(h.to_pic, 0) + 1
    if to_counts:
        most_receive = max(to_counts, key=to_counts.get)
        col2.metric("Paling Sering Menerima", most_receive, f"{to_counts[most_receive]}x")
    
    # PIC paling sering mengirim
    from_counts = {}
    for h in histories:
        from_counts[h.from_pic] = from_counts.get(h.from_pic, 0) + 1
    if from_counts:
        most_send = max(from_counts, key=from_counts.get)
        col3.metric("Paling Sering Mengirim", most_send, f"{from_counts[most_send]}x")
    
    # Bulan dengan transfer terbanyak
    month_counts = {}
    for h in histories:
        month_key = h.created_at.strftime("%B %Y")
        month_counts[month_key] = month_counts.get(month_key, 0) + 1
    if month_counts:
        most_month = max(month_counts, key=month_counts.get)
        col4.metric("Bulan Terbanyak", most_month, f"{month_counts[most_month]}x")
    
    # Export
    if st.button("📥 Export CSV", use_container_width=True):
        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            f"transfer_history_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
