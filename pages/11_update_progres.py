import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from core.database import get_db
from core.models import FPTK, User, RecruitmentProgress
from core.auth import get_current_user, is_admin
from core.utils import get_filter_options_from_db
import time


# ============================================================
# HELPER: GET WEEK NUMBER
# ============================================================

def get_current_week():
    """Dapatkan ISO week number + year"""
    today = date.today()
    iso = today.isocalendar()
    return iso[1], iso[0]  # week_number, year


def get_week_label(week_num, year):
    """Format: 'Week 36, 2026'"""
    return f"Week {week_num}, {year}"


def get_week_range(week_num, year):
    """Dapatkan tanggal awal & akhir dari ISO week"""
    try:
        # ISO week: Senin = day 1
        jan4 = date(year, 1, 4)
        start_of_year_week = jan4 - timedelta(days=jan4.isoweekday() - 1)
        week_start = start_of_year_week + timedelta(weeks=week_num - 1)
        week_end = week_start + timedelta(days=6)
        return week_start, week_end
    except Exception:
        return None, None


# ============================================================
# MAIN FUNCTION
# ============================================================

def show_update_progres():
    st.title("📊 Update Progres Recruitment")
    st.markdown("Update progress rekrutmen mingguan per FPTK yang masih OP.")

    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return

    admin = is_admin(db)

    # ============================================================
    # HEADER: WEEK INFO
    # ============================================================
    current_week, current_year = get_current_week()
    week_label = get_week_label(current_week, current_year)
    week_start, week_end = get_week_range(current_week, current_year)

    col1, col2, col3 = st.columns(3)
    col1.metric("📅 Week Ini", week_label)
    if week_start and week_end:
        col2.metric("📆 Periode", f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m/%Y')}")
    col3.metric("👤 Login Sebagai", user.display_name or user.username)

    st.markdown("---")

    # ============================================================
    # LOAD FILTER OPTIONS
    # ============================================================
    filter_opts = get_filter_options_from_db()

    # ============================================================
    # SIDEBAR FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter FPTK")

        # Search
        search = st.text_input("🔎 Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")

        # PIC Filter (DINAMIS)
        pic_options = ["Semua"] + filter_opts.get("pic_options", [])
        # Kalau bukan admin, default ke PIC sendiri
        default_pic_idx = 0
        if not admin and user.pic_recruiter in pic_options:
            default_pic_idx = pic_options.index(user.pic_recruiter)
        pic_filter = st.selectbox("PIC Recruiter", pic_options, index=default_pic_idx)

        # BU Filter (DINAMIS)
        bu_options = ["Semua"] + filter_opts.get("bu_options", [])
        bu_filter = st.selectbox("Business Unit", bu_options)

        # Direktorat Filter (DINAMIS)
        dir_options = ["Semua"] + filter_opts.get("direktorat_options", [])
        dir_filter = st.selectbox("Direktorat", dir_options)

        # Filter Kategorisasi (DINAMIS)
        filter_kat_options = ["Semua"] + filter_opts.get("filter_kategorisasi_options", [])
        filter_kat = st.selectbox("Filter Kategorisasi", filter_kat_options)

        # Level Filter
        level_options = ["Semua", "1A", "1B", "1C", "2A", "2B", "2C",
                         "3A", "3B", "3C", "4A", "4B", "5A", "5B"]
        level_filter = st.selectbox("Level FPTK", level_options)

        st.markdown("---")

        # Show only my data
        show_mine = st.checkbox("Hanya FPTK saya", value=not admin)

        if st.button("🔄 Refresh Filter Options", use_container_width=True):
            get_filter_options_from_db.clear()
            st.success("✅ Filter refreshed!")
            time.sleep(0.3)
            st.rerun()

        st.caption("💡 Hanya FPTK dengan status **OP** yang ditampilkan")

    # ============================================================
    # BUILD QUERY — HANYA STATUS = OP
    # ============================================================
    query = db.query(FPTK).filter(FPTK.status == "OP")

    if search:
        search_term = search.strip()
        query = query.filter(
            (FPTK.kode_unik.ilike(f"%{search_term}%")) |
            (FPTK.posisi.ilike(f"%{search_term}%"))
        )

    if pic_filter != "Semua":
        query = query.filter(FPTK.pic_recruiter == pic_filter)

    if bu_filter != "Semua":
        query = query.filter(FPTK.business_unit == bu_filter)

    if dir_filter != "Semua":
        query = query.filter(FPTK.direktorat == dir_filter)

    if filter_kat != "Semua":
        query = query.filter(FPTK.filter_kategorisasi_fptk == filter_kat)

    if level_filter != "Semua":
        query = query.filter(FPTK.level_fptk == level_filter)

    if show_mine and not admin:
        query = query.filter(FPTK.pic_recruiter == user.pic_recruiter)

    # Order by FPTK date desc
    query = query.order_by(FPTK.fptk_date_real.desc())

    total = query.count()

    # ============================================================
    # STATISTIK
    # ============================================================
    st.markdown("### 📈 Statistik")

    col1, col2, col3, col4 = st.columns(4)

    # Hitung progress yang udah diisi week ini
    existing_progress = db.query(RecruitmentProgress).filter(
        RecruitmentProgress.week_number == current_week,
        RecruitmentProgress.year == current_year
    ).all()

    progress_fptk_ids = set([p.fptk_id for p in existing_progress])
    already_updated = query.filter(FPTK.id.in_(progress_fptk_ids)).count() if progress_fptk_ids else 0
    belum_update = total - already_updated

    col1.metric("Total FPTK OP", total)
    col2.metric("✅ Sudah Update", already_updated)
    col3.metric("⏳ Belum Update", belum_update)
    col4.metric("📊 Progress", f"{(already_updated/total*100):.0f}%" if total > 0 else "0%")

    st.markdown("---")

    # ============================================================
    # TAMPILKAN TABEL FPTK
    # ============================================================
    if total == 0:
        st.info("Tidak ada FPTK dengan status **OP** yang sesuai filter.")
        return

    # Pagination
    page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
    page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
    offset = (page - 1) * page_size

    df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)

    if not df.empty:
        # Ambil progress existing untuk week ini
        fptk_ids_page = df['id'].tolist()
        progress_map = {p.fptk_id: p for p in existing_progress if p.fptk_id in fptk_ids_page}

        # Build display dataframe
        display_data = []
        for _, row in df.iterrows():
            fptk_id = row['id']
            has_progress = fptk_id in progress_map

            display_data.append({
                "ID": fptk_id,
                "Kode Unik": row.get('kode_unik', ''),
                "Posisi": row.get('posisi', '')[:60] + "..." if len(str(row.get('posisi', ''))) > 60 else row.get('posisi', ''),
                "PIC": row.get('pic_recruiter', ''),
                "BU": row.get('business_unit', '')[:30] + "..." if len(str(row.get('business_unit', ''))) > 30 else row.get('business_unit', ''),
                "Level": row.get('level_fptk', ''),
                "Status Update": "✅ Sudah" if has_progress else "⏳ Belum",
            })

        df_display = pd.DataFrame(display_data)

        st.dataframe(
            df_display,
            use_container_width=True,
            height=400,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Kode Unik": st.column_config.TextColumn("Kode Unik", width="medium"),
                "Posisi": st.column_config.TextColumn("Posisi", width="large"),
                "PIC": st.column_config.TextColumn("PIC", width="small"),
                "BU": st.column_config.TextColumn("BU", width="medium"),
                "Level": st.column_config.TextColumn("Level", width="small"),
                "Status Update": st.column_config.TextColumn("Status Update", width="small"),
            }
        )

    # ============================================================
    # FORM UPDATE PROGRES
    # ============================================================
    st.markdown("---")
    st.markdown("### ✏️ Update Progress FPTK")

    # Pilihan FPTK
    df_all = pd.read_sql(query.statement, db.bind)

    if df_all.empty:
        st.info("Tidak ada FPTK untuk diupdate.")
        return

    select_options = {}
    for _, row in df_all.iterrows():
        kode = row.get('kode_unik', '')
        posisi = row.get('posisi', '')
        display = f"{kode} | {posisi[:50]}..." if len(str(posisi)) > 50 else f"{kode} | {posisi}"
        select_options[display] = row.get('id')

    selected_display = st.selectbox(
        "Pilih FPTK (Kode Unik | Posisi)",
        list(select_options.keys())
    )
    selected_id = select_options[selected_display]

    # Load detail FPTK
    detail = db.query(FPTK).filter(FPTK.id == selected_id).first()
    if not detail:
        st.error("FPTK tidak ditemukan!")
        return

    # Cek akses
    can_edit = admin or (detail.pic_recruiter == user.pic_recruiter)
    if not can_edit:
        st.warning("⚠️ Anda hanya bisa update progress FPTK milik PIC Anda sendiri.")
        return

    # ============================================================
    # INFO FPTK
    # ============================================================
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Kode Unik:** {detail.kode_unik}")
        st.markdown(f"**Posisi:** {detail.posisi}")
    with col2:
        st.markdown(f"**PIC:** {detail.pic_recruiter}")
        st.markdown(f"**BU:** {detail.business_unit}")
    with col3:
        st.markdown(f"**Level:** {detail.level_fptk}")
        st.markdown(f"**Status:** {detail.status}")

    # ============================================================
    # LOAD EXISTING PROGRESS (kalau udah ada)
    # ============================================================
    existing = db.query(RecruitmentProgress).filter(
        RecruitmentProgress.fptk_id == selected_id,
        RecruitmentProgress.week_number == current_week,
        RecruitmentProgress.year == current_year
    ).first()

    default_progress = existing.progress_this_week if existing else ""
    default_next = existing.next_action if existing else ""

    # ============================================================
    # FORM
    # ============================================================
    with st.form(f"form_progress_{selected_id}", clear_on_submit=False):
        st.markdown(f"#### 📅 Update untuk **{week_label}**")

        if existing:
            st.info(f"✏️ Sudah ada update sebelumnya. Dibuat oleh **{existing.created_by_name}** pada {existing.created_at.strftime('%d/%m/%Y %H:%M') if existing.created_at else '-'}")

        progress_this_week = st.text_area(
            "📝 **Progress Week Ini**",
            value=default_progress,
            placeholder=(
                "Contoh:\n"
                "> Send 25 CV di Week 36\n"
                "> Shortlisted by User 9 kandidat\n"
                "> HR Interview 5 kandidat\n"
                "> 2 kandidat DROP, 3 kandidat lanjut user interview"
            ),
            height=200,
            help="Ceritakan progress recruitment untuk FPTK ini di minggu ini"
        )

        next_action = st.text_area(
            "➡️ **Next Action Week Depan**",
            value=default_next,
            placeholder=(
                "Contoh:\n"
                "> Send 10 kandidat baru di Week 37\n"
                "> Follow up hasil user interview\n"
                "> Schedule psikotes 3 kandidat\n"
                "> Approval offering 1 kandidat"
            ),
            height=150,
            help="Rencana / action yang akan dilakukan minggu depan"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            submit = st.form_submit_button("💾 Simpan Progress", type="primary", use_container_width=True)

        if submit:
            if not progress_this_week or not progress_this_week.strip():
                st.error("❌ Progress Week Ini wajib diisi!")
            elif not next_action or not next_action.strip():
                st.error("❌ Next Action Week Depan wajib diisi!")
            else:
                try:
                    if existing:
                        # Update
                        existing.progress_this_week = progress_this_week.strip()
                        existing.next_action = next_action.strip()
                        existing.updated_at = datetime.now()
                        existing.created_by = user.id
                        existing.created_by_name = user.display_name or user.username
                    else:
                        # Create new
                        new_progress = RecruitmentProgress(
                            fptk_id=selected_id,
                            kode_unik=detail.kode_unik,
                            posisi=detail.posisi,
                            pic_recruiter=detail.pic_recruiter,
                            week_number=current_week,
                            year=current_year,
                            week_label=week_label,
                            progress_this_week=progress_this_week.strip(),
                            next_action=next_action.strip(),
                            status="SUBMITTED",
                            created_by=user.id,
                            created_by_name=user.display_name or user.username
                        )
                        db.add(new_progress)

                    db.commit()

                    st.cache_data.clear()
                    st.success(f"✅ Progress berhasil disimpan untuk **{week_label}**!")
                    time.sleep(0.5)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()

    # ============================================================
    # HISTORY PROGRESS
    # ============================================================
    st.markdown("---")
    st.markdown(f"### 📜 History Progress — {detail.kode_unik}")

    history = db.query(RecruitmentProgress).filter(
        RecruitmentProgress.fptk_id == selected_id
    ).order_by(
        RecruitmentProgress.year.desc(),
        RecruitmentProgress.week_number.desc()
    ).limit(20).all()

    if not history:
        st.info("Belum ada history progress untuk FPTK ini.")
    else:
        for h in history:
            with st.expander(
                f"📅 **{h.week_label}** — Updated by {h.created_by_name} pada {h.created_at.strftime('%d/%m/%Y %H:%M') if h.created_at else '-'}",
                expanded=(h.week_number == current_week and h.year == current_year)
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**📝 Progress Week Ini:**")
                    st.info(h.progress_this_week or "-")
                with col2:
                    st.markdown("**➡️ Next Action:**")
                    st.success(h.next_action or "-")

                if admin:
                    if st.button(f"🗑️ Hapus Progress {h.week_label}", key=f"del_prog_{h.id}"):
                        try:
                            db.delete(h)
                            db.commit()
                            st.success("✅ Progress dihapus!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            db.rollback()
