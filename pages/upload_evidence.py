# pages/upload_evidence.py
import streamlit as st
import pandas as pd
import uuid
import hashlib
from core.database import get_db
from core.models import DBSourcing, FPTK, Evidence, User
from core.auth import get_current_user, is_admin, is_it, is_editor
from core.r2_storage import get_r2
from datetime import datetime


@st.cache_resource(ttl=3600)
def get_pic_options_evidence(_db):
    try:
        pic_list = ["Semua"] + [u[0] for u in _db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        return pic_list
    except Exception:
        return ["Semua"]


@st.cache_resource(ttl=300)
def get_sourcing_kode_unik(_db):
    try:
        data = _db.query(DBSourcing.kode_unik, DBSourcing.posisi).filter(
            DBSourcing.kode_unik.isnot(None)
        ).distinct().all()
        return data
    except Exception:
        return []


def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing dan lihat histori upload.")

    db = next(get_db())
    if not is_editor(db):
        st.error("❌ Anda tidak memiliki akses untuk upload evidence. Hubungi Admin.")
        return
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)
    it_mode = is_it(db)

    with st.spinner("📋 Memuat data..."):
        sourcing_data = get_sourcing_kode_unik(db)
        pic_list = get_pic_options_evidence(db)

    if not sourcing_data:
        st.warning("Belum ada data sourcing dengan Kode Unik.")
        return

    if it_mode:
        st.info("🔍 Mode View-Only (IT) - Anda hanya bisa melihat dan download.")
        show_histori_only(db, pic_list)
        return

    tab1, tab2 = st.tabs(["📤 Upload Evidence Baru", "📋 Histori Evidence"])

    with tab1:
        show_upload_form(db, user, sourcing_data)

    with tab2:
        show_histori(db, user, admin, pic_list)


def show_upload_form(db, user, sourcing_data):
    st.subheader("📤 Upload Evidence Baru")

    posisi_options = {}
    for s in sourcing_data:
        if s.posisi:
            key = f"{s.posisi[:50]} | {s.kode_unik}"
            posisi_options[key] = s.kode_unik

    selected = st.selectbox("Pilih Posisi / Kode Unik", list(posisi_options.keys()))
    kode_unik = posisi_options[selected]
    posisi_text = selected.split(" | ")[0]

    tanggal = st.date_input("Tanggal Evidence", datetime.now())

    auto_count = db.query(DBSourcing).filter(
        DBSourcing.kode_unik == kode_unik,
        DBSourcing.sourcing_date == tanggal
    ).count()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**Jumlah CV yang dikirim ke user hari ini**")
        st.caption(f"ℹ️ Auto-count dari DB Sourcing: **{auto_count} CV**. Anda bisa edit manual kalau berbeda.")

        total_cv = st.number_input(
            "Jumlah CV *",
            min_value=0,
            value=auto_count,
            step=1,
            key="evidence_total_cv_input"
        )

    with col2:
        st.metric("📊 Auto-count", auto_count)
        if total_cv != auto_count:
            st.caption("✏️ Manual override")

    st.markdown("**Keterangan (opsional)**")
    st.caption("Contoh: '15 CV dikirim ke user Bpk. Andi via email pagi ini'")
    keterangan = st.text_area(
        "Keterangan",
        placeholder="Contoh: 15 CV yang dikirim ke user hari ini",
        height=100,
        key="evidence_keterangan_input"
    )

    uploaded_file = st.file_uploader(
        "Pilih file bukti evidence (PDF, Image, Excel)",
        type=["pdf", "jpg", "jpeg", "png", "xlsx", "xlsm"]
    )

    if uploaded_file:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")

        if st.button("💾 Upload Evidence", type="primary"):
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name

            clean_posisi = posisi_text.replace(" ", "_").replace("/", "_")[:40]
            safe_name = f"{tanggal.strftime('%Y-%m-%d')}_{clean_posisi}_{total_cv}_CV.{file_name.split('.')[-1]}"

            r2_key = None
            try:
                # Upload ke R2
                ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"
                safe_kode = (kode_unik or "unknown").replace("/", "_").replace("\\", "_")
                r2_key = f"evidences/{safe_kode}/{uuid.uuid4().hex}.{ext}"

                r2 = get_r2()
                r2.upload_bytes(
                    file_bytes=file_bytes,
                    key=r2_key,
                    content_type=uploaded_file.type or "application/octet-stream",
                )

                new_evidence = Evidence(
                    kode_unik=kode_unik,
                    posisi=posisi_text,
                    tanggal=tanggal,
                    file_name=safe_name,
                    file_key=r2_key,
                    file_size=len(file_bytes),
                    total_cv=total_cv,
                    file_type=uploaded_file.type or "application/octet-stream",
                    keterangan=keterangan.strip() if keterangan else None,
                    pic_recruiter=user.pic_recruiter or user.username,
                    user_id=user.id,
                    created_at=datetime.now()
                )

                db.add(new_evidence)
                db.commit()

                st.success("✅ Evidence berhasil direkam!")
                st.info(f"📋 Nama file: {safe_name}")
                st.info(f"📋 Total CV: {total_cv}")
                if keterangan:
                    st.info(f"📋 Keterangan: {keterangan}")

                st.info("📁 File disimpan di Cloudflare R2")

                st.download_button(
                    "📥 Download File",
                    file_bytes,
                    safe_name,
                    uploaded_file.type
                )

                st.balloons()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
                # Rollback: hapus dari R2 kalau DB gagal
                if r2_key:
                    try:
                        get_r2().delete(r2_key)
                    except Exception:
                        pass


