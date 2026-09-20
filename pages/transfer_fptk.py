# pages/transfer_fptk.py
import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import FPTK, User, TransferHistory
from core.auth import get_current_user, is_admin, is_it, is_editor
from datetime import datetime
import time


def show_transfer_fptk():
    st.title("🔄 Transfer FPTK")
    st.markdown("Transfer FPTK dari satu PIC ke PIC lain.")

    db = next(get_db())

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

    tab1, tab2 = st.tabs(["🔄 Transfer FPTK", "📜 History Transfer"])

    with tab1:
        show_transfer_form(db, user)

    with tab2:
        show_transfer_history(db)

    db.close()


def show_transfer_form(db, user):
    st.subheader("Pilih FPTK yang akan ditransfer")

    col1, col2 = st.columns([2, 2])

    with col1:
        search = st.text_input(
            "🔎 Cari (Kode Unik / Posisi)",
            placeholder="Ketik kode unik atau posisi...",
            key="transfer_fptk_search"
        )

    with col2:
        status_filter = st.selectbox(
            "Filter Status",
            ["Semua", "OP", "Closed", "Cancel"],
            key="transfer_fptk_status"
        )

    query = db.query(FPTK)

    if search:
        s = search.strip()
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{s}%")) |
            (FPTK.posisi.ilike(f"%{s}%"))
        )

    if status_filter != "Semua":
        query = query.filter(FPTK.status == status_filter)

    query = query.order_by(FPTK.fptk_date_real.desc()).limit(500)
    fptk_list = query.all()

    if not fptk_list:
        st.warning("Tidak ada data FPTK yang cocok.")
        return

    st.markdown(f"**Ditemukan {len(fptk_list)} FPTK**")

    display_data = []
    for f in fptk_list:
        display_data.append({
            "pilih": False,
            "id": f.id,
            "kode_unik": f.kode_unik,
            "posisi": f.posisi,
            "pic_recruiter": f.pic_recruiter,
            "status": f.status,
            "level_fptk": f.level_fptk,
            "business_unit": f.business_unit or "-",
        })

    df = pd.DataFrame(display_data)

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "pilih": st.column_config.CheckboxColumn("Pilih", default=False),
            "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "kode_unik": st.column_config.TextColumn("Kode Unik", disabled=True, width="medium"),
            "posisi": st.column_config.TextColumn("Posisi", disabled=True, width="large"),
            "pic_recruiter": st.column_config.TextColumn("PIC Saat Ini", disabled=True, width="medium"),
            "status": st.column_config.TextColumn("Status", disabled=True, width="small"),
            "level_fptk": st.column_config.TextColumn("Level", disabled=True, width="small"),
            "business_unit": st.column_config.TextColumn("BU", disabled=True, width="medium"),
        },
        key="transfer_fptk_table"
    )

    selected_ids = edited_df[edited_df["pilih"] == True]["id"].tolist()

    st.markdown(f"**{len(selected_ids)} FPTK dipilih**")

    if not selected_ids:
        st.info("Pilih minimal 1 FPTK untuk ditransfer.")
        return

    st.markdown("---")
    st.markdown("### Transfer Ke PIC Tujuan")

    target_users = db.query(User).filter(
        User.role.in_(['user', 'admin']),
        User.pic_recruiter.isnot(None)
    ).all()

    target_options = {}
    for u in target_users:
        display = f"{u.pic_recruiter} ({u.username})"
        target_options[display] = u.pic_recruiter

    if not target_options:
        st.warning("Tidak ada PIC tujuan yang tersedia.")
        return

    target_pic_display = st.selectbox(
        "PIC Tujuan",
        list(target_options.keys()),
        key="transfer_target_pic"
    )
    target_pic_value = target_options[target_pic_display]

    reason = st.text_area(
        "Alasan Transfer *",
        placeholder="Isi alasan transfer (min 10 karakter)...",
        height=100,
        key="transfer_reason"
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Transfer Sekarang", type="primary", use_container_width=True):
            if not reason or len(reason.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                success_count = 0
                error_count = 0
                errors = []

                for fptk_id in selected_ids:
                    try:
                        fptk = db.query(FPTK).filter(FPTK.id == fptk_id).first()
                        if not fptk:
                            error_count += 1
                            errors.append(f"ID {fptk_id}: FPTK tidak ditemukan")
                            continue

                        if fptk.pic_recruiter == target_pic_value:
                            error_count += 1
                            errors.append(f"{fptk.kode_unik}: PIC sudah sama ({target_pic_value})")
                            continue

                        old_pic = fptk.pic_recruiter

                        fptk.pic_recruiter = target_pic_value
                        fptk.last_updated_at = datetime.now()
                        fptk.last_compile_action = "TRANSFER"

                        history = TransferHistory(
                            fptk_id=fptk.id,
                            kode_unik=fptk.kode_unik,
                            posisi=fptk.posisi,
                            from_pic=old_pic,
                            to_pic=target_pic_value,
                            reason=reason.strip(),
                            transferred_by=user.id,
                            transferred_by_name=user.display_name or user.username
                        )
                        db.add(history)
                        db.commit()
                        success_count += 1

                    except Exception as e:
                        error_count += 1
                        errors.append(f"ID {fptk_id}: {str(e)}")
                        db.rollback()

                st.success(f"✅ Berhasil transfer: {success_count} FPTK")
                if error_count > 0:
                    st.warning(f"⚠️ Gagal: {error_count} FPTK")
                    with st.expander("Detail Error"):
                        for err in errors:
                            st.text(err)

                st.balloons()
                time.sleep(1)
                st.rerun()


def show_transfer_history(db):
    st.subheader("📜 History Transfer FPTK")

    col1, col2 = st.columns(2)

    with col1:
        pic_options = ["Semua"] + sorted(set([
            p[0] for p in db.query(FPTK.pic_recruiter).distinct().all() if p[0]
        ]))
        pic_filter = st.selectbox("Filter PIC", pic_options, key="transfer_hist_pic")

    with col2:
        search = st.text_input(
            "Cari (Kode Unik / Posisi / Alasan)",
            placeholder="Ketik keyword...",
            key="transfer_hist_search"
        )

    col3, col4 = st.columns(2)
    with col3:
        filter_type = st.selectbox(
            "Filter Waktu",
            ["Semua", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir"],
            key="transfer_hist_time"
        )

    query = db.query(TransferHistory).order_by(TransferHistory.created_at.desc())

    if pic_filter != "Semua":
        query = query.filter(
            (TransferHistory.from_pic == pic_filter) |
            (TransferHistory.to_pic == pic_filter)
        )

    if search:
        s = search.strip()
        query = query.filter(
            (TransferHistory.kode_unik.ilike(f"%{s}%")) |
            (TransferHistory.posisi.ilike(f"%{s}%")) |
            (TransferHistory.reason.ilike(f"%{s}%"))
        )

    if filter_type == "Hari Ini":
        today = datetime.now().date()
        query = query.filter(TransferHistory.created_at >= datetime.combine(today, datetime.min.time()))
    elif filter_type == "7 Hari Terakhir":
        query = query.filter(TransferHistory.created_at >= (datetime.now() - pd.Timedelta(days=7)))
    elif filter_type == "30 Hari Terakhir":
        query = query.filter(TransferHistory.created_at >= (datetime.now() - pd.Timedelta(days=30)))

    histories = query.limit(500).all()

    if not histories:
        st.info("Belum ada history transfer.")
        return

    data = []
    for h in histories:
        data.append({
            "Tanggal": h.created_at.strftime("%d/%m/%Y %H:%M") if h.created_at else "-",
            "Kode Unik": h.kode_unik,
            "Posisi": h.posisi or "-",
            "From": h.from_pic,
            "To": h.to_pic,
            "Alasan": h.reason or "-",
            "Oleh": h.transferred_by_name or "-"
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📊 Statistik Transfer")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transfer", len(histories))

    to_counts = {}
    for h in histories:
        to_counts[h.to_pic] = to_counts.get(h.to_pic, 0) + 1
    if to_counts:
        most_receive = max(to_counts, key=to_counts.get)
        col2.metric("Paling Sering Menerima", most_receive, f"{to_counts[most_receive]}x")

    from_counts = {}
    for h in histories:
        from_counts[h.from_pic] = from_counts.get(h.from_pic, 0) + 1
    if from_counts:
        most_send = max(from_counts, key=from_counts.get)
        col3.metric("Paling Sering Mengirim", most_send, f"{from_counts[most_send]}x")

    month_counts = {}
    for h in histories:
        if h.created_at:
            month_key = h.created_at.strftime("%B %Y")
            month_counts[month_key] = month_counts.get(month_key, 0) + 1
    if month_counts:
        most_month = max(month_counts, key=month_counts.get)
        col4.metric("Bulan Terbanyak", most_month, f"{month_counts[most_month]}x")

    if st.button("📥 Export CSV", use_container_width=True):
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            csv,
            f"transfer_history_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
