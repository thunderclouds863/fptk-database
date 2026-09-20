# pages/candidate_transfer.py
import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing, FPTK, CandidateTransfer, User
from core.auth import get_current_user, is_admin, is_it
from core.utils import get_last_pipeline_stage, transfer_candidate, transfer_candidates_bulk
from datetime import datetime
import time


def show_candidate_transfer():
    st.title("🔄 Transfer Kandidat")
    st.markdown("Pindahkan kandidat dari satu FPTK ke FPTK lain (recycle).")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    if is_it(db):
        st.info("🔍 Mode View-Only (IT) - Anda hanya bisa melihat history transfer.")
        show_transfer_history_only(db)
        return

    admin = is_admin(db)

    tab1, tab2, tab3 = st.tabs(["🔄 Transfer Single", "📦 Transfer Bulk", "📜 History Transfer"])

    with tab1:
        show_transfer_single(db, user, admin)

    with tab2:
        show_transfer_bulk(db, user, admin)

    with tab3:
        show_transfer_history(db, admin)


def show_transfer_single(db, user, admin):
    st.subheader("Transfer 1 Kandidat")

    fptk_list = db.query(FPTK).filter(FPTK.status == "OP").order_by(FPTK.kode_unik).all()
    fptk_options = {f"{f.kode_unik} | {f.posisi[:50]}" if len(str(f.posisi)) > 50 else f"{f.kode_unik} | {f.posisi}": f.kode_unik for f in fptk_list}

    if not fptk_options:
        st.warning("Tidak ada FPTK OP yang tersedia.")
        return

    filter_fptk = st.selectbox("Filter dari FPTK Asal", ["Semua"] + list(fptk_options.keys()))

    query = db.query(DBSourcing)

    if filter_fptk != "Semua":
        kode_unik_filter = fptk_options[filter_fptk]
        query = query.filter(DBSourcing.kode_unik == kode_unik_filter)

    if not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)

    candidates = query.limit(500).all()

    if not candidates:
        st.info("Tidak ada kandidat yang bisa ditransfer.")
        return

    search = st.text_input("🔎 Cari Kandidat (Nama / Kode Unik)", placeholder="Ketik keyword...")

    if search:
        s = search.strip().lower()
        candidates = [c for c in candidates if s in (c.nama or "").lower() or s in (c.kode_unik or "").lower()]

    if not candidates:
        st.info("Tidak ada kandidat yang cocok.")
        return

    cand_options = {}
    for c in candidates:
        last_stage = get_last_pipeline_stage(c)
        stage_label = last_stage["stage_label"] if last_stage else "Belum ada stage"
        display = f"{c.kode_unik} | {c.nama} | {stage_label}"
        cand_options[display] = c.id

    selected_display = st.selectbox("Pilih Kandidat", list(cand_options.keys()))
    selected_id = cand_options.get(selected_display)

    if not selected_id:
        return

    candidate = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
    if not candidate:
        st.error("Kandidat tidak ditemukan.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nama:** {candidate.nama}")
        st.markdown(f"**Kode Unik Saat Ini:** {candidate.kode_unik}")
        st.markdown(f"**Posisi:** {candidate.posisi or '-'}")
        st.markdown(f"**PIC:** {candidate.rekruter or '-'}")
        st.markdown(f"**Email:** {candidate.email or '-'}")
        st.markdown(f"**No HP:** {candidate.nomor_hp or '-'}")

    with col2:
        last_stage = get_last_pipeline_stage(candidate)
        if last_stage:
            st.markdown(f"**Tahap Terakhir:** {last_stage['stage_label']}")
            st.markdown(f"**Status:** {last_stage['status']}")
            st.markdown(f"**Tanggal:** {last_stage['tanggal'].strftime('%d/%m/%Y') if last_stage['tanggal'] else '-'}")
        else:
            st.info("Kandidat belum masuk tahap pipeline apapun.")

    st.markdown("---")
    st.markdown("### Transfer Ke FPTK Tujuan")

    target_fptk = st.selectbox("Pilih FPTK Tujuan", list(fptk_options.keys()), key="target_fptk_single")
    new_kode_unik = fptk_options[target_fptk]

    reason = st.text_area(
        "Alasan Transfer *",
        placeholder="Contoh: Kandidat lebih cocok untuk posisi ini, kandidat direcycle, dll.",
        height=100,
        key="transfer_reason_single"
    )

    if st.button("🔄 Transfer Kandidat", type="primary", use_container_width=True, key="btn_transfer_single"):
        if not reason or len(reason.strip()) < 10:
            st.error("❌ Alasan wajib diisi minimal 10 karakter!")
        else:
            with st.spinner("Memproses transfer..."):
                result = transfer_candidate(
                    db,
                    selected_id,
                    new_kode_unik,
                    reason.strip(),
                    user.id,
                    user.display_name or user.username
                )

                if result["success"]:
                    st.success(f"✅ Kandidat **{candidate.nama}** berhasil ditransfer!")
                    st.info(f"📋 Dari: {result['old_kode_unik']} → Ke: {result['new_kode_unik']}")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Gagal transfer: {result.get('error', 'Unknown error')}")


