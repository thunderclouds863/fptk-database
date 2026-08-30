import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, FPTK, User, Evidence
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import time
import base64
import io

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
# 🔥🔥🔥 FUNGSI UNTUK TAMPILKAN EVIDENCE 🔥🔥🔥
# ============================================================

def show_evidence_detail(evidence_data, kode_unik, tanggal):
    """Menampilkan detail evidence dalam pop-up style"""
    
    if not evidence_data:
        st.info("Tidak ada evidence untuk tanggal ini.")
        return
    
    st.markdown(f"### 📎 Evidence untuk **{kode_unik}** - {tanggal.strftime('%d/%m/%Y')}")
    st.markdown("---")
    
    for idx, ev in enumerate(evidence_data):
        st.markdown(f"#### Evidence #{idx + 1}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**File:** {ev.get('file_name', '-')}")
            st.markdown(f"**Total CV:** {ev.get('total_cv', '-')}")
            st.markdown(f"**PIC:** {ev.get('pic_recruiter', '-')}")
        with col2:
            st.markdown(f"**Upload:** {ev.get('created_at', '-')}")
            st.markdown(f"**File Size:** {ev.get('file_size', '-')} bytes")
        
        # 🔥🔥🔥 TAMPILKAN GAMBAR (jika ada) 🔥🔥🔥
        file_data = ev.get('file_data')
        file_name = ev.get('file_name', '')
        
        if file_data:
            try:
                # Cek apakah file adalah gambar
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
                is_image = any(file_name.lower().endswith(ext) for ext in image_extensions)
                
                if is_image:
                    # Tampilkan gambar
                    st.image(file_data, caption=file_name, use_container_width=True)
                else:
                    # Tampilkan sebagai download button
                    st.download_button(
                        label=f"📥 Download {file_name}",
                        data=file_data,
                        file_name=file_name,
                        mime="application/octet-stream",
                        key=f"download_{kode_unik}_{tanggal}_{idx}"
                    )
            except Exception as e:
                st.warning(f"Tidak bisa menampilkan file: {str(e)}")
        else:
            st.info("File tidak tersedia untuk ditampilkan.")
        
        st.markdown("---")


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
    # 🔥🔥🔥 SESSION STATE UNTUK EVIDENCE POP-UP 🔥🔥🔥
    # ============================================================
    if 'show_evidence' not in st.session_state:
        st.session_state.show_evidence = False
    if 'evidence_kode_unik' not in st.session_state:
        st.session_state.evidence_kode_unik = None
    if 'evidence_tanggal' not in st.session_state:
        st.session_state.evidence_tanggal = None
    if 'evidence_data' not in st.session_state:
        st.session_state.evidence_data = None
    
    # ============================================================
    # LOAD DATA
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        pic_list = get_pic_options_monitoring(db)
    
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
        
        pic_filter = st.selectbox("PIC Recruiter", pic_list)
        kode_filter = st.text_input("Filter Kode Unik (opsional)", placeholder="Masukkan Kode Unik...")
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    week_start, week_end = week_options[selected_week]
    
    with st.spinner("📊 Memuat data..."):
        df = get_monitoring_data(db, week_start, week_end, pic_filter, kode_filter)
        kode_unik_list = df['kode_unik'].dropna().unique().tolist()
        fptk_df = get_fptk_data(db, kode_unik_list) if kode_unik_list else pd.DataFrame()
        evidence_df = get_evidence_data(db, kode_unik_list) if kode_unik_list else pd.DataFrame()
    
    total = len(df)
    
    # ============================================================
    # METRIC CARDS
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
    # BUILD TABLE
    # ============================================================
    st.subheader("📋 Monitoring Sourcing per Kode Unik")
    
    if total > 0:
        grouped = df.groupby('kode_unik')
        tanggal_list = [(week_start + timedelta(days=i)) for i in range(7)]
        
        table_data = []
        evidence_map = {}  # Untuk menyimpan evidence per kode_unik + tanggal
        
        for kode_unik, group in grouped:
            row = {
                'kode_unik': kode_unik,
                'posisi': group.iloc[0].get('posisi', '-'),
                'pic_recruiter': group.iloc[0].get('rekruter', '-'),
            }
            
            # FPTK Data
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
                        can_view = admin or (ev_rows.iloc[0].get('pic_recruiter') == user.pic_recruiter)
                        ev_count = len(ev_rows)
                        row[f'ev_{tgl_str}'] = ev_count
                        # Simpan data evidence untuk ditampilkan nanti
                        key = f"{kode_unik}_{tgl_str}"
                        evidence_map[key] = {
                            'count': ev_count,
                            'can_view': can_view,
                            'data': ev_rows.to_dict('records'),
                            'kode_unik': kode_unik,
                            'tanggal': tgl
                        }
                    else:
                        row[f'ev_{tgl_str}'] = 0
                else:
                    row[f'ev_{tgl_str}'] = 0
            
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
        # RENAME COLUMNS
        # ============================================================
        hari_indonesia = {
            0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'
        }
        
        rename_map = {
            'fptk_date_real': 'FPTK Date',
            'kode_unik': 'Kode Unik',
            'posisi': 'Posisi',
            'pic_recruiter': 'PIC',
            'status_fptk': 'Status FPTK',
            'filter_kategorisasi': 'Filter Kat',
            'total_minggu': 'Total'
        }
        
        for tgl in tanggal_list:
            tgl_str = tgl.strftime('%Y-%m-%d')
            hari = hari_indonesia[tgl.weekday()]
            tgl_display = f"{hari} {tgl.strftime('%d/%m')}"
            rename_map[tgl_str] = tgl_display
            rename_map[f'ev_{tgl_str}'] = f'📎{tgl.strftime("%d/%m")}'
        
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
        
        # ============================================================
        # 🔥🔥🔥 RENDER TABLE DENGAN TOMBOL EVIDENCE 🔥🔥🔥
        # ============================================================
        
        # Buat daftar kolom evidence
        ev_columns = [col for col in display_df.columns if col.startswith('📎')]
        
        # Tampilkan tabel dengan custom rendering
        st.markdown("""
        <style>
        .ev-btn {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 2px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .ev-btn:hover {
            background: #45a049;
        }
        .ev-btn-locked {
            background: #ff9800;
            color: white;
            border: none;
            padding: 2px 10px;
            border-radius: 4px;
            font-size: 12px;
        }
        .ev-btn-zero {
            color: #999;
            font-size: 12px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Buat HTML table
        html = '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        
        # Header
        html += '<tr style="background:#f0f2f6;border-bottom:2px solid #ddd;">'
        for col in display_df.columns:
            html += f'<th style="padding:8px 10px;text-align:left;font-weight:600;">{col}</th>'
        html += '</tr>'
        
        # Body
        for idx, row in display_df.iterrows():
            html += '<tr style="border-bottom:1px solid #eee;">'
            for col in display_df.columns:
                val = row[col]
                
                # 🔥🔥🔥 KOLOM EVIDENCE -> TOMBOL 🔥🔥🔥
                if col in ev_columns:
                    # Cari kode_unik dan tanggal dari baris
                    kode_unik = row['Kode Unik']
                    # Cari tanggal dari nama kolom
                    tgl_str = col.replace('📎', '').strip()
                    # Cari di tanggal_list
                    tgl_match = None
                    for tgl in tanggal_list:
                        if tgl.strftime('%d/%m') == tgl_str:
                            tgl_match = tgl
                            break
                    
                    if tgl_match:
                        key = f"{kode_unik}_{tgl_match.strftime('%Y-%m-%d')}"
                        ev_info = evidence_map.get(key)
                        
                        if ev_info and ev_info['count'] > 0:
                            if ev_info['can_view']:
                                # 🔥 TOMBOL KLIK UNTUK LIHAT EVIDENCE
                                btn_key = f"ev_{kode_unik}_{tgl_match.strftime('%Y%m%d')}"
                                if st.button(f"📎 {ev_info['count']}", key=btn_key, use_container_width=True):
                                    st.session_state.show_evidence = True
                                    st.session_state.evidence_kode_unik = kode_unik
                                    st.session_state.evidence_tanggal = tgl_match
                                    st.session_state.evidence_data = ev_info['data']
                                    st.rerun()
                                html += f'<td style="padding:4px 10px;">{ev_info["count"]}</td>'
                            else:
                                html += f'<td style="padding:4px 10px;">🔒 {ev_info["count"]}</td>'
                        else:
                            html += f'<td style="padding:4px 10px;color:#999;">-</td>'
                    else:
                        html += f'<td style="padding:4px 10px;">{val}</td>'
                else:
                    html += f'<td style="padding:4px 10px;">{val}</td>'
            html += '</tr>'
        
        html += '</table>'
        
        st.markdown(html, unsafe_allow_html=True)
        
        # ============================================================
        # 🔥🔥🔥 EVIDENCE POP-UP / DETAIL (DI BAWAH TABEL) 🔥🔥🔥
        # ============================================================
        
        if st.session_state.show_evidence:
            st.markdown("---")
            st.markdown("### 📎 Evidence Detail")
            
            # Tombol close
            if st.button("❌ Tutup Evidence", use_container_width=False):
                st.session_state.show_evidence = False
                st.session_state.evidence_kode_unik = None
                st.session_state.evidence_tanggal = None
                st.session_state.evidence_data = None
                st.rerun()
            
            # Tampilkan evidence
            if st.session_state.evidence_data:
                show_evidence_detail(
                    st.session_state.evidence_data,
                    st.session_state.evidence_kode_unik,
                    st.session_state.evidence_tanggal
                )
            else:
                st.info("Tidak ada data evidence untuk ditampilkan.")
        
        # ============================================================
        # LEGEND & EXPORT
        # ============================================================
        st.markdown("---")
        st.markdown("### 📌 Legend")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("📎 = Evidence tersedia (klik tombol)")
        with col2:
            st.markdown("🔒 = Evidence terkunci (hanya PIC/Admin)")
        with col3:
            st.markdown("- = Tidak ada evidence")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export CSV", use_container_width=True):
                export_df = display_df.copy()
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