def show_histori(db, user, admin, pic_list):
    st.subheader("📋 Histori Evidence")

    col1, col2 = st.columns(2)
    with col1:
        pic_filter = st.selectbox("Filter PIC", ["Semua"] + pic_list, key="evidence_pic_filter")
    with col2:
        search_filter = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...", key="evidence_search")

    query = db.query(Evidence)
    if pic_filter != "Semua":
        query = query.filter(Evidence.pic_recruiter == pic_filter)
    if search_filter:
        query = query.filter(
            (Evidence.kode_unik.ilike(f"%{search_filter}%")) |
            (Evidence.posisi.ilike(f"%{search_filter}%"))
        )

    evidences = query.order_by(Evidence.created_at.desc()).limit(100).all()

    if evidences:
        data = []
        for e in evidences:
            row = {
                "ID": e.id,
                "Kode Unik": e.kode_unik,
                "Posisi": e.posisi[:40] + "..." if len(e.posisi or "") > 40 else e.posisi,
                "Tanggal": e.tanggal.strftime("%d/%m/%Y") if e.tanggal else "-",
                "File": e.file_name,
                "CV": e.total_cv,
                "PIC": e.pic_recruiter,
                "Upload": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "-"
            }
            row["Keterangan"] = (e.keterangan or "")[:50] + "..." if e.keterangan and len(e.keterangan) > 50 else (e.keterangan or "-")
            data.append(row)

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)

        col_export1, col_export2 = st.columns(2)
        with col_export1:
            if st.button("📥 Export CSV", use_container_width=True, key="evidence_export_csv"):
                csv = df.to_csv(index=False)
                st.download_button(
                    "⬇️ Download CSV",
                    csv,
                    f"evidence_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    key="dl_evidence_csv"
                )

        st.markdown("---")
        st.subheader("🔍 Detail Evidence")

        selected_id = st.selectbox("Pilih ID untuk lihat detail", [e.id for e in evidences], key="evidence_detail_select")
        if selected_id:
            detail = db.query(Evidence).filter(Evidence.id == selected_id).first()
            if detail:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**Posisi:** {detail.posisi}")
                with col2:
                    st.markdown(f"**Tanggal:** {detail.tanggal.strftime('%d/%m/%Y') if detail.tanggal else '-'}")
                    st.markdown(f"**Total CV:** {detail.total_cv}")
                with col3:
                    st.markdown(f"**File:** {detail.file_name}")
                    st.markdown(f"**PIC:** {detail.pic_recruiter}")

                if detail.keterangan:
                    st.markdown("---")
                    st.markdown("### 📝 Keterangan")
                    st.info(detail.keterangan)

                st.markdown("---")
                st.markdown("### 📎 File Evidence")

                if detail.file_key:
                    try:
                        r2 = get_r2()
                        url = r2.get_presigned_url(detail.file_key, expires_in=3600)
                        file_lower = detail.file_name.lower()

                        if file_lower.endswith(('.jpg', '.jpeg', '.png')):
                            st.image(url, caption=detail.file_name, use_container_width=True)
                        else:
                            st.info(f"📄 File {detail.file_name} - klik Download untuk membuka")

                        st.markdown(
                            f'<a href="{url}" target="_blank" style="text-decoration:none;">'
                            f'<button style="width:100%;padding:10px;background:#4CAF50;color:white;border:none;border-radius:4px;cursor:pointer;font-size:16px;">📥 Download File</button>'
                            f'</a>',
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        st.error(f"Error menampilkan file: {str(e)}")
                else:
                    st.info("💡 File tidak tersedia")

                if admin:
                    st.markdown("---")
                    col_edit1, col_edit2 = st.columns(2)

                    with col_edit1:
                        with st.expander("✏️ Edit Total CV & Keterangan"):
                            with st.form(f"edit_evidence_{detail.id}"):
                                new_total = st.number_input(
                                    "Total CV",
                                    min_value=0,
                                    value=detail.total_cv or 0,
                                    step=1
                                )

                                new_ket = detail.keterangan or ""
                                new_ket = st.text_area("Keterangan", value=new_ket, height=100)

                                if st.form_submit_button("💾 Simpan", type="primary"):
                                    try:
                                        detail.total_cv = new_total
                                        detail.keterangan = new_ket.strip() if new_ket else None
                                        db.commit()
                                        st.success("✅ Evidence diupdate!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                                        db.rollback()

                    with col_edit2:
                        if st.button("🗑️ Hapus Evidence", type="secondary", key=f"del_evidence_{detail.id}"):
                            try:
                                # Hapus dari R2 dulu
                                if detail.file_key:
                                    try:
                                        get_r2().delete(detail.file_key)
                                    except Exception:
                                        pass
                                db.delete(detail)
                                db.commit()
                                st.success("Data berhasil dihapus!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()
    else:
        st.info("Belum ada evidence yang diupload.")


def show_histori_only(db, pic_list):
    st.subheader("📋 Histori Evidence (View-Only)")

    col1, col2 = st.columns(2)
    with col1:
        pic_filter = st.selectbox("Filter PIC", ["Semua"] + pic_list, key="it_pic_filter")
    with col2:
        search_filter = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...", key="it_search")

    query = db.query(Evidence)
    if pic_filter != "Semua":
        query = query.filter(Evidence.pic_recruiter == pic_filter)
    if search_filter:
        query = query.filter(
            (Evidence.kode_unik.ilike(f"%{search_filter}%")) |
            (Evidence.posisi.ilike(f"%{search_filter}%"))
        )

    evidences = query.order_by(Evidence.created_at.desc()).limit(100).all()

    if not evidences:
        st.info("Belum ada evidence.")
        return

    data = []
    for e in evidences:
        data.append({
            "ID": e.id,
            "Kode Unik": e.kode_unik,
            "Posisi": e.posisi[:40] + "..." if len(e.posisi or "") > 40 else e.posisi,
            "Tanggal": e.tanggal.strftime("%d/%m/%Y") if e.tanggal else "-",
            "File": e.file_name,
            "CV": e.total_cv,
            "PIC": e.pic_recruiter,
            "Upload": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "-"
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400)


if __name__ == "__main__":
    show_upload_evidence()