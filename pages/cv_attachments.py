# pages/cv_attachments.py
import streamlit as st
import pandas as pd
import base64
from core.database import get_db
from core.models import DBSourcing, CVAttachment
from core.auth import get_current_user, is_admin, is_it
from datetime import datetime
import time


MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "jpg", "jpeg", "png", "xlsx", "xlsm", "ppt", "pptx", "txt"]


def format_file_size(size_bytes):
    if not size_bytes:
        return "-"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def show_cv_attachments():
    st.title("📎 Lampiran CV Kandidat")
    st.markdown("Upload dan lihat CV kandidat yang sudah diproses.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)
    it_mode = is_it(db)

    if it_mode:
        st.info("🔍 Mode View-Only (IT) - Anda hanya bisa melihat dan download.")

    tab1, tab2 = st.tabs(["📤 Upload CV", "📂 Daftar & Lihat CV"])

    with tab1:
        if it_mode:
            st.warning("🔍 IT tidak bisa upload CV.")
        else:
            show_upload_cv(db, user, admin)

    with tab2:
        show_list_cv(db, user, admin, it_mode)


def show_upload_cv(db, user, admin):
    st.subheader("Upload CV Kandidat")

    query = db.query(DBSourcing).order_by(DBSourcing.sourcing_date.desc())

    if not admin:
        query = query.filter(DBSourcing.rekruter == user.pic_recruiter)

    all_candidates = query.limit(1000).all()

    if not all_candidates:
        st.warning("Belum ada kandidat di DB Sourcing.")
        return

    search = st.text_input("🔎 Cari Kandidat (Nama / Kode Unik)", placeholder="Ketik keyword...")

    if search:
        s = search.strip().lower()
        all_candidates = [c for c in all_candidates if s in (c.nama or "").lower() or s in (c.kode_unik or "").lower()]

    if not all_candidates:
        st.info("Tidak ada kandidat yang cocok.")
        return

    cand_options = {}
    for c in all_candidates:
        display = f"{c.kode_unik} | {c.nama} | {c.posisi or '-'}"
        cand_options[display] = c.id

    selected_display = st.selectbox("Pilih Kandidat", list(cand_options.keys()))
    selected_id = cand_options.get(selected_display)

    if not selected_id:
        return

    candidate = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
    if not candidate:
        st.error("Kandidat tidak ditemukan.")
        return

    st.info(f"📋 **{candidate.nama}** | Kode Unik: {candidate.kode_unik} | Posisi: {candidate.posisi or '-'}")

    existing_cvs = db.query(CVAttachment).filter(
        CVAttachment.sourcing_id == selected_id
    ).all()

    if existing_cvs:
        st.markdown(f"**Sudah ada {len(existing_cvs)} CV terlampir:**")
        for cv in existing_cvs:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"📄 **{cv.file_name}** ({format_file_size(cv.file_size)})")
                st.caption(f"Upload: {cv.created_at.strftime('%d/%m/%Y %H:%M')} oleh {cv.uploaded_by_name or '-'}")
            with col2:
                try:
                    file_bytes = base64.b64decode(cv.file_data)
                    st.download_button(
                        "⬇️ Download",
                        file_bytes,
                        cv.file_name,
                        mime=cv.file_type or "application/octet-stream",
                        key=f"dl_existing_{cv.id}",
                        use_container_width=True
                    )
                except Exception:
                    st.caption("Error decode")
            with col3:
                if admin:
                    if st.button("🗑️ Hapus", key=f"del_cv_{cv.id}", use_container_width=True):
                        try:
                            db.delete(cv)
                            db.commit()
                            st.success("CV dihapus!")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            db.rollback()
        st.markdown("---")

    st.markdown("### Upload CV Baru")
    st.caption(f"Max {MAX_FILE_SIZE_MB} MB per file. Format: {', '.join(ALLOWED_EXTENSIONS)}. Bisa multiple.")

    uploaded_files = st.file_uploader(
        "Pilih file CV",
        type=ALLOWED_EXTENSIONS,
        accept_multiple_files=True,
        key="cv_uploader"
    )

    if uploaded_files:
        st.markdown(f"**{len(uploaded_files)} file dipilih:**")
        valid_files = []
        for f in uploaded_files:
            size_mb = f.size / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                st.error(f"❌ {f.name} ({size_mb:.1f} MB) melebihi batas {MAX_FILE_SIZE_MB} MB")
            else:
                st.markdown(f"✅ {f.name} ({format_file_size(f.size)})")
                valid_files.append(f)

        if valid_files and st.button(f"📤 Upload {len(valid_files)} File", type="primary"):
            success_count = 0
            error_count = 0

            for f in valid_files:
                try:
                    file_bytes = f.getvalue()
                    file_b64 = base64.b64encode(file_bytes).decode('utf-8')

                    new_cv = CVAttachment(
                        sourcing_id=selected_id,
                        kode_unik=candidate.kode_unik,
                        nama_kandidat=candidate.nama,
                        file_name=f.name,
                        file_data=file_b64,
                        file_size=len(file_bytes),
                        file_type=f.type or "application/octet-stream",
                        uploaded_by=user.id,
                        uploaded_by_name=user.display_name or user.username,
                        created_at=datetime.now()
                    )
                    db.add(new_cv)
                    db.commit()
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    db.rollback()
                    st.error(f"❌ {f.name}: {str(e)}")

            st.success(f"✅ Berhasil upload {success_count} file!")
            if error_count > 0:
                st.warning(f"⚠️ Gagal: {error_count} file")
            st.balloons()
            time.sleep(1)
            st.rerun()


