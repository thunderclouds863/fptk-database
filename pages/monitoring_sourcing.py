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
# 🔥🔥🔥 CACHE FUNCTIONS (GANTI ke st.cache_resource) 🔥🔥🔥
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

def show_evidence_detail(evidence_id, db):
    """Menampilkan detail evidence di popup/expander"""
    try:
        ev = db.query(Evidence).filter(Evidence.id == evidence_id).first()
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
        
        # Cek apakah ada file_data
        if hasattr(ev, 'file_data') and ev.file_data:
            try:
                image_data = base64.b64decode(ev.file_data)
                st.image(image_data, caption=ev.file_name, use_container_width=True)
            except:
                st.info("File tidak bisa ditampilkan sebagai gambar")
        else:
            # Cek file di path
            if ev.file_path and os.path.exists(ev.file_path):
                with open(ev.file_path, "rb") as f:
                    file_data = f.read()
                st.download_button(
                    "📥 Download File",
                    file_data,
                    ev.file_name,
                    mime="application/octet-stream",
                    key=f"download_{evidence_id}"
                )
            else:
                st.info("💡 File tidak ditemukan di server")
        
        # Download jika ada file_data
        if hasattr(ev, 'file_data') and ev.file_data:
            try:
                file_bytes = base64.b64decode(ev.file_data)
                st.download_button(
                    "📥 Download File",
                    file_bytes,
                    ev.file_name,
                    mime="application/octet-stream",
                    key=f"download_b64_{evidence_id}"
                )
            except:
                pass
                
    except Exception as e:
        st.error(f"Error menampilkan evidence: {str(e)}")


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
    # TABLE MONITORING
    # ============================================================
    st.subheader("📋 Monitoring Sourcing per Kode Unik")
    
    if total > 0:
        # Group by kode_unik
        grouped = df.groupby('kode_unik')
        
        # Buat list tanggal dari filter
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
                        evidence_map[f"{kode_unik}_{tgl_str}"] = ev_ids
                    else:
                        row[f'ev_{tgl_str}'] = None
                else:
                    row[f'ev_{tgl_str}'] = None
            
            table_data.append(row)
        
        # ============================================================
        # BUAT DISPLAY DATAFRAME
        # ============================================================
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
        
        # Urutan kolom
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
        
        # Rename kolom
        rename_map = {
            'fptk_date_real': 'FPTK Date (Real)',
            'kode_unik': 'Kode Unik',
            'posisi': 'Posisi',
            'pic_recruiter': 'PIC Recruiter',
            'status_fptk': 'Status FPTK',
            'filter_kategorisasi': 'Filter Kategorisasi FPTK',
            'total_minggu': 'Total Week'
        }
        
        hari_indonesia = {
            0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'
        }
        for tgl in tanggal_list:
            tgl_str = tgl.strftime('%Y-%m-%d')
            hari = hari_indonesia[tgl.weekday()]
            tgl_display = f"{hari} {tgl.strftime('%d/%m/%y')}"
            rename_map[tgl_str] = tgl_display
            rename_map[f'ev_{tgl_str}'] = f'Evidence {tgl.strftime("%d/%m")}'
        
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
        
        # ============================================================
        # TAMPILKAN TABEL
        # ============================================================
        st.dataframe(
            display_df,
            use_container_width=True,
            height=500,
            hide_index=True
        )
        
        # ============================================================
        # EVIDENCE VIEWER
        # ============================================================
        st.markdown("---")
        st.markdown("### 📎 Evidence Viewer")
        st.caption("Klik tombol di bawah untuk melihat evidence per Kode Unik dan Tanggal")
        
        col1, col2 = st.columns(2)
        
        with col1:
            kode_options = sorted(display_df['Kode Unik'].unique().tolist())
            selected_kode = st.selectbox("Pilih Kode Unik", kode_options, key="ev_kode_select")
        
        with col2:
            tanggal_options = []
            if selected_kode:
                for tgl in tanggal_list:
                    key = f"{selected_kode}_{tgl.strftime('%Y-%m-%d')}"
                    if key in evidence_map and evidence_map[key]:
                        tanggal_options.append(tgl)
            
            if tanggal_options:
                selected_tanggal = st.selectbox(
                    "Pilih Tanggal", 
                    tanggal_options,
                    format_func=lambda x: f"{hari_indonesia[x.weekday()]} {x.strftime('%d/%m/%Y')}",
                    key="ev_tanggal_select"
                )
            else:
                st.info("Tidak ada evidence untuk kode unik ini")
                selected_tanggal = None
        
        # ============================================================
        # TAMPILKAN EVIDENCE
        # ============================================================
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
                                        st.image(image_data, caption=ev.file_name, use_container_width=True)
                                        
                                        st.download_button(
                                            label="⬇️ Download File",
                                            data=image_data,
                                            file_name=ev.file_name,
                                            mime="application/octet-stream",
                                            key=f"download_ev_{ev_id}"
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
                                        label="⬇️ Download File",
                                        data=file_data,
                                        file_name=ev.file_name,
                                        mime="application/octet-stream",
                                        key=f"download_path_{ev_id}"
                                    )
                                else:
                                    st.info("💡 File tidak ditemukan di server")
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
            st.markdown("📎 = Evidence tersedia (klik di bawah untuk lihat)")
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
                csv = display_df.to_csv(index=False)
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
                st.success("Cache cleared!")
                st.rerun()
        
    else:
        st.info("Tidak ada data untuk periode yang dipilih.")


# Untuk kompatibilitas
if __name__ == "__main__":
    show()
