import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, FPTK, User, Evidence
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import time

# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_data(ttl=3600)
def get_pic_options_monitoring(_db):
    """Mengambil opsi PIC - cache 1 jam"""
    try:
        pic_list = ["Semua"] + [u[0] for u in _db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        return pic_list
    except:
        return ["Semua"]


@st.cache_data(ttl=300)
def get_monitoring_data(_db, week_start, week_end, pic_filter, kode_filter):
    """Mengambil data monitoring - cache 5 menit"""
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
    except:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_fptk_data(_db, kode_unik_list):
    """Mengambil data FPTK berdasarkan list kode unik - cache 5 menit"""
    if not kode_unik_list:
        return pd.DataFrame()
    
    try:
        query = _db.query(FPTK).filter(FPTK.kode_unik.in_(kode_unik_list))
        df = pd.read_sql(query.statement, _db.bind)
        return df
    except:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_evidence_data(_db, kode_unik_list):
    """Mengambil data evidence berdasarkan kode unik - cache 5 menit"""
    if not kode_unik_list:
        return pd.DataFrame()
    
    try:
        query = _db.query(Evidence).filter(Evidence.kode_unik.in_(kode_unik_list))
        df = pd.read_sql(query.statement, _db.bind)
        return df
    except:
        return pd.DataFrame()


# ============================================================
# FUNGSI UTAMA
# ============================================================

def show():
    show_monitoring_sourcing()


def show_monitoring_sourcing():
    st.title("📈 Monitoring Sourcing")
    st.markdown("Monitoring aktivitas sourcing per periode dengan evidence")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        
        today = datetime.now().date()
        week_options = []
        for i in range(12):
            week_start = today - timedelta(days=today.weekday() + i*7)
            week_end = week_start + timedelta(days=6)
            week_options.append((week_start, week_end))
        
        selected_week = st.selectbox(
            "Pilih Minggu",
            range(len(week_options)),
            format_func=lambda x: f"{week_options[x][0].strftime('%d/%m/%Y')} - {week_options[x][1].strftime('%d/%m/%Y')}"
        )
        
        pic_list = get_pic_options_monitoring(db)
        pic_filter = st.selectbox("PIC Recruiter", pic_list)
        kode_filter = st.text_input("Filter Kode Unik (opsional)", placeholder="Masukkan Kode Unik...")
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ============================================================
    # GET DATA
    # ============================================================
    week_start, week_end = week_options[selected_week]
    
    with st.spinner("📊 Memuat data..."):
        df = get_monitoring_data(db, week_start, week_end, pic_filter, kode_filter)
        kode_unik_list = df['kode_unik'].dropna().unique().tolist()
        fptk_df = get_fptk_data(db, kode_unik_list) if kode_unik_list else pd.DataFrame()
        evidence_df = get_evidence_data(db, kode_unik_list) if kode_unik_list else pd.DataFrame()
    
    total = len(df)
    
    # ============================================================
    # HEADER & METRICS
    # ============================================================
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
    
    # ============================================================
    # CHARTS
    # ============================================================
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
            
            fig = px.bar(daily_full, x='Tanggal', y='Jumlah', 
                         title='📊 CV per Hari', text='Jumlah',
                         color='Jumlah', color_continuous_scale='Blues')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if 'rekruter' in df and df['rekruter'].notna().any():
                pic_counts = df['rekruter'].value_counts().reset_index()
                pic_counts.columns = ['PIC', 'Jumlah']
                fig = px.pie(pic_counts, values='Jumlah', names='PIC', 
                             title='👤 Distribusi per PIC')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ============================================================
    # 🔥🔥🔥 TABEL MONITORING DENGAN TOMBOL EVIDENCE 🔥🔥🔥
    # ============================================================
    st.subheader("📋 Monitoring Sourcing per Kode Unik")
    
    if total == 0:
        st.info("Tidak ada data untuk periode yang dipilih.")
        return
    
    # ============================================================
    # BUILD DATA
    # ============================================================
    grouped = df.groupby('kode_unik')
    tanggal_list = [(week_start + timedelta(days=i)) for i in range(7)]
    
    table_data = []
    evidence_map = {}  # Untuk menyimpan evidence per kode_unik_tanggal
    
    for kode_unik, group in grouped:
        row = {
            'kode_unik': kode_unik,
            'posisi': group.iloc[0].get('posisi', '-'),
            'pic_recruiter': group.iloc[0].get('rekruter', '-'),
        }
        
        # Data FPTK
        fptk_row = fptk_df[fptk_df['kode_unik'] == kode_unik] if not fptk_df.empty else pd.DataFrame()
        if not fptk_row.empty:
            row['fptk_date_real'] = fptk_row.iloc[0].get('fptk_date_real', '-')
            row['status_fptk'] = fptk_row.iloc[0].get('status', '-')
            row['filter_kategorisasi'] = fptk_row.iloc[0].get('filter_kategorisasi_fptk', '-')
        else:
            row['fptk_date_real'] = '-'
            row['status_fptk'] = '-'
            row['filter_kategorisasi'] = '-'
        
        # CV per tanggal
        for tgl in tanggal_list:
            count = len(group[group['sourcing_date'] == tgl])
            row[tgl.strftime('%Y-%m-%d')] = count
        
        # Evidence per tanggal
        for tgl in tanggal_list:
            tgl_str = tgl.strftime('%Y-%m-%d')
            key = f"{kode_unik}_{tgl_str}"
            
            if not evidence_df.empty:
                ev_rows = evidence_df[
                    (evidence_df['kode_unik'] == kode_unik) & 
                    (evidence_df['tanggal'] == tgl)
                ]
                if not ev_rows.empty:
                    ev = ev_rows.iloc[0]
                    can_view = admin or (ev.get('pic_recruiter') == user.pic_recruiter)
                    evidence_map[key] = {
                        'count': len(ev_rows),
                        'can_view': can_view,
                        'data': ev_rows.to_dict('records'),
                        'kode_unik': kode_unik,
                        'tanggal': tgl
                    }
                    row[f'ev_{tgl_str}'] = len(ev_rows)
                else:
                    row[f'ev_{tgl_str}'] = 0
            else:
                row[f'ev_{tgl_str}'] = 0
        
        row['total_minggu'] = len(group)
        table_data.append(row)
    
    # ============================================================
    # TAMPILKAN TABEL DENGAN TOMBOL EVIDENCE
    # ============================================================
    
    hari_indonesia = {0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'}
    
    # Buat header
    headers = ['FPTK Date', 'Kode Unik', 'Posisi', 'PIC', 'Status', 'Filter']
    for tgl in tanggal_list:
        hari = hari_indonesia[tgl.weekday()]
        headers.append(f"{hari}\n{tgl.strftime('%d/%m')}")
        headers.append(f"📎{tgl.strftime('%d/%m')}")
    headers.append('Total')
    
    # Tampilkan tabel dengan st.columns
    st.markdown("### 📋 Data Monitoring")
    
    # Scrollable container
    with st.container():
        # Header
        cols = st.columns(len(headers))
        for i, h in enumerate(headers):
            cols[i].markdown(f"**{h}**")
        
        # Data rows
        for idx, row in enumerate(table_data):
            cols = st.columns(len(headers))
            col_idx = 0
            
            # Kolom data
            cols[col_idx].write(row['fptk_date_real'] if row['fptk_date_real'] != '-' else '-')
            col_idx += 1
            cols[col_idx].write(row['kode_unik'])
            col_idx += 1
            cols[col_idx].write(row['posisi'][:25] + '...' if len(str(row['posisi'])) > 25 else row['posisi'])
            col_idx += 1
            cols[col_idx].write(row['pic_recruiter'])
            col_idx += 1
            cols[col_idx].write(row['status_fptk'])
            col_idx += 1
            cols[col_idx].write(row['filter_kategorisasi'])
            col_idx += 1
            
            # Tanggal & Evidence
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                key = f"{row['kode_unik']}_{tgl_str}"
                
                # CV count
                cols[col_idx].write(row[tgl_str])
                col_idx += 1
                
                # Evidence button
                ev_count = row[f'ev_{tgl_str}']
                if ev_count > 0 and key in evidence_map:
                    ev_info = evidence_map[key]
                    if ev_info['can_view']:
                        button_key = f"ev_{row['kode_unik']}_{tgl_str}".replace('-', '_')
                        if cols[col_idx].button(f"📎{ev_count}", key=button_key, use_container_width=True):
                            st.session_state.selected_evidence = key
                            st.rerun()
                    else:
                        cols[col_idx].write(f"🔒{ev_count}")
                else:
                    cols[col_idx].write('-')
                col_idx += 1
            
            # Total
            cols[col_idx].write(row['total_minggu'])
    
    # ============================================================
    # 🔥🔥🔥 EVIDENCE DETAIL SECTION (DI BAWAH TABEL) 🔥🔥🔥
    # ============================================================
    st.markdown("---")
    st.markdown("### 📎 Detail Evidence")
    
    selected_key = st.session_state.get('selected_evidence', None)
    
    if selected_key and selected_key in evidence_map:
        ev_info = evidence_map[selected_key]
        kode_unik = ev_info['kode_unik']
        tgl = ev_info['tanggal']
        
        st.success(f"📎 **Evidence untuk Kode Unik:** {kode_unik} | **Tanggal:** {tgl.strftime('%d/%m/%Y')}")
        
        for ev in ev_info.get('data', []):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**File:**")
            with col2:
                st.markdown(f"{ev.get('file_name', '-')}")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**Total CV:**")
            with col2:
                st.markdown(f"{ev.get('total_cv', '-')}")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**Upload oleh:**")
            with col2:
                st.markdown(f"{ev.get('pic_recruiter', '-')}")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**Tanggal Upload:**")
            with col2:
                created_at = ev.get('created_at')
                if created_at:
                    if isinstance(created_at, datetime):
                        st.markdown(f"{created_at.strftime('%d/%m/%Y %H:%M')}")
                    else:
                        st.markdown(f"{created_at}")
                else:
                    st.markdown("-")
            
            st.markdown("---")
        
        # Tombol tutup
        if st.button("❌ Tutup Detail Evidence", use_container_width=True):
            st.session_state.selected_evidence = None
            st.rerun()
    
    elif selected_key:
        st.info("Evidence tidak tersedia atau sudah dihapus.")
        if st.button("🔄 Refresh"):
            st.session_state.selected_evidence = None
            st.rerun()
    else:
        st.caption("💡 Klik tombol **📎** di tabel di atas untuk melihat detail evidence.")
    
    # ============================================================
    # LEGEND
    # ============================================================
    st.markdown("---")
    st.markdown("### 📌 Legend")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("📎 = Evidence tersedia (klik untuk lihat)")
    with col2:
        st.markdown("🔒 = Evidence terkunci (hanya PIC/Admin)")
    with col3:
        st.markdown("- = Tidak ada evidence")
    
    # ============================================================
    # EXPORT
    # ============================================================
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export CSV", use_container_width=True):
            # Buat export data
            export_rows = []
            for row in table_data:
                export_row = {
                    'FPTK Date (Real)': row['fptk_date_real'],
                    'Kode Unik': row['kode_unik'],
                    'Posisi': row['posisi'],
                    'PIC Recruiter': row['pic_recruiter'],
                    'Status FPTK': row['status_fptk'],
                    'Filter Kategorisasi': row['filter_kategorisasi'],
                }
                for tgl in tanggal_list:
                    tgl_str = tgl.strftime('%Y-%m-%d')
                    export_row[f'CV_{tgl_str}'] = row[tgl_str]
                    export_row[f'Evidence_{tgl_str}'] = row[f'ev_{tgl_str}']
                export_row['Total Week'] = row['total_minggu']
                export_rows.append(export_row)
            
            export_df = pd.DataFrame(export_rows)
            csv = export_df.to_csv(index=False)
            st.download_button(
                "⬇️ Download CSV", 
                csv, 
                f"monitoring_{week_start.strftime('%Y%m%d')}.csv", 
                "text/csv"
            )
    
    with col2:
        if st.button("🔄 Refresh Cache", use_container_width=True):
            st.cache_data.clear()
            st.session_state.selected_evidence = None
            st.success("Cache cleared!")
            st.rerun()


# Untuk kompatibilitas
if __name__ == "__main__":
    show()