def show_transfer_bulk(db, user, admin):
    st.subheader("Transfer Banyak Kandidat (Bulk)")

    fptk_list = db.query(FPTK).filter(FPTK.status == "OP").order_by(FPTK.kode_unik).all()
    fptk_options = {f"{f.kode_unik} | {f.posisi[:50]}" if len(str(f.posisi)) > 50 else f"{f.kode_unik} | {f.posisi}": f.kode_unik for f in fptk_list}

    if not fptk_options:
        st.warning("Tidak ada FPTK OP yang tersedia.")
        return

    filter_fptk = st.selectbox("Filter dari FPTK Asal", ["Semua"] + list(fptk_options.keys()), key="bulk_filter_fptk")

    query = db.query(DBSourcing)

    if filter_fptk != "Semua":
        kode_unik_filter = fptk_options[filter_fptk]
        query = query.filter(DBSourcing.kode_unik == kode_unik_filter)

    if not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)

    candidates = query.limit(500).all()

    if not candidates:
        st.info("Tidak ada kandidat yang bisa ditransfer.")
        return

    search = st.text_input("🔎 Cari Kandidat (Nama / Kode Unik)", placeholder="Ketik keyword...", key="bulk_search")

    if search:
        s = search.strip().lower()
        candidates = [c for c in candidates if s in (c.nama or "").lower() or s in (c.kode_unik or "").lower()]

    if not candidates:
        st.info("Tidak ada kandidat yang cocok.")
        return

    bulk_data = []
    for c in candidates:
        last_stage = get_last_pipeline_stage(c)
        bulk_data.append({
            "pilih": False,
            "id": c.id,
            "kode_unik": c.kode_unik,
            "nama": c.nama,
            "posisi": (c.posisi or "")[:50],
            "rekruter": c.rekruter or "-",
            "tahap_terakhir": last_stage["stage_label"] if last_stage else "-",
        })

    bulk_df = pd.DataFrame(bulk_data)

    edited_df = st.data_editor(
        bulk_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "pilih": st.column_config.CheckboxColumn("Pilih", default=False),
            "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "kode_unik": st.column_config.TextColumn("Kode Unik", disabled=True, width="medium"),
            "nama": st.column_config.TextColumn("Nama", disabled=True, width="medium"),
            "posisi": st.column_config.TextColumn("Posisi", disabled=True, width="medium"),
            "rekruter": st.column_config.TextColumn("PIC", disabled=True, width="small"),
            "tahap_terakhir": st.column_config.TextColumn("Tahap Terakhir", disabled=True, width="medium"),
        },
        key="bulk_transfer_table"
    )

    selected_ids = edited_df[edited_df["pilih"] == True]["id"].tolist()

    st.markdown(f"**{len(selected_ids)} kandidat dipilih**")

    if selected_ids:
        st.markdown("---")
        st.markdown("### Transfer Ke FPTK Tujuan")

        target_fptk_bulk = st.selectbox("Pilih FPTK Tujuan", list(fptk_options.keys()), key="target_fptk_bulk")
        new_kode_unik_bulk = fptk_options[target_fptk_bulk]

        reason_bulk = st.text_area(
            "Alasan Transfer *",
            placeholder="Contoh: Recycle kandidat ke FPTK baru.",
            height=100,
            key="transfer_reason_bulk"
        )

        if st.button("🔄 Transfer Semua Kandidat Terpilih", type="primary", use_container_width=True, key="btn_transfer_bulk"):
            if not reason_bulk or len(reason_bulk.strip()) < 10:
                st.error("❌ Alasan wajib diisi minimal 10 karakter!")
            else:
                with st.spinner(f"Memproses {len(selected_ids)} kandidat..."):
                    result = transfer_candidates_bulk(
                        db,
                        selected_ids,
                        new_kode_unik_bulk,
                        reason_bulk.strip(),
                        user.id,
                        user.display_name or user.username
                    )

                    st.success(f"✅ Transfer selesai!")
                    st.info(f"📋 Berhasil: {result['success_count']}")
                    st.warning(f"⚠️ Gagal: {result['error_count']}")

                    if result["errors"]:
                        with st.expander("❌ Detail Error"):
                            for err in result["errors"]:
                                st.text(err)

                    st.balloons()
                    time.sleep(1)
                    st.rerun()


