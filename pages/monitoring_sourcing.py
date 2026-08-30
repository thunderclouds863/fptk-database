import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, FPTK, User, Evidence
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import time
import base64

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
    """Fungsi utama yang dipanggil dari app.py"""
    show_monitoring_sourcing()


def show_monitoring_sourcing():
    """Fungsi dengan nama spesifik untuk kompatibilitas"""
    st.title("📈 Monitoring Sourcing")
    st.markdown("Monitoring aktivitas sourcing per periode dengan evidence")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # 🔥🔥🔥 LOAD FROM CACHE 🔥🔥🔥
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        pic_list = get_pic_options_monitoring(db)
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        
        # Pilih minggu (12 minggu terakhir)
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
    # HEADER
    # ============================================================
    st.subheader(f"📅 Minggu: {week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}")
    
    # ============================================================
    # METRIC CARDS
    # ============================================================
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
    # 🔥🔥🔥 TABLE MONITORING DENGAN EVIDENCE KLIKABLE 🔥🔥🔥
    # ============================================================
    st.subheader("📋 Monitoring Sourcing per Kode Unik")
    
    if total > 0:
        # ============================================================
        # BUILD TABLE PER KODE UNIK
        # ============================================================
        
        grouped = df.groupby('kode_unik')
        tanggal_list = [(week_start + timedelta(days=i)) for i in range(7)]
        
        table_data = []
        all_evidence_data = {}  # Untuk menyimpan evidence detail
        
        for kode_unik, group in grouped:
            row = {
                'kode_unik': kode_unik,
                'posisi': group.iloc[0].get('posisi', '-'),
                'pic_recruiter': group.iloc[0].get('rekruter', '-'),
                'total_cv': len(group)
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
            
            row['total_minggu'] = len(group)
            
            # Evidence per tanggal
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                if not evidence_df.empty:
                    ev_rows = evidence_df[
                        (evidence_df['kode_unik'] == kode_unik) & 
                        (evidence_df['tanggal'] == tgl)
                    ]
                    if not ev_rows.empty:
                        ev = ev_rows.iloc[0]
                        can_view = admin or (ev.get('pic_recruiter') == user.pic_recruiter)
                        row[f'ev_{tgl_str}'] = {
                            'count': len(ev_rows),
                            'can_view': can_view,
                            'data': ev_rows.to_dict('records'),
                            'kode_unik': kode_unik,
                            'tanggal': tgl
                        }
                        # Simpan untuk detail view
                        key = f"{kode_unik}_{tgl_str}"
                        all_evidence_data[key] = row[f'ev_{tgl_str}']
                    else:
                        row[f'ev_{tgl_str}'] = None
                else:
                    row[f'ev_{tgl_str}'] = None
            
            table_data.append(row)
        
        display_df = pd.DataFrame(table_data)
        
        # ============================================================
        # SUSUN KOLOM
        # ============================================================
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
        
        # Format tanggal FPTK
        if 'fptk_date_real' in display_df.columns:
            display_df['fptk_date_real'] = display_df['fptk_date_real'].apply(
                lambda x: x.strftime('%d/%m/%y') if isinstance(x, pd.Timestamp) else (x if x != '-' else '-')
            )
        
        # ============================================================
        # 🔥🔥🔥 RENAME & FORMAT EVIDENCE UNTUK DISPLAY 🔥🔥🔥
        # ============================================================
        hari_indonesia = {
            0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'
        }
        
        rename_map = {
            'fptk_date_real': 'FPTK Date (Real)',
            'kode_unik': 'Kode Unik',
            'posisi': 'Posisi',
            'pic_recruiter': 'PIC Recruiter',
            'status_fptk': 'Status FPTK',
            'filter_kategorisasi': 'Filter Kategorisasi FPTK',
            'total_minggu': 'Total Week'
        }
        
        for tgl in tanggal_list:
            tgl_str = tgl.strftime('%Y-%m-%d')
            hari = hari_indonesia[tgl.weekday()]
            tgl_display = f"{hari} {tgl.strftime('%d/%m/%y')}"
            rename_map[tgl_str] = tgl_display
            rename_map[f'ev_{tgl_str}'] = f'📎 {tgl.strftime("%d/%m")}'
        
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
        
        # ============================================================
        # 🔥🔥🔥 KONVERSI EVIDENCE KE HTML BUTTON 🔥🔥🔥
        # ============================================================
        
        # Cari kolom evidence
        ev_columns = [col for col in display_df.columns if col.startswith('📎')]
        
        # Buat session state untuk menyimpan evidence yang dipilih
        if 'selected_evidence' not in st.session_state:
            st.session_state.selected_evidence = None
        if 'show_evidence_detail' not in st.session_state:
            st.session_state.show_evidence_detail = False
        
        # Fungsi untuk membuat button HTML
        def make_evidence_button(kode_unik, tgl_str, count, can_view):
            if count == 0:
                return '-'
            
            if can_view:
                # Button untuk lihat evidence
                btn_id = f"ev_{kode_unik}_{tgl_str}".replace('-', '_')
                return f'<button onclick="document.getElementById(\'{btn_id}\').click()" style="background:#4CAF50;color:white;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:12px;">📎 {count}</button>'
            else:
                return f'🔒 {count}'
        
        # Buat kolom evidence sebagai HTML
        for col in ev_columns:
            # Cari tanggal dari nama kolom
            tgl_str = None
            for tgl in tanggal_list:
                if col == f'📎 {tgl.strftime("%d/%m")}':
                    tgl_str = tgl.strftime('%Y-%m-%d')
                    break
            
            if tgl_str:
                display_df[col] = display_df.apply(
                    lambda row, t=tgl_str, c=col: make_evidence_button(
                        row['Kode Unik'],
                        t,
                        row[c] if isinstance(row[c], dict) and row[c] is not None else 0,
                        row[c]['can_view'] if isinstance(row[c], dict) and row[c] is not None else False
                    ) if isinstance(row[c], dict) else '-',
                    axis=1
                )
        
        # Tampilkan dataframe dengan HTML
        st.markdown("""
        <style>
        .dataframe td {
            white-space: nowrap;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Tampilkan sebagai HTML table dengan custom rendering
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # ============================================================
        # 🔥🔥🔥 EVIDENCE DETAIL POPUP (DI BAWAH TABEL) 🔥🔥🔥
        # ============================================================
        
        # Pilihan untuk melihat evidence detail
        st.markdown("---")
        st.markdown("### 📎 Detail Evidence")
        
        col1, col2 = st.columns([2, 3])
        
        with col1:
            # Pilih Kode Unik
            kode_options = sorted(display_df['Kode Unik'].unique().tolist())
            selected_kode = st.selectbox("Pilih Kode Unik", kode_options, key="ev_kode_select")
        
        with col2:
            # Pilih Tanggal
            if selected_kode:
                # Cari tanggal yang ada evidence untuk kode ini
                tanggal_available = []
                for tgl in tanggal_list:
                    tgl_str = tgl.strftime('%Y-%m-%d')
                    key = f"{selected_kode}_{tgl_str}"
                    if key in all_evidence_data and all_evidence_data[key]:
                        tanggal_available.append(tgl)
                
                if tanggal_available:
                    selected_tgl = st.selectbox(
                        "Pilih Tanggal",
                        tanggal_available,
                        format_func=lambda x: f"{hari_indonesia[x.weekday()]}, {x.strftime('%d/%m/%Y')}",
                        key="ev_tgl_select"
                    )
                else:
                    st.info("Tidak ada evidence untuk kode unik ini")
                    selected_tgl = None
            else:
                selected_tgl = None
        
        # Tampilkan detail evidence
        if selected_kode and selected_tgl:
            tgl_str = selected_tgl.strftime('%Y-%m-%d')
            key = f"{selected_kode}_{tgl_str}"
            
            if key in all_evidence_data and all_evidence_data[key]:
                ev_info = all_evidence_data[key]
                
                if ev_info.get('can_view', False):
                    st.markdown(f"#### 📎 Evidence untuk **{selected_kode}** - {selected_tgl.strftime('%d/%m/%Y')}")
                    
                    for ev in ev_info.get('data', []):
                        st.markdown(f"- **File:** {ev.get('file_name', '-')}")
                        st.markdown(f"  **Total CV:** {ev.get('total_cv', '-')}")
                        st.markdown(f"  **Upload oleh:** {ev.get('pic_recruiter', '-')}")
                        st.markdown(f"  **Tanggal Upload:** {ev.get('created_at', '-')}")
                        st.markdown("---")
                else:
                    st.warning("🔒 Evidence ini hanya bisa dilihat oleh PIC yang upload atau Admin")
            else:
                st.info("Tidak ada evidence untuk tanggal ini")
        
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
                export_df = display_df.copy()
                # Clean up evidence columns for export
                for col in ev_columns:
                    export_df[col] = export_df[col].apply(
                        lambda x: str(x) if x != '-' else '-'
                    )
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
                st.success("Cache cleared!")
                st.rerun()
        
    else:
        st.info("Tidak ada data untuk periode yang dipilih.")


# Untuk kompatibilitas dengan pemanggilan lama
if __name__ == "__main__":
    show()
