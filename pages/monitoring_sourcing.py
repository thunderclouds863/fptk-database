import streamlit as st
import pandas as pd
import plotly.express as px
from core.database import get_db
from core.models import DBSourcing, FPTK, User
from core.auth import get_current_user
from datetime import datetime, timedelta

def show():
    """Fungsi utama yang dipanggil dari app.py"""
    show_monitoring_sourcing()

def show_monitoring_sourcing():
    """Fungsi dengan nama spesifik untuk kompatibilitas"""
    st.title("📈 Monitoring Sourcing")
    st.markdown("Monitoring aktivitas sourcing per periode")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
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
        
        # PIC Filter
        pic_list = ["Semua"] + [u[0] for u in db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        pic_filter = st.selectbox("PIC Recruiter", pic_list)
        
        # Kode Unik Filter
        kode_filter = st.text_input("Filter Kode Unik (opsional)", placeholder="Masukkan Kode Unik...")
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
    
    # ============================================================
    # QUERY DATA
    # ============================================================
    week_start, week_end = week_options[selected_week]
    
    query = db.query(DBSourcing).filter(
        DBSourcing.sourcing_date >= week_start,
        DBSourcing.sourcing_date <= week_end
    )
    
    if pic_filter != "Semua":
        query = query.filter(DBSourcing.rekruter == pic_filter)
    
    if kode_filter:
        query = query.filter(DBSourcing.kode_unik.ilike(f"%{kode_filter}%"))
    
    df = pd.read_sql(query.statement, db.bind)
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
    
    # Hitung sourcing per hari
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
            # Daily distribution
            df['date'] = pd.to_datetime(df['sourcing_date'])
            daily = df.groupby(df['date'].dt.date).size().reset_index()
            daily.columns = ['Tanggal', 'Jumlah']
            
            # Tambahkan hari kosong
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
            # Distribution by PIC
            if 'rekruter' in df and df['rekruter'].notna().any():
                pic_counts = df['rekruter'].value_counts().reset_index()
                pic_counts.columns = ['PIC', 'Jumlah']
                fig = px.pie(pic_counts, values='Jumlah', names='PIC', 
                             title='👤 Distribusi per PIC')
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Belum ada data PIC")
    
    # ============================================================
    # TABLE
    # ============================================================
    st.subheader("📋 Detail Data Sourcing")
    
    if total > 0:
        # Pilih kolom yang akan ditampilkan
        display_cols = ['id', 'nama', 'posisi', 'kode_unik', 'rekruter', 'sourcing_date',
                       'sumber_sourcing', 'model_rekrutmen']
        available_cols = [c for c in display_cols if c in df.columns]
        
        display_df = df[available_cols].copy()
        
        # Rename kolom
        rename_map = {
            'id': 'ID', 'nama': 'Nama', 'posisi': 'Posisi', 
            'kode_unik': 'Kode Unik', 'rekruter': 'PIC',
            'sourcing_date': 'Tgl Sourcing', 'sumber_sourcing': 'Sumber',
            'model_rekrutmen': 'Model'
        }
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
        
        # Format tanggal
        if 'Tgl Sourcing' in display_df.columns:
            display_df['Tgl Sourcing'] = pd.to_datetime(display_df['Tgl Sourcing']).dt.strftime('%d/%m/%Y')
        
        # Tampilkan dengan pagination
        page_size = st.selectbox("Baris per halaman", [10, 25, 50, 100], index=1)
        total_pages = (len(display_df) + page_size - 1) // page_size
        page = st.number_input("Halaman", min_value=1, max_value=max(1, total_pages), value=1)
        
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, len(display_df))
        
        st.dataframe(display_df.iloc[start_idx:end_idx], use_container_width=True, height=400)
        
        # Export
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export CSV"):
                csv = df.to_csv(index=False)
                st.download_button("Download CSV", csv, 
                                   f"monitoring_{week_start.strftime('%Y%m%d')}.csv", 
                                   "text/csv")
        with col2:
            if st.button("📊 Export Excel"):
                # Buat Excel dengan styling
                output = pd.ExcelWriter(f"monitoring_{week_start.strftime('%Y%m%d')}.xlsx", engine='xlsxwriter')
                df.to_excel(output, sheet_name='Monitoring', index=False)
                output.close()
                st.success("Export Excel selesai!")
    else:
        st.info("Tidak ada data untuk periode yang dipilih.")
        
        # Tampilkan data FPTK terkait (jika ada)
        st.subheader("📋 FPTK Terkait")
        fptk_query = db.query(FPTK).filter(
            FPTK.fptk_date_real >= week_start,
            FPTK.fptk_date_real <= week_end
        )
        if pic_filter != "Semua":
            fptk_query = fptk_query.filter(FPTK.pic_recruiter == pic_filter)
        if kode_filter:
            fptk_query = fptk_query.filter(FPTK.kode_unik.ilike(f"%{kode_filter}%"))
        
        fptk_df = pd.read_sql(fptk_query.statement, db.bind)
        if len(fptk_df) > 0:
            st.dataframe(fptk_df[['kode_unik', 'posisi', 'pic_recruiter', 'status', 'fptk_date_real']].head(20), 
                        use_container_width=True)
        else:
            st.info("Tidak ada FPTK terkait.")

# Untuk kompatibilitas dengan pemanggilan lama
if __name__ == "__main__":
    show()