def show_transfer_history(db, admin):
    st.subheader("📜 History Transfer Kandidat")

    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("Cari (Nama / Kode Unik)", placeholder="Ketik keyword...")

    with col2:
        filter_type = st.selectbox("Filter", ["Semua", "Hari Ini", "7 Hari Terakhir", "30 Hari Terakhir"])

    query = db.query(CandidateTransfer).order_by(CandidateTransfer.transferred_at.desc())

    if search:
        s = search.strip()
        query = query.filter(
            (CandidateTransfer.nama.ilike(f"%{s}%")) |
            (CandidateTransfer.old_kode_unik.ilike(f"%{s}%")) |
            (CandidateTransfer.new_kode_unik.ilike(f"%{s}%"))
        )

    if filter_type == "Hari Ini":
        today = datetime.now().date()
        query = query.filter(CandidateTransfer.transferred_at >= datetime.combine(today, datetime.min.time()))
    elif filter_type == "7 Hari Terakhir":
        query = query.filter(CandidateTransfer.transferred_at >= (datetime.now() - pd.Timedelta(days=7)))
    elif filter_type == "30 Hari Terakhir":
        query = query.filter(CandidateTransfer.transferred_at >= (datetime.now() - pd.Timedelta(days=30)))

    histories = query.limit(500).all()

    if not histories:
        st.info("Belum ada history transfer.")
        return

    data = []
    for h in histories:
        data.append({
            "Tanggal": h.transferred_at.strftime("%d/%m/%Y %H:%M") if h.transferred_at else "-",
            "Nama": h.nama,
            "Dari Kode Unik": h.old_kode_unik,
            "Ke Kode Unik": h.new_kode_unik,
            "Tahap Terakhir": h.old_pipeline_stage or "-",
            "Alasan": h.reason or "-",
            "Oleh": h.transferred_by_name or "-",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📊 Statistik")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Transfer", len(histories))

    if histories:
        to_counts = {}
        for h in histories:
            to_counts[h.new_kode_unik] = to_counts.get(h.new_kode_unik, 0) + 1
        if to_counts:
            most_receive = max(to_counts, key=to_counts.get)
            col2.metric("FPTK Paling Sering Menerima", most_receive, f"{to_counts[most_receive]}x")

        from_counts = {}
        for h in histories:
            from_counts[h.old_kode_unik] = from_counts.get(h.old_kode_unik, 0) + 1
        if from_counts:
            most_send = max(from_counts, key=from_counts.get)
            col3.metric("FPTK Paling Sering Mengirim", most_send, f"{from_counts[most_send]}x")

    if st.button("📥 Export CSV", use_container_width=True):
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            csv,
            f"candidate_transfer_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv"
        )


def show_transfer_history_only(db):
    st.subheader("📜 History Transfer Kandidat (View-Only)")
    show_transfer_history(db, admin=False)


if __name__ == "__main__":
    show_candidate_transfer()
