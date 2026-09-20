# pages/blacklist_list.py
import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing, User, BlacklistRequest
from core.auth import get_current_user, is_admin, is_it
from datetime import datetime
import time


def request_unblacklist_dialog(db, sourcing_id, kode_unik, nama, posisi):
    @st.dialog("Request Un-Blacklist")
    def _dialog():
        st.info(f"**Kandidat:** {nama}")
        st.caption(f"Kode Unik: {kode_unik} | Posisi: {posisi}")

        reason = st.text_area(
            "Alasan Un-Blacklist *",
            placeholder="Contoh: Kandidat sudah diperbaiki, kesalahan input, dll.",
            height=150,
            key="reason_unblacklist"
        )

        st.caption("Alasan wajib diisi minimal 10 karakter.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Kirim Request", type="primary", use_container_width=True):
                if not reason or len(reason.strip()) < 10:
                    st.error("❌ Alasan wajib diisi minimal 10 karakter!")
                else:
                    try:
                        existing = db.query(BlacklistRequest).filter(
                            BlacklistRequest.sourcing_id == sourcing_id,
                            BlacklistRequest.action == "UNBLACKLIST",
                            BlacklistRequest.status == "PENDING"
                        ).first()

                        if existing:
                            st.warning("⚠️ Request un-blacklist untuk kandidat ini sudah ada dan masih PENDING.")
                        else:
                            user = get_current_user(db)
                            new_req = BlacklistRequest(
                                sourcing_id=sourcing_id,
                                kode_unik=kode_unik,
                                nama=nama,
                                posisi=posisi,
                                action="UNBLACKLIST",
                                reason=reason.strip(),
                                status="PENDING",
                                requested_by=user.id if user else None,
                                requested_by_name=user.display_name if user else "Unknown",
                                requested_at=datetime.now()
                            )
                            db.add(new_req)
                            db.commit()

                            st.success("✅ Request berhasil dikirim ke Admin!")
                            time.sleep(0.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        db.rollback()

        with col2:
            if st.button("❌ Batal", use_container_width=True):
                st.rerun()

    _dialog()


def show_blacklist_list():
    st.title("🚫 Blacklist Kandidat")
    st.markdown("Daftar kandidat yang di-blacklist. Kandidat tidak bisa diproses di FPTK baru.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)
    it_mode = is_it(db)

    if it_mode:
        st.info("🔍 Mode View-Only (IT)")

    with st.sidebar:
        st.markdown("### 🔍 Filter Blacklist")

        search = st.text_input("🔎 Cari (Nama / Kode Unik / Posisi)", placeholder="Ketik keyword...")

        pic_options = ["Semua"] + sorted(set([
            r[0] for r in db.query(DBSourcing.rekruter)
            .filter(DBSourcing.rekruter.isnot(None), DBSourcing.rekruter != "")
            .distinct().all() if r[0]
        ]))
        pic_filter = st.selectbox("PIC Recruiter", pic_options)

        reason_filter = st.text_input("Filter Alasan", placeholder="Ketik keyword alasan...")

        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()

    query = db.query(DBSourcing).filter(DBSourcing.is_blacklisted == True)

    if search:
        s = search.strip()
        query = query.filter(
            (DBSourcing.nama.ilike(f"%{s}%")) |
            (DBSourcing.kode_unik.ilike(f"%{s}%")) |
            (DBSourcing.posisi.ilike(f"%{s}%"))
        )

    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)

    if reason_filter:
        query = query.filter(DBSourcing.blacklist_reason.ilike(f"%{reason_filter}%"))

    query = query.order_by(DBSourcing.blacklisted_at.desc())
    total = query.count()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Blacklist", total)

    pending_unblacklist = db.query(BlacklistRequest).filter(
        BlacklistRequest.action == "UNBLACKLIST",
        BlacklistRequest.status == "PENDING"
    ).count()
    col2.metric("Request Un-Blacklist Pending", pending_unblacklist)

    if total > 0:
        df_all = pd.read_sql(query.statement, db.bind)
        last_30 = len(df_all[df_all['blacklisted_at'] >= (datetime.now() - pd.Timedelta(days=30))]) if 'blacklisted_at' in df_all else 0
        col3.metric("Blacklist 30 Hari Terakhir", last_30)
    else:
        col3.metric("Blacklist 30 Hari Terakhir", 0)

    st.markdown("---")

    if total == 0:
        st.info("Tidak ada kandidat blacklist dengan filter ini.")
        return

    col_export1, col_export2 = st.columns(2)
    with col_export1:
        if st.button("📥 Export CSV", use_container_width=True):
            df_export = pd.read_sql(query.statement, db.bind)
            csv = df_export.to_csv(index=False)
            st.download_button(
                "⬇️ Download CSV",
                csv,
                f"blacklist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                key="dl_blacklist_csv"
            )
    with col_export2:
        if st.button("📊 Export Excel", use_container_width=True):
            from io import BytesIO
            df_export = pd.read_sql(query.statement, db.bind)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='Blacklist', index=False)
            output.seek(0)
            st.download_button(
                "⬇️ Download Excel",
                output.getvalue(),
                f"blacklist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_blacklist_xlsx"
            )

    st.markdown("---")

    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
    offset = (page - 1) * page_size

    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)

    display_cols = ['id', 'kode_unik', 'nama', 'posisi', 'rekruter', 'email', 'nomor_hp',
                    'blacklisted_at', 'blacklist_reason']
    available_cols = [c for c in display_cols if c in df.columns]

    if 'blacklisted_at' in df.columns:
        df['blacklisted_at'] = pd.to_datetime(df['blacklisted_at'])
        df['Tgl Blacklist'] = df['blacklisted_at'].dt.strftime('%d/%m/%Y %H:%M')

    display_df = df[available_cols + (['Tgl Blacklist'] if 'Tgl Blacklist' in df.columns else [])].copy()

    rename_map = {
        'id': 'ID',
        'kode_unik': 'Kode Unik',
        'nama': 'Nama Kandidat',
        'posisi': 'Posisi',
        'rekruter': 'PIC',
        'email': 'Email',
        'nomor_hp': 'No HP',
        'blacklist_reason': 'Alasan Blacklist'
    }
    display_df = display_df.rename(columns=rename_map)

    st.dataframe(display_df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📋 Detail & Aksi")

    select_options = {}
    for _, row in df.iterrows():
        kode = row.get('kode_unik', '')
        nama = row.get('nama', '')
        display = f"{kode} | {nama[:40]}" if len(str(nama)) > 40 else f"{kode} | {nama}"
        select_options[display] = row.get('id')

    selected_display = st.selectbox("Pilih Kandidat", list(select_options.keys()))
    selected_id = select_options.get(selected_display)

    if not selected_id:
        return

    detail = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
    if not detail:
        st.error("Data tidak ditemukan.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nama:** {detail.nama}")
        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        st.markdown(f"**Posisi:** {detail.posisi or '-'}")
        st.markdown(f"**PIC:** {detail.rekruter or '-'}")
        st.markdown(f"**Email:** {detail.email or '-'}")
        st.markdown(f"**No HP:** {detail.nomor_hp or '-'}")

    with col2:
        st.markdown(f"**Tgl Blacklist:** {detail.blacklisted_at.strftime('%d/%m/%Y %H:%M') if detail.blacklisted_at else '-'}")
        st.markdown(f"**Alasan:** {detail.blacklist_reason or '-'}")
        st.markdown(f"**Blacklisted By (User ID):** {detail.blacklisted_by or '-'}")
        st.markdown(f"**Sumber Sourcing:** {detail.sumber_sourcing or '-'}")
        st.markdown(f"**Domisili:** {detail.domisili or '-'}")

    existing_request = db.query(BlacklistRequest).filter(
        BlacklistRequest.sourcing_id == selected_id,
        BlacklistRequest.action == "UNBLACKLIST",
        BlacklistRequest.status == "PENDING"
    ).first()

    st.markdown("---")
    st.markdown("### ⚙️ Aksi")

    col1, col2, col3 = st.columns(3)

    if it_mode:
        with col1:
            st.info("🔍 IT tidak bisa melakukan aksi.")
        return

    if admin:
        with col1:
            if st.button("✅ Un-Blacklist Langsung (Admin)", type="primary", use_container_width=True):
                try:
                    detail.is_blacklisted = False
                    detail.blacklisted_at = None
                    detail.blacklisted_by = None
                    detail.blacklist_reason = None
                    detail.last_updated_at = datetime.now()
                    detail.last_compile_action = "UNBLACKLIST_ADMIN"
                    db.commit()

                    st.cache_data.clear()
                    st.success(f"✅ Kandidat {detail.nama} berhasil di-un-blacklist!")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()

        with col2:
            if existing_request:
                st.warning(f"📩 Pending request dari {existing_request.requested_by_name}")
            else:
                st.caption("Tidak ada request pending")

        with col3:
            all_reqs = db.query(BlacklistRequest).filter(
                BlacklistRequest.sourcing_id == selected_id
            ).order_by(BlacklistRequest.requested_at.desc()).all()

            if all_reqs:
                with st.expander(f"📋 History Request ({len(all_reqs)})"):
                    for req in all_reqs:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.action} - {req.status}**")
                        st.caption(f"By: {req.requested_by_name} - {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")
                        st.caption(f"Alasan: {req.reason}")
                        if req.admin_notes:
                            st.caption(f"Admin: {req.admin_notes}")
                        st.markdown("---")

    else:
        with col1:
            if existing_request:
                st.info(f"📩 Request Anda PENDING - {existing_request.requested_at.strftime('%d/%m/%Y %H:%M')}")
            else:
                if st.button("📩 Request Un-Blacklist ke Admin", type="primary", use_container_width=True):
                    request_unblacklist_dialog(db, detail.id, detail.kode_unik, detail.nama, detail.posisi)

        with col2:
            all_reqs = db.query(BlacklistRequest).filter(
                BlacklistRequest.sourcing_id == selected_id,
                BlacklistRequest.requested_by == user.id
            ).order_by(BlacklistRequest.requested_at.desc()).all()

            if all_reqs:
                st.caption(f"📋 Total {len(all_reqs)} request Anda")

        with col3:
            if all_reqs:
                with st.expander("📋 History Request Anda"):
                    for req in all_reqs:
                        emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(req.status, "❓")
                        st.markdown(f"{emoji} **{req.status}** - {req.requested_at.strftime('%d/%m/%Y %H:%M') if req.requested_at else '-'}")
                        st.caption(f"Alasan: {req.reason}")
                        if req.status == "REJECTED" and req.admin_notes:
                            st.caption(f"Admin Notes: {req.admin_notes}")
                        st.markdown("---")


if __name__ == "__main__":
    show_blacklist_list()
