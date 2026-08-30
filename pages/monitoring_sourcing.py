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
    """Menampilkan evidence detail"""
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
    # TABLE MONITORING
    # ============================================================
    st.subheader("📋 Monitoring Sourcing per Kode Unik")
    st.caption("💡 Klik tombol di kolom Evidence untuk melihat detail file")
    
    if total > 0:
        # Group by kode_unik
        grouped = df.groupby('kode_unik')
        
        # Buat list tanggal dari filter
        tanggal_list = [(week_start + timedelta(days=i)) for i in range(7)]
        
        table_data = []
        evidence_map = {}
        all_evidence_ids = []
        
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
            else:
                row['fptk_date_real'] = '-'
                row['status_fptk'] = '-'
                row['filter_kategorisasi'] = '-'
            
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
                        all_evidence_ids.extend(ev_ids)
                    else:
                        row[f'ev_{tgl_str}'] = None
                else:
                    row[f'ev_{tgl_str}'] = None
            
            table_data.append(row)
        
        # ============================================================
        # BUAT DISPLAY DATAFRAME DENGAN HTML BUTTON
        # ============================================================
        display_rows = []
        for row in table_data:
            display_row = {}
            
            display_row['FPTK Date'] = row['fptk_date_real']
            display_row['Kode Unik'] = row['kode_unik']
            display_row['Posisi'] = row['posisi'][:30] + '...' if len(row['posisi'] or '') > 30 else row['posisi']
            display_row['PIC'] = row['pic_recruiter']
            display_row['Status'] = row['status_fptk']
            display_row['Filter'] = row['filter_kategorisasi'][:12] + '...' if len(row['filter_kategorisasi'] or '') > 12 else row['filter_kategorisasi']
            
            # Kolom CV per hari
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                display_row[tgl.strftime('%d/%m')] = row.get(tgl_str, 0)
            
            # 🔥🔥🔥 KOLOM EVIDENCE DENGAN HTML BUTTON 🔥🔥🔥
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                ev_key = f'ev_{tgl_str}'
                ev_data = row.get(ev_key)
                col_name = f'📎 {tgl.strftime("%d/%m")}'
                
                if ev_data and ev_data.get('count', 0) > 0:
                    if ev_data.get('can_view', False):
                        ev_id = ev_data['ids'][0]
                        # 🔥🔥🔥 HTML BUTTON 🔥🔥🔥
                        display_row[col_name] = f'<button onclick="alert(\'Evidence ID: {ev_id}\')" style="background:#4CAF50;color:white;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:12px;">📎 {ev_data["count"]}</button>'
                    else:
                        display_row[col_name] = f'🔒 {ev_data["count"]}'
                else:
                    display_row[col_name] = '-'
            
            display_row['Total'] = row['total_minggu']
            display_rows.append(display_row)
        
        display_df = pd.DataFrame(display_rows)
        
        # ============================================================
        # TAMPILKAN TABEL DENGAN STYLING
        # ============================================================
        st.markdown("""
        <style>
        .stDataFrame {
            font-size: 12px !important;
        }
        .stDataFrame td {
            padding: 4px 8px !important;
        }
        .stDataFrame th {
            padding: 6px 8px !important;
            background-color: #f0f2f6 !important;
            font-weight: bold !important;
            text-align: center !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=500,
            hide_index=True
        )
        
        # ============================================================
        # 🔥🔥🔥 EVIDENCE VIEWER (DENGAN TOMBOL DI BAWAH TABEL) 🔥🔥🔥
        # ============================================================
        st.markdown("---")
        st.markdown("### 📎 Detail Evidence")
        st.caption("Klik tombol 📎 di tabel di atas untuk melihat detail evidence")
        
        # Pilihan evidence dari tabel
        ev_options = []
        ev_option_map = {}
        
        for row in table_data:
            kode = row['kode_unik']
            for tgl in tanggal_list:
                tgl_str = tgl.strftime('%Y-%m-%d')
                ev_key = f'ev_{tgl_str}'
                if ev_key in row and row[ev_key] and row[ev_key].get('count', 0) > 0:
                    hari = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'][tgl.weekday()]
                    label = f"{kode} | {hari} {tgl.strftime('%d/%m/%Y')} ({row[ev_key]['count']} files)"
                    ev_options.append(label)
                    ev_option_map[label] = {
                        'kode_unik': kode,
                        'tanggal': tgl,
                        'ev_data': row[ev_key]
                    }
        
        # Dropdown untuk memilih evidence
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if ev_options:
                selected_label = st.selectbox(
                    "Pilih Evidence dari tabel di atas",
                    ev_options,
                    key="ev_select_direct"
                )
            else:
                st.info("📭 Tidak ada evidence pada periode ini")
                selected_label = None
        
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        
        # ============================================================
        # TAMPILKAN EVIDENCE YANG DIPILIH
        # ============================================================
        if selected_label and selected_label in ev_option_map:
            selected = ev_option_map[selected_label]
            ev_data = selected['ev_data']
            
            if ev_data.get('can_view', False):
                st.markdown(f"### 📎 Evidence untuk {selected['kode_unik']} - {selected['tanggal'].strftime('%d/%m/%Y')}")
                
                for ev_id in ev_data.get('ids', []):
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
        
        # ============================================================
        # LEGEND
        # ============================================================
        st.markdown("---")
        st.markdown("### 📌 Legend")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("📎 = Evidence tersedia (klik tombol atau pilih dari dropdown)")
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
                # Export tanpa HTML
                export_rows = []
                for row in table_data:
                    export_row = {
                        'FPTK Date': row['fptk_date_real'],
                        'Kode Unik': row['kode_unik'],
                        'Posisi': row['posisi'],
                        'PIC': row['pic_recruiter'],
                        'Status FPTK': row['status_fptk'],
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
                st.success("Cache cleared!")
                st.rerun()
        
    else:
        st.info("Tidak ada data untuk periode yang dipilih.")


if __name__ == "__main__":
    show()
