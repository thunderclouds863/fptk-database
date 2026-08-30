import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, FPTK, User, Evidence
from core.auth import get_current_user, is_admin
from datetime import datetime, timedelta
import time
import base64
import os

# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS 🔥🔥🔥
# ============================================================

@st.cache_resource(ttl=3600)
def get_pic_options_monitoring(_db):
    """Mengambil opsi PIC - cache 1 jam"""
    try:
        pic_list = ["Semua"] + [u[0] for u in _db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        return pic_list
    except:
        return ["Semua"]


@st.cache_resource(ttl=300)
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


@st.cache_resource(ttl=300)
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


@st.cache_resource(ttl=300)
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
# FUNGSI TAMPILKAN EVIDENCE
# ============================================================

def show_evidence_detail(ev_id, db):
    """Menampilkan evidence detail di container yang diberikan"""
    try:
        ev = db.query(Evidence).filter(Evidence.id == ev_id).first()
        if not ev:
            st.warning("Evidence tidak ditemukan")
            return
        
        st.markdown(f"### 📎 {ev.file_name}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Kode Unik:** {ev.kode_unik}")
        with col2:
            st.markdown(f"**Tanggal:** {ev.tanggal.strftime('%d/%m/%Y') if ev.tanggal else '-'}")
        with col3:
            st.markdown(f"**PIC:** {ev.pic_recruiter}")
        
        st.markdown(f"**Total CV:** {ev.total_cv}")
        st.markdown(f"**Upload:** {ev.created_at.strftime('%d/%m/%Y %H:%M') if ev.created_at else '-'}")
        
        if hasattr(ev, 'file_data') and ev.file_data:
            try:
                image_data = base64.b64decode(ev.file_data)
                st.image(image_data, caption=ev.file_name, use_container_width=True)
                st.download_button(
                    "📥 Download File",
                    image_data,
                    ev.file_name,
                    mime="application/octet-stream",
                    key=f"download_{ev.id}"
                )
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
            st.download_button(
                "📥 Download File",
                file_data,
                ev.file_name,
                mime="application/octet-stream",
                key=f"download_path_{ev.id}"
            )
        else:
            st.info("💡 File tidak ditemukan di server")
    except Exception as e:
        st.error(f"Error: {str(e)}")


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
    # LOAD FROM CACHE
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        pic_list = get_pic_options_monitoring(db)
    
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
        
        pic_filter = st.selectbox("PIC Recruiter", pic_list)
        kode_filter = st.text_input("Filter Kode Unik (opsional)", placeholder="Masukkan Kode Unik...")
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
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
    # 🔥🔥🔥 TABLE DENGAN TOMBOL EVIDENCE 🔥🔥🔥
    # ============================================================
    st.subheader("📋 Monitoring Sourcing per Kode Unik")
    st.caption("💡 Klik tombol 📎 di kolom Evidence untuk melihat detail")
    
    if total > 0:
        # Group by kode_unik
        grouped = df.groupby('kode_unik')
        
        # Buat list tanggal dari filter
        tanggal_list = [(week_start + timedelta(days=i)) for i in range(7)]
        
        table_data = []
        evidence_map = {}
        evidence_id_map = {}  # Untuk mapping tombol ke evidence ID
        
        for kode_unik, group in grouped:
            row = {
                'kode_unik': kode_unik,
                'posisi': group.iloc[0].get('posisi', '-'),
                'pic_recruiter': group.iloc[0].get('rekruter', '-'),
                'total_cv': len(group)
            }
            
            # Ambil data FPTK
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
            
            # Hitung CV per tanggal
            for tgl in tanggal_list:
                count = len(group[group['sourcing_date'] == tgl])
                row[tgl.strftime('%Y-%m-%d')] = count
            
            # Total minggu ini
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
                        can_view = admin
                        if not can_view:
                            for _, ev in ev_rows.iterrows():
                                if ev.get('pic_recruiter') == user.pic_recruiter:
                                    can_view = True
                                    break
                        
                        ev_ids = ev_rows['id'].tolist()
                        row[f'ev_{tgl_str}'] = {
                            'count': len(ev_rows),
                            'can_view': can_view,
                            'ids': ev_ids
                        }
                        # Simpan mapping untuk tombol
                        for ev_id in ev_ids:
                            evidence_id_map[f"{kode_unik}_{tgl_str}_{ev_id}"] = ev_id
                        evidence_map[f"{kode_unik}_{tgl_str}"] = ev_ids
                    else:
                        row[f'ev_{tgl_str}'] = None
                else:
                    row[f'ev_{tgl_str}'] = None
            
            table_data.append(row)
        
        # ============================================================
        # 🔥🔥🔥 RENDER TABEL DENGAN TOMBOL 🔥🔥🔥
        # ============================================================
        
        # Header tabel
        hari_indonesia = {
            0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'
        }
        
        # Buat header columns
        header_cols = st.columns([1.2, 2, 1.2, 1, 1, 1] + [0.8] * 7 + [0.8] * 7 + [0.8])
        
        headers = ['Kode Unik', 'Posisi', 'PIC', 'Status', 'FPTK Date', 'Filter']
        for tgl in tanggal_list:
            headers.append(f"{hari_indonesia[tgl.weekday()]}\n{tgl.strftime('%d/%m')}")
        for tgl in tanggal_list:
            headers.append(f"📎\n{tgl.strftime('%d/%m')}")
        headers.append('Total')
        
        for i, header in enumerate(headers):
            with header_cols[i]:
                st.markdown(f"**{header}**")
        
        st.markdown("---")
        
        # 🔥🔥🔥 RENDER SETIAP BARIS DENGAN TOMBOL 🔥🔥🔥
        selected_ev_id = None
        
        for idx, row in enumerate(table_data):
            # Buat columns untuk setiap baris
            cols = st.columns([1.2, 2, 1.2, 1, 1, 1] + [0.8] * 7 + [0.8] * 7 + [0.8])
            
            col_idx = 0
            
            # Kolom data utama
            with cols[col_idx]:
                st.write(row['kode_unik'])
            col_idx += 1
            
            with cols[col_idx]:
                st.write(row['posisi'][:25] + '...' if len(row['posisi'] or '') > 25 else row['posisi'])
            col_idx += 1
            
            with cols[col_idx]:
                st.write(row['pic_recruiter'])
            col_idx += 1
            
            with cols[col_idx]:
                st.write(row['status_fptk'])
            col_idx += 1
            
            with cols[col_idx]:
                st.write(row['fptk_date_real'])
            col_idx += 1
            
            with cols[col_idx]:
                st.write(row['filter_kategorisasi'][:10] + '...' if len(row['filter_kategorisasi'] or '') > 10 else row['filter_kategorisasi'])
            col_idx += 1
            
            # Kolom CV per hari (7 hari)
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                with cols[col_idx]:
                    val = row.get(tgl_str, 0)
                    if val > 0:
                        st.write(f"{val}")
                    else:
                        st.write("-")
                col_idx += 1
            
            # 🔥🔥🔥 KOLOM EVIDENCE - TOMBOL 🔥🔥🔥
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                ev_key = f'ev_{tgl_str}'
                ev_data = row.get(ev_key)
                
                with cols[col_idx]:
                    if ev_data and ev_data.get('count', 0) > 0:
                        if ev_data.get('can_view', False):
                            # 🔥🔥🔥 TOMBOL EVIDENCE 🔥🔥🔥
                            ev_id = ev_data['ids'][0]  # Ambil ID pertama
                            button_key = f"ev_{idx}_{tgl_str}"
                            
                            if st.button(
                                f"📎 {ev_data['count']}", 
                                key=button_key,
                                help=f"Lihat {ev_data['count']} file evidence",
                                use_container_width=True
                            ):
                                selected_ev_id = ev_id
                                st.session_state['selected_ev_id'] = ev_id
                        else:
                            st.write(f"🔒 {ev_data['count']}")
                    else:
                        st.write("-")
                col_idx += 1
            
            # Total Week
            with cols[col_idx]:
                st.write(row['total_minggu'])
            col_idx += 1
            
            # Garis pemisah
            st.markdown("---")
        
        # ============================================================
        # 🔥🔥🔥 TAMPILKAN EVIDENCE YANG DIPILIH 🔥🔥🔥
        # ============================================================
        st.markdown("---")
        st.markdown("### 📎 Detail Evidence")
        
        # Cek apakah ada evidence yang dipilih dari session state atau dari tombol
        if 'selected_ev_id' not in st.session_state:
            st.session_state['selected_ev_id'] = None
        
        # Jika tombol diklik, update session state
        if selected_ev_id:
            st.session_state['selected_ev_id'] = selected_ev_id
        
        # Tampilkan evidence jika ada
        if st.session_state['selected_ev_id']:
            ev_id = st.session_state['selected_ev_id']
            show_evidence_detail(ev_id, db)
            
            # Tombol clear
            if st.button("🗑️ Tutup Detail", use_container_width=True):
                st.session_state['selected_ev_id'] = None
                st.rerun()
        else:
            st.info("💡 Klik tombol 📎 di kolom Evidence untuk melihat detail")
        
        # ============================================================
        # LEGEND
        # ============================================================
        st.markdown("---")
        st.markdown("### 📌 Legend")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("📎 = Evidence tersedia (klik tombol untuk lihat)")
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
                        'Kode Unik': row['kode_unik'],
                        'Posisi': row['posisi'],
                        'PIC': row['pic_recruiter'],
                        'Status FPTK': row['status_fptk'],
                        'FPTK Date': row['fptk_date_real'],
                        'Filter Kategorisasi': row['filter_kategorisasi'],
                    }
                    for tgl in tanggal_list:
                        tgl_str = tgl.strftime('%Y-%m-%d')
                        export_row[tgl.strftime('%d/%m')] = row.get(tgl_str, 0)
                    for tgl in tanggal_list:
                        tgl_str = tgl.strftime('%Y-%m-%d')
                        ev_key = f'ev_{tgl_str}'
                        ev_data = row.get(ev_key)
                        export_row[f'Evidence {tgl.strftime("%d/%m")}'] = ev_data.get('count', 0) if ev_data else 0
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
                st.cache_resource.clear()
                st.session_state['selected_ev_id'] = None
                st.success("Cache cleared!")
                st.rerun()
        
    else:
        st.info("Tidak ada data untuk periode yang dipilih.")


if __name__ == "__main__":
    show()
