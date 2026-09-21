# pages/monitoring_sourcing.py
import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, FPTK, User, Evidence
from core.auth import get_current_user, is_admin, is_it, is_editor
from datetime import datetime, timedelta
import time
import base64
import os


@st.cache_resource(ttl=3600)
def get_pic_options_monitoring(_db):
    try:
        pic_list = ["Semua"] + [u[0] for u in _db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        return pic_list
    except Exception:
        return ["Semua"]


@st.cache_resource(ttl=300)
def get_monitoring_data(_db, week_start, week_end, pic_filter, kode_filter):
    try:
        query = _db.query(DBSourcing).filter(
            DBSourcing.sourcing_date >= week_start,
            DBSourcing.sourcing_date <= week_end
        )
        if pic_filter != "Semua":
            query = query.filter(DBSourcing.rekruter == pic_filter)
        if kode_filter:
            query = query.filter(DBSourcing.kode_unik.ilike(f"%{kode_filter}%"))
        df = pd.read_sql(query.statement, _db.bind)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_resource(ttl=300)
def get_fptk_data(_db, kode_unik_list):
    if not kode_unik_list:
        return pd.DataFrame()
    try:
        query = _db.query(FPTK).filter(FPTK.kode_unik.in_(kode_unik_list))
        df = pd.read_sql(query.statement, _db.bind)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_resource(ttl=300)
def get_evidence_data(_db, kode_unik_list):
    if not kode_unik_list:
        return pd.DataFrame()
    try:
        query = _db.query(Evidence).filter(Evidence.kode_unik.in_(kode_unik_list))
        df = pd.read_sql(query.statement, _db.bind)
        return df
    except Exception:
        return pd.DataFrame()


def check_column_exists(table, column_name, db):
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        columns = [c['name'] for c in inspector.get_columns(table)]
        return column_name in columns
    except Exception:
        return False


def save_cv_attachments(db, sourcing_id, kode_unik, nama_kandidat, uploaded_files, user):
    from core.models import CVAttachment
    saved = 0
    errors = []
    for f in uploaded_files:
        try:
            file_bytes = f.getvalue()
            size_mb = len(file_bytes) / (1024 * 1024)
            if size_mb > 10:
                errors.append(f"{f.name}: melebihi 10 MB")
                continue
            file_b64 = base64.b64encode(file_bytes).decode('utf-8')
            new_cv = CVAttachment(
                sourcing_id=sourcing_id, kode_unik=kode_unik,
                nama_kandidat=nama_kandidat, file_name=f.name,
                file_data=file_b64, file_size=len(file_bytes),
                file_type=f.type or "application/octet-stream",
                uploaded_by=user.id,
                uploaded_by_name=user.display_name or user.username,
                created_at=datetime.now()
            )
            db.add(new_cv)
            db.commit()
            saved += 1
        except Exception as e:
            errors.append(f"{f.name}: {str(e)}")
            db.rollback()
    return saved, errors


def show_monitoring_sourcing():
    st.title("📊 Monitoring & Evidence")
    st.markdown("Monitoring aktivitas sourcing & upload evidence.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)
    it_mode = is_it(db)
    editor_mode = is_editor(db)

    tab1, tab2 = st.tabs(["📈 Monitoring Sourcing", "📎 Upload Evidence"])

    with tab1:
        render_monitoring_tab(db, user, admin)

    with tab2:
        if it_mode:
            st.info("🔍 Mode View-Only (IT) - Anda hanya bisa melihat evidence.")
            render_evidence_histori_only(db, admin)
        elif not editor_mode:
            st.error("❌ Anda tidak memiliki akses untuk upload evidence.")
        else:
            render_evidence_tab(db, user, admin)


# ============================================================
# TAB 1: MONITORING SOURCING
# ============================================================

def render_monitoring_tab(db, user, admin):
    with st.spinner("📋 Memuat data..."):
        pic_list = get_pic_options_monitoring(db)

    with st.sidebar:
        st.markdown("### 🔍 Filter Monitoring")

        today = datetime.now().date()
        week_options = []
        for i in range(12):
            week_start = today - timedelta(days=today.weekday() + i * 7)
            week_end = week_start + timedelta(days=6)
            week_options.append((week_start, week_end))

        selected_week = st.selectbox(
            "Pilih Minggu", range(len(week_options)),
            format_func=lambda x: f"{week_options[x][0].strftime('%d/%m/%Y')} - {week_options[x][1].strftime('%d/%m/%Y')}",
            key="mon_week"
        )

        pic_filter = st.selectbox("PIC Recruiter", pic_list, key="mon_pic")
        kode_filter = st.text_input("Filter Kode Unik (opsional)", placeholder="Masukkan Kode Unik...", key="mon_kode")

        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True, key="mon_refresh"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    week_start, week_end = week_options[selected_week]

    with st.spinner("📊 Memuat data..."):
        df = get_monitoring_data(db, week_start, week_end, pic_filter, kode_filter)
        kode_unik_list = df['kode_unik'].dropna().unique().tolist()
        fptk_df = get_fptk_data(db, kode_unik_list) if kode_unik_list else pd.DataFrame()
        evidence_df = get_evidence_data(db, kode_unik_list) if kode_unik_list else pd.DataFrame()

    total = len(df)

    st.subheader(f"📅 Minggu: {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total CV", total)
    col2.metric("Unique Kode Unik", df['kode_unik'].nunique() if 'kode_unik' in df else 0)
    col3.metric("Unique Posisi", df['posisi'].nunique() if 'posisi' in df else 0)
    col4.metric("Unique Nama", df['nama'].nunique() if 'nama' in df else 0)

    if total > 0 and 'sourcing_date' in df:
        daily_avg = df.groupby(df['sourcing_date']).size().mean()
        col5.metric("Rata-rata CV/hari", f"{daily_avg:.1f}")

    st.markdown("---")

    if total > 0 and 'sourcing_date' in df:
        col1, col2 = st.columns(2)

        with col1:
            df['date'] = pd.to_datetime(df['sourcing_date'])
            daily = df.groupby(df['date'].dt.date).size().reset_index()
            daily.columns = ['Tanggal', 'Jumlah']
            all_dates = pd.date_range(week_start, week_end)
            daily_full = pd.DataFrame({'Tanggal': all_dates})
            daily_full['Tanggal'] = daily_full['Tanggal'].dt.date
            daily_full = daily_full.merge(daily, on='Tanggal', how='left').fillna(0)
            daily_full['Jumlah'] = daily_full['Jumlah'].astype(int)

            fig = px.bar(daily_full, x='Tanggal', y='Jumlah', title='📊 CV per Hari', text='Jumlah',
                         color='Jumlah', color_continuous_scale='Blues')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if 'rekruter' in df and df['rekruter'].notna().any():
                pic_counts = df['rekruter'].value_counts().reset_index()
                pic_counts.columns = ['PIC', 'Jumlah']
                fig = px.pie(pic_counts, values='Jumlah', names='PIC', title='👤 Distribusi per PIC')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Monitoring Sourcing per Kode Unik")

    if total > 0:
        grouped = df.groupby('kode_unik')
        tanggal_list = [(week_start + timedelta(days=i)) for i in range(7)]

        table_data = []
        evidence_map = {}

        for kode_unik, group in grouped:
            row = {
                'kode_unik': kode_unik,
                'posisi': group.iloc[0].get('posisi', '-'),
                'pic_recruiter': group.iloc[0].get('rekruter', '-'),
                'total_cv': len(group)
            }

            fptk_row = fptk_df[fptk_df['kode_unik'] == kode_unik] if not fptk_df.empty else pd.DataFrame()
            if not fptk_row.empty:
                row['fptk_date_real'] = fptk_row.iloc[0].get('fptk_date_real', '-')
                row['status_fptk'] = fptk_row.iloc[0].get('status', '-')
                row['filter_kategorisasi'] = fptk_row.iloc[0].get('filter_kategorisasi_fptk', '-')
                row['level_fptk'] = fptk_row.iloc[0].get('level_fptk', '-')
            else:
                row['fptk_date_real'] = '-'
                row['status_fptk'] = '-'
                row['filter_kategorisasi'] = '-'
                row['level_fptk'] = '-'

            for tgl in tanggal_list:
                count = len(group[group['sourcing_date'] == tgl])
                row[tgl.strftime('%Y-%m-%d')] = count

            row['total_minggu'] = len(group)

            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                if not evidence_df.empty:
                    ev_rows = evidence_df[
                        (evidence_df['kode_unik'] == kode_unik) &
                        (evidence_df['tanggal'] == tgl)
                    ]
                    if not ev_rows.empty:
                        can_view = admin
                        if not can_view:
                            for _, ev in ev_rows.iterrows():
                                if ev.get('pic_recruiter') == user.pic_recruiter:
                                    can_view = True
                                    break
                        ev_ids = ev_rows['id'].tolist()
                        row[f'ev_{tgl_str}'] = {'count': len(ev_rows), 'can_view': can_view, 'ids': ev_ids}
                        evidence_map[f"{kode_unik}_{tgl_str}"] = ev_ids
                    else:
                        row[f'ev_{tgl_str}'] = None
                else:
                    row[f'ev_{tgl_str}'] = None

            table_data.append(row)

        display_rows = []
        for row in table_data:
            display_row = {}
            display_row['fptk_date_real'] = row['fptk_date_real']
            display_row['kode_unik'] = row['kode_unik']
            display_row['posisi'] = row['posisi']
            display_row['pic_recruiter'] = row['pic_recruiter']
            display_row['status_fptk'] = row['status_fptk']
            display_row['filter_kategorisasi'] = row['filter_kategorisasi']

            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                display_row[tgl_str] = row.get(tgl_str, 0)

            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                ev_key = f'ev_{tgl_str}'
                ev_data = row.get(ev_key)
                if ev_data and ev_data.get('count', 0) > 0:
                    if ev_data.get('can_view', False):
                        display_row[f'ev_{tgl_str}'] = f"📎 {ev_data['count']}"
                    else:
                        display_row[f'ev_{tgl_str}'] = f"🔒 {ev_data['count']}"
                else:
                    display_row[f'ev_{tgl_str}'] = '-'

            display_row['total_minggu'] = row['total_minggu']
            display_rows.append(display_row)

        display_df = pd.DataFrame(display_rows)

        kolom_utama = ['fptk_date_real', 'kode_unik', 'posisi', 'pic_recruiter', 'status_fptk', 'filter_kategorisasi']
        kolom_tanggal = [tgl.strftime('%Y-%m-%d') for tgl in tanggal_list]
        kolom_ev = [f'ev_{tgl.strftime("%Y-%m-%d")}' for tgl in tanggal_list]
        kolom_total = ['total_minggu']

        final_columns = []
        final_columns.extend(kolom_utama)
        for i, tgl in enumerate(kolom_tanggal):
            final_columns.append(tgl)
            if i < len(kolom_ev):
                final_columns.append(kolom_ev[i])
        final_columns.extend(kolom_total)

        available_cols = [c for c in final_columns if c in display_df.columns]
        display_df = display_df[available_cols]

        if 'fptk_date_real' in display_df.columns:
            display_df['fptk_date_real'] = display_df['fptk_date_real'].apply(
                lambda x: x.strftime('%d/%m/%y') if isinstance(x, pd.Timestamp) else (x if x != '-' else '-')
            )

        rename_map = {
            'fptk_date_real': 'FPTK Date (Real)', 'kode_unik': 'Kode Unik', 'posisi': 'Posisi',
            'pic_recruiter': 'PIC Recruiter', 'status_fptk': 'Status FPTK',
            'filter_kategorisasi': 'Filter Kategorisasi FPTK', 'total_minggu': 'Total Week'
        }

        hari_indonesia = {0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'}
        for tgl in tanggal_list:
            tgl_str = tgl.strftime('%Y-%m-%d')
            hari = hari_indonesia[tgl.weekday()]
            tgl_display = f"{hari} {tgl.strftime('%d/%m/%y')}"
            rename_map[tgl_str] = tgl_display
            rename_map[f'ev_{tgl_str}'] = f'Evidence {tgl.strftime("%d/%m")}'

        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})

        st.dataframe(display_df, use_container_width=True, height=500, hide_index=True)

        st.markdown("---")
        st.markdown("### 📎 Evidence Viewer")
        st.caption("Cari evidence berdasarkan Kode Unik atau Posisi")

        search_options = {}
        for _, row in display_df.iterrows():
            kode = row['Kode Unik']
            posisi = row['Posisi']
            display = f"{kode} | {posisi[:50]}..." if len(posisi) > 50 else f"{kode} | {posisi}"
            search_options[display] = kode

        col1, col2 = st.columns([2, 1])

        with col1:
            selected_display = st.selectbox("Cari Kode Unik / Posisi", list(search_options.keys()), key="ev_search_select")
            selected_kode = search_options[selected_display] if selected_display else None

        with col2:
            if selected_kode:
                tanggal_options = []
                for tgl in tanggal_list:
                    key = f"{selected_kode}_{tgl.strftime('%Y-%m-%d')}"
                    if key in evidence_map and evidence_map[key]:
                        tanggal_options.append(tgl)

                if tanggal_options:
                    selected_tanggal = st.selectbox(
                        "Pilih Tanggal", tanggal_options,
                        format_func=lambda x: f"{hari_indonesia[x.weekday()]} {x.strftime('%d/%m/%Y')}",
                        key="ev_tanggal_search"
                    )
                else:
                    st.info("Tidak ada evidence untuk kode unik ini")
                    selected_tanggal = None
            else:
                selected_tanggal = None
                st.info("Pilih Kode Unik terlebih dahulu")

        if selected_kode and selected_tanggal:
            key = f"{selected_kode}_{selected_tanggal.strftime('%Y-%m-%d')}"
            if key in evidence_map and evidence_map[key]:
                ev_ids = evidence_map[key]
                can_view = admin
                if not can_view:
                    for ev_id in ev_ids:
                        ev = db.query(Evidence).filter(Evidence.id == ev_id).first()
                        if ev and ev.pic_recruiter == user.pic_recruiter:
                            can_view = True
                            break

                if can_view:
                    st.markdown(f"### 📎 Evidence untuk {selected_kode} - {selected_tanggal.strftime('%d/%m/%Y')}")
                    for ev_id in ev_ids:
                        ev = db.query(Evidence).filter(Evidence.id == ev_id).first()
                        if ev:
                            with st.expander(f"📄 {ev.file_name} | CV: {ev.total_cv} | PIC: {ev.pic_recruiter}", expanded=True):
                                if hasattr(ev, 'file_data') and ev.file_data:
                                    try:
                                        image_data = base64.b64decode(ev.file_data)
                                        file_lower = ev.file_name.lower()
                                        if file_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                            st.image(image_data, caption=ev.file_name, use_container_width=True)
                                        else:
                                            st.info(f"📄 File {ev.file_name} - klik Download")
                                        st.download_button("⬇️ Download File", image_data, ev.file_name,
                                            mime="application/octet-stream", key=f"download_ev_{ev_id}")
                                    except Exception as e:
                                        st.error(f"Error menampilkan gambar: {str(e)}")
                                elif ev.file_path and os.path.exists(ev.file_path):
                                    with open(ev.file_path, "rb") as f:
                                        file_data = f.read()
                                    ext = ev.file_name.split('.')[-1].lower() if ev.file_name else ''
                                    if ext in ['jpg', 'jpeg', 'png', 'gif']:
                                        st.image(file_data, caption=ev.file_name, use_container_width=True)
                                    else:
                                        st.info(f"📄 File {ext.upper()} - Klik download")
                                    st.download_button("⬇️ Download File", file_data, ev.file_name,
                                        mime="application/octet-stream", key=f"download_path_{ev_id}")
                                else:
                                    st.info("💡 File tidak ditemukan di server")
                else:
                    st.warning("🔒 Evidence ini hanya bisa dilihat oleh PIC yang upload atau Admin")
            else:
                st.info("Tidak ada evidence untuk tanggal ini")

        st.markdown("---")
        st.markdown("### 📌 Legend")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("📎 = Evidence tersedia")
        with col2:
            st.markdown("🔒 = Evidence terkunci")
        with col3:
            st.markdown("- = Tidak ada evidence")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export CSV", use_container_width=True, key="mon_export"):
                csv = display_df.to_csv(index=False)
                st.download_button("⬇️ Download CSV", csv,
                    f"monitoring_{week_start.strftime('%Y%m%d')}.csv", "text/csv")
        with col2:
            if st.button("🔄 Refresh Cache", use_container_width=True, key="mon_refresh_cache"):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Cache cleared!")
                st.rerun()
    else:
        st.info("Tidak ada data untuk periode yang dipilih.")


# ============================================================
# TAB 2: UPLOAD EVIDENCE
# ============================================================

def render_evidence_tab(db, user, admin):
    st.subheader("📤 Upload Evidence Baru")

    has_file_data = check_column_exists('evidences', 'file_data', db)
    has_keterangan = check_column_exists('evidences', 'keterangan', db)

    if not has_file_data:
        st.warning("⚠️ Kolom 'file_data' belum ada. File tidak akan disimpan di database.")
    if not has_keterangan:
        st.warning("⚠️ Kolom 'keterangan' belum ada.")

    sourcing_data = db.query(DBSourcing.kode_unik, DBSourcing.posisi).filter(
        DBSourcing.kode_unik.isnot(None)
    ).distinct().all()

    if not sourcing_data:
        st.warning("Belum ada data sourcing dengan Kode Unik.")
        return

    posisi_options = {}
    for s in sourcing_data:
        if s.posisi:
            key = f"{s.posisi[:50]} | {s.kode_unik}"
            posisi_options[key] = s.kode_unik

    selected = st.selectbox("Pilih Posisi / Kode Unik", list(posisi_options.keys()), key="ev_upload_posisi")
    kode_unik = posisi_options[selected]
    posisi_text = selected.split(" | ")[0]

    tanggal = st.date_input("Tanggal Evidence", datetime.now(), key="ev_upload_tanggal")

    auto_count = db.query(DBSourcing).filter(
        DBSourcing.kode_unik == kode_unik,
        DBSourcing.sourcing_date == tanggal
    ).count()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**Jumlah CV yang dikirim ke user hari ini**")
        st.caption(f"ℹ️ Auto-count dari DB Sourcing: **{auto_count} CV**. Anda bisa edit manual kalau berbeda.")
        total_cv = st.number_input("Jumlah CV *", min_value=0, value=auto_count, step=1, key="ev_total_cv_input")
    with col2:
        st.metric("📊 Auto-count", auto_count)
        if total_cv != auto_count:
            st.caption("✏️ Manual override")

    keterangan = ""
    if has_keterangan:
        st.markdown("**Keterangan (opsional)**")
        keterangan = st.text_area("Keterangan", placeholder="Contoh: 15 CV yang dikirim ke user hari ini",
            height=100, key="ev_keterangan_input")

    uploaded_file = st.file_uploader("Pilih file bukti evidence (PDF, Image, Excel)",
        type=["pdf", "jpg", "jpeg", "png", "xlsx", "xlsm"], key="ev_upload_file")

    if uploaded_file:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")

        if st.button("💾 Upload Evidence", type="primary", key="btn_upload_ev"):
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            clean_posisi = posisi_text.replace(" ", "_").replace("/", "_")[:40]
            safe_name = f"{tanggal.strftime('%Y-%m-%d')}_{clean_posisi}_{total_cv}_CV.{file_name.split('.')[-1]}"

            try:
                file_data_b64 = None
                if has_file_data:
                    file_data_b64 = base64.b64encode(file_bytes).decode('utf-8')

                new_evidence = Evidence(
                    kode_unik=kode_unik, posisi=posisi_text, tanggal=tanggal,
                    file_name=safe_name, file_path=f"evidence/{safe_name}",
                    file_size=len(file_bytes), total_cv=total_cv,
                    pic_recruiter=user.pic_recruiter or user.username,
                    user_id=user.id, created_at=datetime.now()
                )
                if has_file_data:
                    new_evidence.file_data = file_data_b64
                if has_keterangan and keterangan:
                    new_evidence.keterangan = keterangan.strip()

                db.add(new_evidence)
                db.commit()

                st.success("✅ Evidence berhasil direkam!")
                st.info(f"📋 Nama file: {safe_name}")
                st.info(f"📋 Total CV: {total_cv}")
                if keterangan:
                    st.info(f"📋 Keterangan: {keterangan}")

                st.download_button("📥 Download File", file_bytes, safe_name, uploaded_file.type)
                st.balloons()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()

    st.markdown("---")
    st.subheader("📋 Histori Evidence")

    pic_list = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]

    col1, col2 = st.columns(2)
    with col1:
        pic_filter = st.selectbox("Filter PIC", ["Semua"] + pic_list, key="ev_hist_pic")
    with col2:
        search_filter = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...", key="ev_hist_search")

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
                "ID": e.id, "Kode Unik": e.kode_unik,
                "Posisi": e.posisi[:40] + "..." if len(e.posisi or "") > 40 else e.posisi,
                "Tanggal": e.tanggal.strftime("%d/%m/%Y") if e.tanggal else "-",
                "File": e.file_name, "CV": e.total_cv,
                "PIC": e.pic_recruiter,
                "Upload": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "-"
            }
            if has_keterangan:
                row["Keterangan"] = (e.keterangan or "")[:50] + "..." if e.keterangan and len(e.keterangan) > 50 else (e.keterangan or "-")
            data.append(row)

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)

        if st.button("📥 Export CSV", use_container_width=True, key="ev_hist_export"):
            csv = df.to_csv(index=False)
            st.download_button("⬇️ Download CSV", csv, f"evidence_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

        st.markdown("---")
        st.subheader("🔍 Detail Evidence")

        selected_id = st.selectbox("Pilih ID untuk lihat detail", [e.id for e in evidences], key="ev_detail_select")
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

                if has_keterangan and detail.keterangan:
                    st.markdown("---")
                    st.markdown("### 📝 Keterangan")
                    st.info(detail.keterangan)

                st.markdown("---")
                st.markdown("### 📎 File Evidence")

                if has_file_data and hasattr(detail, 'file_data') and detail.file_data:
                    try:
                        image_data = base64.b64decode(detail.file_data)
                        file_lower = detail.file_name.lower()
                        if file_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                            st.image(image_data, caption=detail.file_name, use_container_width=True)
                        else:
                            st.info(f"📄 File {detail.file_name} - klik Download")

                        st.download_button("📥 Download File", image_data, detail.file_name,
                            mime="application/octet-stream", key=f"dl_ev_detail_{detail.id}")
                    except Exception as e:
                        st.error(f"Error menampilkan gambar: {str(e)}")
                else:
                    st.info("💡 File tidak ditemukan di database")

                if admin:
                    st.markdown("---")
                    col_edit1, col_edit2 = st.columns(2)

                    with col_edit1:
                        with st.expander("✏️ Edit Total CV & Keterangan"):
                            with st.form(f"edit_evidence_{detail.id}"):
                                new_total = st.number_input("Total CV", min_value=0, value=detail.total_cv or 0, step=1)
                                new_ket = detail.keterangan if has_keterangan and detail.keterangan else ""
                                if has_keterangan:
                                    new_ket = st.text_area("Keterangan", value=new_ket, height=100)

                                if st.form_submit_button("💾 Simpan", type="primary"):
                                    try:
                                        detail.total_cv = new_total
                                        if has_keterangan:
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
                                db.delete(detail)
                                db.commit()
                                st.success("Data berhasil dihapus!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()
    else:
        st.info("Belum ada evidence yang diupload.")


def render_evidence_histori_only(db, admin):
    st.subheader("📋 Histori Evidence (View-Only)")

    pic_list = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]

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
            "ID": e.id, "Kode Unik": e.kode_unik,
            "Posisi": e.posisi[:40] + "..." if len(e.posisi or "") > 40 else e.posisi,
            "Tanggal": e.tanggal.strftime("%d/%m/%Y") if e.tanggal else "-",
            "File": e.file_name, "CV": e.total_cv,
            "PIC": e.pic_recruiter,
            "Upload": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "-"
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400)


if __name__ == "__main__":
    show_monitoring_sourcing()
