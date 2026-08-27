import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DBKodePosisi, MasterDropdown, FPTK
from core.auth import get_current_user, is_admin
from datetime import datetime
import re

def show_db_kode_posisi():
    st.title("🏢 DB Kode Posisi")
    st.markdown("Master database posisi, lokasi, dan mapping user (mirip sheet DB Kode Posisi di VBA).")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # LOAD MASTER DATA UNTUK DROPDOWN
    # ============================================================
    master_records = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
    bu_options = sorted(set([m.bu for m in master_records if m.bu]))
    direktorat_options = sorted(set([m.nama_direktorat for m in master_records if m.nama_direktorat]))
    
    # ============================================================
    # FILTERS
    # ============================================================
    with st.sidebar:
        st.markdown("### 🔍 Filter")
        
        search = st.text_input("🔎 Cari Position", placeholder="Ketik posisi...")
        bu_filter = st.selectbox("Business Unit", ["Semua"] + bu_options)
        
        st.markdown("---")
        if st.button("🔄 Reset Filter", use_container_width=True):
            st.rerun()
    
    # ============================================================
    # BUILD QUERY
    # ============================================================
    query = db.query(DBKodePosisi)
    
    if search:
        query = query.filter(DBKodePosisi.position.ilike(f"%{search}%"))
    if bu_filter != "Semua":
        query = query.filter(DBKodePosisi.business_unit == bu_filter)
    
    total = query.count()
    
    # ============================================================
    # METRIK CARD
    # ============================================================
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Position", total)
    
    # Hitung posisi dengan User Manager terisi
    if total > 0:
        df_all = pd.read_sql(query.statement, db.bind)
        has_user = len(df_all[df_all['user_manager'].notna()]) if 'user_manager' in df_all else 0
        col2.metric("Dengan User Manager", has_user)
        col3.metric("Tanpa User Manager", total - has_user)
    
    st.markdown("---")
    
    # ============================================================
    # TABEL LIST DB KODE POSISI
    # ============================================================
    st.markdown("### 📋 Daftar Position")
    
    if total == 0:
        st.info("Tidak ada data DB Kode Posisi.")
    else:
        # Pagination
        page_size = st.number_input("Baris per halaman", min_value=10, max_value=200, value=50)
        page = st.number_input("Halaman", min_value=1, max_value=max(1, (total + page_size - 1) // page_size), value=1)
        offset = (page - 1) * page_size
        
        df = pd.read_sql(query.limit(page_size).offset(offset).statement, db.bind)
        
        st.dataframe(
            df,
            use_container_width=True,
            height=400,
            column_config={
                "id": "ID",
                "kode": "Kode",
                "position": "Position",
                "location": "Location",
                "business_unit": "Business Unit",
                "division_chris": "Division CHRIS",
                "department_chris": "Department CHRIS",
                "user_manager": "User (Manager)",
                "indirect_user": "Indirect User",
                "directorate": "Directorate",
                "year": "Year"
            }
        )
    
    # ============================================================
    # TAMBAH POSITION BARU
    # ============================================================
    st.markdown("---")
    st.markdown("### ➕ Tambah Position Baru")
    
    if not admin:
        st.warning("⚠️ Hanya Admin yang bisa menambah/mengedit DB Kode Posisi.")
    else:
        with st.form("add_position_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                position = st.text_input("Position *", placeholder="Contoh: Sales Taking Order Staff (Chilled)")
                location = st.text_input("Location", placeholder="Contoh: Jakarta, Cikupa, Sentul")
                business_unit = st.selectbox("Business Unit", [""] + bu_options)
                directorate = st.selectbox("Directorate", [""] + direktorat_options)
            
            with col2:
                division = st.text_input("Division CHRIS", placeholder="Contoh: Commercial CMD")
                department = st.text_input("Department CHRIS", placeholder="Contoh: Sales General Trade")
                user_manager = st.text_input("User (Manager)", placeholder="Nama User Manager")
                indirect_user = st.text_input("Indirect User", placeholder="Nama Indirect User")
            
            # Auto generate year
            year = datetime.now().year
            
            submitted = st.form_submit_button("💾 Tambah Position", type="primary")
            
            if submitted:
                if not position:
                    st.error("❌ Position wajib diisi!")
                else:
                    # Cek duplikat
                    existing = db.query(DBKodePosisi).filter(
                        DBKodePosisi.position == position,
                        DBKodePosisi.business_unit == business_unit,
                        DBKodePosisi.location == location
                    ).first()
                    
                    if existing:
                        st.warning(f"⚠️ Position '{position}' dengan BU '{business_unit}' dan Location '{location}' sudah ada!")
                    else:
                        try:
                            # Generate kode otomatis (mirip VBA GenerateNewPositionCode)
                            # Cari max kode numeric
                            all_kodes = db.query(DBKodePosisi.kode).all()
                            max_kode = 0
                            for k in all_kodes:
                                if k[0]:
                                    # Extract numeric dari kode
                                    num = re.search(r'(\d+)', str(k[0]))
                                    if num:
                                        max_kode = max(max_kode, int(num.group(1)))
                            
                            new_kode = max_kode + 1
                            
                            new_position = DBKodePosisi(
                                kode=str(new_kode),
                                position=position,
                                location=location,
                                business_unit=business_unit,
                                division_chris=division,
                                department_chris=department,
                                user_manager=user_manager,
                                indirect_user=indirect_user,
                                directorate=directorate,
                                year=year
                            )
                            db.add(new_position)
                            db.commit()
                            
                            st.success(f"✅ Position berhasil ditambahkan!")
                            st.info(f"📋 Kode: {new_kode} | Position: {position}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            db.rollback()
    
    # ============================================================
    # EDIT / DELETE POSITION
    # ============================================================
    if total > 0 and admin:
        st.markdown("---")
        st.markdown("### ✏️ Edit / Hapus Position")
        
        # Pilih position untuk edit
        pos_options = {}
        for _, row in df.iterrows():
            pos = row.get('position', '')
            bu = row.get('business_unit', '')
            loc = row.get('location', '')
            display = f"{pos} | {bu} | {loc}" if loc else f"{pos} | {bu}"
            pos_options[display] = row.get('id')
        
        selected_display = st.selectbox(
            "Pilih Position untuk diedit",
            list(pos_options.keys())
        )
        
        if selected_display:
            selected_id = pos_options[selected_display]
            detail = db.query(DBKodePosisi).filter(DBKodePosisi.id == selected_id).first()
            
            if detail:
                with st.form("edit_position_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_kode = st.text_input("Kode", value=detail.kode or "", disabled=True)
                        edit_position = st.text_input("Position", value=detail.position or "")
                        edit_location = st.text_input("Location", value=detail.location or "")
                        edit_business_unit = st.selectbox("Business Unit", [""] + bu_options,
                                                           index=bu_options.index(detail.business_unit) + 1 if detail.business_unit in bu_options else 0)
                        edit_directorate = st.selectbox("Directorate", [""] + direktorat_options,
                                                        index=direktorat_options.index(detail.directorate) + 1 if detail.directorate in direktorat_options else 0)
                    
                    with col2:
                        edit_division = st.text_input("Division CHRIS", value=detail.division_chris or "")
                        edit_department = st.text_input("Department CHRIS", value=detail.department_chris or "")
                        edit_user_manager = st.text_input("User (Manager)", value=detail.user_manager or "")
                        edit_indirect_user = st.text_input("Indirect User", value=detail.indirect_user or "")
                        edit_year = st.number_input("Year", min_value=2000, max_value=2100, value=detail.year or datetime.now().year)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        update_btn = st.form_submit_button("💾 Update Position", type="primary")
                    with col2:
                        delete_btn = st.form_submit_button("🗑️ Hapus Position", type="secondary")
                    
                    if update_btn:
                        if not edit_position:
                            st.error("❌ Position wajib diisi!")
                        else:
                            try:
                                detail.position = edit_position
                                detail.location = edit_location
                                detail.business_unit = edit_business_unit
                                detail.directorate = edit_directorate
                                detail.division_chris = edit_division
                                detail.department_chris = edit_department
                                detail.user_manager = edit_user_manager
                                detail.indirect_user = edit_indirect_user
                                detail.year = edit_year
                                db.commit()
                                st.success("✅ Position berhasil diupdate!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                db.rollback()
                    
                    if delete_btn:
                        confirm = st.warning(f"Yakin ingin menghapus position '{detail.position}'?")
                        if st.button("Ya, Hapus", key="confirm_delete_position"):
                            db.delete(detail)
                            db.commit()
                            st.success("🗑️ Position berhasil dihapus!")
                            st.rerun()
    
    # ============================================================
    # BULK UPDATE FROM FPTK (Mirip VBA Compile_DB_Kode_Posisi)
    # ============================================================
    if admin:
        st.markdown("---")
        st.markdown("### 🔄 Sync dari FPTK")
        st.caption("Ambil data Position, BU, Division, Department dari FPTK yang sudah di-compile.")
        
        if st.button("🚀 Sync dari FPTK", type="primary"):
            with st.spinner("Memproses sync dari FPTK..."):
                try:
                    # Ambil semua FPTK yang punya posisi
                    fptk_data = db.query(FPTK).filter(FPTK.posisi.isnot(None)).all()
                    
                    if not fptk_data:
                        st.warning("Tidak ada data FPTK untuk di-sync.")
                    else:
                        # Group by posisi + bu + lokasi
                        position_map = {}
                        for f in fptk_data:
                            key = f"{f.posisi}|{f.business_unit}|{f.lokasi_kerja or ''}"
                            if key not in position_map:
                                position_map[key] = {
                                    "position": f.posisi,
                                    "business_unit": f.business_unit,
                                    "location": f.lokasi_kerja or "",
                                    "division": f.divisi or "",
                                    "department": f.department or "",
                                    "directorate": f.direktorat or "",
                                    "user_manager": f.user_manager or "",
                                    "indirect_user": f.indirect_user or "",
                                }
                        
                        # Insert/Update ke DB Kode Posisi
                        added = 0
                        updated = 0
                        
                        for key, data in position_map.items():
                            existing = db.query(DBKodePosisi).filter(
                                DBKodePosisi.position == data["position"],
                                DBKodePosisi.business_unit == data["business_unit"],
                                DBKodePosisi.location == data["location"]
                            ).first()
                            
                            if existing:
                                # Update
                                existing.division_chris = data["division"] or existing.division_chris
                                existing.department_chris = data["department"] or existing.department_chris
                                existing.directorate = data["directorate"] or existing.directorate
                                existing.user_manager = data["user_manager"] or existing.user_manager
                                existing.indirect_user = data["indirect_user"] or existing.indirect_user
                                updated += 1
                            else:
                                # Insert
                                # Generate kode
                                all_kodes = db.query(DBKodePosisi.kode).all()
                                max_kode = 0
                                for k in all_kodes:
                                    if k[0]:
                                        num = re.search(r'(\d+)', str(k[0]))
                                        if num:
                                            max_kode = max(max_kode, int(num.group(1)))
                                
                                new_position = DBKodePosisi(
                                    kode=str(max_kode + 1),
                                    position=data["position"],
                                    location=data["location"],
                                    business_unit=data["business_unit"],
                                    division_chris=data["division"],
                                    department_chris=data["department"],
                                    user_manager=data["user_manager"],
                                    indirect_user=data["indirect_user"],
                                    directorate=data["directorate"],
                                    year=datetime.now().year
                                )
                                db.add(new_position)
                                added += 1
                        
                        db.commit()
                        st.success(f"✅ Sync selesai! Added: {added}, Updated: {updated}")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    db.rollback()
    
    # ============================================================
    # EXPORT
    # ============================================================
    if total > 0:
        st.markdown("---")
        if st.button("📥 Export CSV"):
            df_export = pd.read_sql(query.statement, db.bind)
            csv = df_export.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                f"db_kode_posisi_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