def show_list_cv(db, user, admin, it_mode):
    st.subheader("Daftar CV Kandidat")

    with st.sidebar:
        st.markdown("### 🔍 Filter")

        search_cv = st.text_input("Cari (Nama / Kode Unik / File)", placeholder="Ketik keyword...", key="search_cv")

        pic_options = ["Semua"] + sorted(set([
            r[0] for r in db.query(DBSourcing.rekruter)
            .filter(DBSourcing.rekruter.isnot(None), DBSourcing.rekruter != "")
            .distinct().all() if r[0]
        ]))
        pic_filter = st.selectbox("PIC Recruiter", pic_options, key="pic_filter_cv")

        uploaded_by_filter = st.text_input("Filter Upload By", placeholder="Nama uploader...", key="uploader_filter")

        if st.button("🔄 Reset Filter", use_container_width=True, key="reset_cv_filter"):
            st.rerun()

    query = db.query(CVAttachment).order_by(CVAttachment.created_at.desc())

    if search_cv:
        s = search_cv.strip()
        query = query.filter(
            (CVAttachment.nama_kandidat.ilike(f"%{s}%")) |
            (CVAttachment.kode_unik.ilike(f"%{s}%")) |
            (CVAttachment.file_name.ilike(f"%{s}%"))
        )

    if uploaded_by_filter:
        query = query.filter(CVAttachment.uploaded_by_name.ilike(f"%{uploaded_by_filter}%"))

    if pic_filter != "Semua":
        kode_list = [r[0] for r in db.query(DBSourcing.kode_unik).filter(
            DBSourcing.rekruter == pic_filter
        ).distinct().all() if r[0]]
        query = query.filter(CVAttachment.kode_unik.in_(kode_list))

    total = query.count()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total CV", total)

    if total > 0:
        df_all = pd.read_sql(query.statement, db.bind)
        total_size = df_all['file_size'].sum() if 'file_size' in df_all else 0
        col2.metric("Total Size", format_file_size(total_size))
        unique_kandidat = df_all['nama_kandidat'].nunique() if 'nama_kandidat' in df_all else 0
        col3.metric("Kandidat dengan CV", unique_kandidat)
    else:
        col2.metric("Total Size", "0 B")
        col3.metric("Kandidat dengan CV", 0)

    st.markdown("---")

    if total == 0:
        st.info("Belum ada CV yang diupload.")
        return

    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50, key="cv_page_size")
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1, key="cv_page")
    offset = (page - 1) * page_size

    cv_list = query.limit(page_size).offset(offset).all()

    data = []
    for cv in cv_list:
        data.append({
            "ID": cv.id,
            "Nama Kandidat": cv.nama_kandidat,
            "Kode Unik": cv.kode_unik,
            "File": cv.file_name,
            "Size": format_file_size(cv.file_size),
            "Type": cv.file_type or "-",
            "Upload By": cv.uploaded_by_name or "-",
            "Tgl Upload": cv.created_at.strftime("%d/%m/%Y %H:%M") if cv.created_at else "-",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400, hide_index=True)

    st.markdown("---")
    st.markdown("### 📂 Lihat & Download CV")

    select_options = {}
    for cv in cv_list:
        display = f"#{cv.id} | {cv.nama_kandidat} | {cv.file_name}"
        select_options[display] = cv.id

    selected_display = st.selectbox("Pilih CV untuk dilihat", list(select_options.keys()), key="view_cv_select")
    selected_cv_id = select_options.get(selected_display)

    if not selected_cv_id:
        return

    cv_detail = db.query(CVAttachment).filter(CVAttachment.id == selected_cv_id).first()
    if not cv_detail:
        st.error("CV tidak ditemukan.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Kandidat:** {cv_detail.nama_kandidat}")
        st.markdown(f"**Kode Unik:** {cv_detail.kode_unik}")
        st.markdown(f"**File:** {cv_detail.file_name}")
        st.markdown(f"**Size:** {format_file_size(cv_detail.file_size)}")
        st.markdown(f"**Type:** {cv_detail.file_type or '-'}")
        st.markdown(f"**Upload By:** {cv_detail.uploaded_by_name or '-'}")
        st.markdown(f"**Tgl Upload:** {cv_detail.created_at.strftime('%d/%m/%Y %H:%M') if cv_detail.created_at else '-'}")

    with col2:
        st.markdown("**Preview / Download:**")

        try:
            file_bytes = base64.b64decode(cv_detail.file_data)

            st.download_button(
                "⬇️ Download CV",
                file_bytes,
                cv_detail.file_name,
                mime=cv_detail.file_type or "application/octet-stream",
                key=f"dl_cv_{cv_detail.id}",
                use_container_width=True
            )

            file_lower = cv_detail.file_name.lower()

            if file_lower.endswith(('.jpg', '.jpeg', '.png')):
                st.image(file_bytes, caption=cv_detail.file_name, use_container_width=True)
            elif file_lower.endswith('.pdf'):
                st.info("📄 PDF file - klik Download untuk membuka")
                b64_pdf = base64.b64encode(file_bytes).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            else:
                st.info(f"📄 File {cv_detail.file_type or 'unknown'} - klik Download untuk membuka")

        except Exception as e:
            st.error(f"Error: {str(e)}")

    if admin and not it_mode:
        st.markdown("---")
        if st.button("🗑️ Hapus CV Ini", type="secondary", key=f"del_view_cv_{cv_detail.id}"):
            try:
                db.delete(cv_detail)
                db.commit()
                st.success("CV berhasil dihapus!")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")
                db.rollback()


if __name__ == "__main__":
    show_cv_attachments()
