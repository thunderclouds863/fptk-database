import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.database import get_db
from core.models import FPTK, MasterDropdown, User
from core.auth import get_current_user
from core.utils import normalize_key, parse_date_dmy, safe_int

def show_fptk_input():
    st.title("📝 Input FPTK Baru")
    st.markdown("Form input manual FPTK (mirip frmInputFPTK di VBA)")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    # ============================================================
    # LOAD MASTER DATA
    # ============================================================
    master = db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
    
    # Extract unique values untuk dropdown
    pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
    kode_pic_options = sorted(set([m.kode_pic for m in master if m.kode_pic]))
    bu_options = sorted(set([m.bu for m in master if m.bu]))
    alasan_options = sorted(set([m.alasan for m in master if m.alasan]))
    category_options = sorted(set([m.category_fptk for m in master if m.category_fptk]))
    direktorat_options = sorted(set([m.nama_direktorat for m in master if m.nama_direktorat]))
    filter_options = sorted(set([m.filter_fptk for m in master if m.filter_fptk]))
    status_options = ["OP", "Closed", "Cancel"]
    
    # ============================================================
    # FORM
    # ============================================================
    with st.form("fptk_input_form", clear_on_submit=True):
        st.markdown("### Data FPTK")
        
        col1, col2 = st.columns(2)
        with col1:
            kode_pic = st.selectbox("Kode PIC", [""] + kode_pic_options)
            kode_unik = st.text_input("Kode Unik", placeholder="Akan di-generate otomatis")
            posisi = st.text_input("Posisi *")
            business_unit = st.selectbox("Business Unit *", [""] + bu_options)
            direktorat = st.selectbox("Direktorat *", [""] + direktorat_options)
            divisi = st.text_input("Divisi *")
            department = st.text_input("Department *")
        
        with col2:
            fptk_date = st.date_input("FPTK Date (Real) *", datetime.now())
            level_fptk = st.text_input("Level FPTK *", placeholder="Contoh: 1A, 2B, 3A")
            level_number = st.number_input("Level Number *", min_value=1, max_value=10, value=1)
            alasan = st.selectbox("Alasan Permintaan FPTK *", [""] + alasan_options)
            category = st.selectbox("Category FPTK *", [""] + category_options)
            pic_recruiter = st.selectbox("PIC Recruiter *", [""] + pic_options)
            vacancy = st.number_input("Vacancy *", min_value=1, value=1)
            status = st.selectbox("Status *", status_options)
        
        # Conditional fields
        if status == "Closed":
            offering_date = st.date_input("Offering Date (required untuk Closed)", datetime.now())
        else:
            offering_date = None
        
        if status == "Cancel":
            cancel_date = st.date_input("FPTK Cancel Date (required untuk Cancel)", datetime.now())
        else:
            cancel_date = None
        
        st.markdown("---")
        st.markdown("### Data Tambahan")
        
        col1, col2 = st.columns(2)
        with col1:
            nama_kandidat = st.text_input("Nama Kandidat")
            lokasi_kerja = st.text_input("Lokasi Kerja")
            lokasi_hr = st.text_input("Lokasi HR")
            user_manager = st.text_input("User (Manager)")
            indirect_user = st.text_input("Indirect User")
            status_karyawan = st.text_input("Status Karyawan")
        with col2:
            estimasi_join = st.date_input("Estimasi Join", value=None)
            kebutuhan_laptop = st.selectbox("Kebutuhan Laptop", ["", "Ya", "Tidak"])
            lokasi_onboarding = st.selectbox("Lokasi Onboarding", [""] + sorted(set([m.lokasi_onboarding for m in master if m.lokasi_onboarding])))
            fptk_availability = st.selectbox("FPTK Availability", ["", "Y", "N"])
            remark = st.text_area("Remark")
        
        st.markdown("---")
        submitted = st.form_submit_button("💾 Simpan FPTK", type="primary")
    
    # ============================================================
    # PROSES SIMPAN
    # ============================================================
    if submitted:
        errors = []
        
        # Validasi
        if not posisi:
            errors.append("Posisi wajib diisi")
        if not business_unit:
            errors.append("Business Unit wajib diisi")
        if not direktorat:
            errors.append("Direktorat wajib diisi")
        if not divisi:
            errors.append("Divisi wajib diisi")
        if not department:
            errors.append("Department wajib diisi")
        if not level_fptk:
            errors.append("Level FPTK wajib diisi")
        if level_number <= 0:
            errors.append("Level Number wajib > 0")
        if not alasan:
            errors.append("Alasan Permintaan FPTK wajib diisi")
        if not category:
            errors.append("Category FPTK wajib diisi")
        if not pic_recruiter:
            errors.append("PIC Recruiter wajib diisi")
        if vacancy <= 0:
            errors.append("Vacancy wajib > 0")
        if not status:
            errors.append("Status wajib diisi")
        if status == "Closed" and not offering_date:
            errors.append("Offering Date wajib diisi jika Status = Closed")
        if status == "Cancel" and not cancel_date:
            errors.append("FPTK Cancel Date wajib diisi jika Status = Cancel")
        
        # Generate Kode Unik jika kosong
        if not kode_unik:
            # Format: KODE PIC + Kode Angka + ddmmyy
            date_code = fptk_date.strftime("%d%m%y")
            kode_angka = kode_pic[:4] if kode_pic else "XXXX"
            kode_unik = f"{kode_pic}{kode_angka}{date_code}" if kode_pic else ""
            if not kode_unik:
                errors.append("Kode Unik tidak bisa di-generate otomatis. Silakan isi Kode PIC terlebih dahulu.")
        
        # Cek duplikat Kode Unik
        if kode_unik:
            existing = db.query(FPTK).filter(FPTK.kode_unik == kode_unik).first()
            if existing:
                errors.append(f"Kode Unik '{kode_unik}' sudah ada di database!")
        
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            try:
                # Hitung SLA
                if level_number <= 3:
                    sla_days = 30
                elif level_number == 4:
                    sla_days = 45
                elif level_number >= 5:
                    sla_days = 60
                else:
                    sla_days = 30
                
                deadline_sla = fptk_date + timedelta(days=sla_days) if fptk_date else None
                week_num = fptk_date.isocalendar()[1] if fptk_date else None
                month_name = fptk_date.strftime("%B") if fptk_date else None
                kode_bu = kode_pic[:4] if kode_pic else ""
                
                # Tentukan filter kategorisasi
                filter_kat = ""
                posisi_lower = posisi.lower()
                if posisi_lower.startswith('cimory') or posisi_lower.startswith('fresh'):
                    filter_kat = 'CLAP FGDP'
                elif level_number in [1, 2]:
                    filter_kat = 'Level 1-2'
                elif level_number == 3:
                    filter_kat = 'Level 3'
                elif level_number == 4:
                    filter_kat = 'Level 4'
                
                # Simpan
                new_fptk = FPTK(
                    kode_unik=kode_unik,
                    posisi=posisi,
                    kode_pic=kode_pic,
                    fptk_date_real=fptk_date,
                    fptk_date_kode=fptk_date,
                    kode_angka=f"{kode_pic}{vacancy}" if kode_pic else "",
                    business_unit=business_unit,
                    direktorat=direktorat,
                    divisi=divisi,
                    department=department,
                    level_fptk=level_fptk,
                    level_number=level_number,
                    alasan_permintaan_fptk=alasan,
                    category_fptk=category,
                    pic_recruiter=pic_recruiter,
                    filter_kategorisasi_fptk=filter_kat,
                    vacancy=vacancy,
                    status=status,
                    offering_date=offering_date,
                    fptk_cancel_date=cancel_date,
                    jumlah_sla=sla_days,
                    deadline_sla=deadline_sla,
                    week_fptk_date=week_num,
                    month_fptk_date=month_name,
                    kode_bu=kode_bu,
                    nama_kandidat=nama_kandidat,
                    lokasi_kerja=lokasi_kerja,
                    lokasi_hr=lokasi_hr,
                    user_manager=user_manager,
                    indirect_user=indirect_user,
                    status_karyawan=status_karyawan,
                    estimasi_join=estimasi_join,
                    kebutuhan_laptop=kebutuhan_laptop,
                    lokasi_onboarding=lokasi_onboarding,
                    fptk_availability=fptk_availability,
                    remark=remark,
                    source_user_id=user.id,
                    created_at=datetime.now(),
                    last_compile_action="MANUAL_INPUT"
                )
                db.add(new_fptk)
                db.commit()
                
                st.success(f"✅ FPTK berhasil disimpan!")
                st.info(f"📋 Kode Unik: **{kode_unik}**")
                st.info(f"📋 Deadline SLA: **{deadline_sla.strftime('%d/%m/%Y') if deadline_sla else '-'}**")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Error menyimpan data: {str(e)}")
                db.rollback()
    
    # ============================================================
    # CARI FPTK EXISTING
    # ============================================================
    st.markdown("---")
    st.subheader("🔍 Cari FPTK Existing")
    
    search = st.text_input("Cari berdasarkan Kode Unik atau Posisi", placeholder="Ketik keyword...")
    if search:
        results = db.query(FPTK).filter(
            (FPTK.kode_unik.ilike(f"%{search}%")) |
            (FPTK.posisi.ilike(f"%{search}%"))
        ).limit(20).all()
        
        if results:
            data = []
            for r in results:
                data.append({
                    "ID": r.id,
                    "Kode Unik": r.kode_unik,
                    "Posisi": r.posisi,
                    "PIC": r.pic_recruiter,
                    "Status": r.status,
                    "Tanggal": r.fptk_date_real.strftime("%d/%m/%Y") if r.fptk_date_real else "-",
                    "BU": r.business_unit
                })
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            
            # Pilih untuk edit
            selected_id = st.selectbox("Pilih ID untuk lihat detail", [r.id for r in results])
            if selected_id:
                detail = db.query(FPTK).filter(FPTK.id == selected_id).first()
                if detail:
                    with st.expander(f"📋 Detail FPTK: {detail.kode_unik}"):
                        st.markdown(f"**Posisi:** {detail.posisi}")
                        st.markdown(f"**PIC:** {detail.pic_recruiter}")
                        st.markdown(f"**Status:** {detail.status}")
                        st.markdown(f"**BU:** {detail.business_unit}")
                        st.markdown(f"**Direktorat:** {detail.direktorat}")
                        st.markdown(f"**Filter Kategorisasi:** {detail.filter_kategorisasi_fptk}")
                        st.markdown(f"**SLA:** {detail.jumlah_sla} hari")
                        st.markdown(f"**Deadline SLA:** {detail.deadline_sla.strftime('%d/%m/%Y') if detail.deadline_sla else '-'}")
                        st.markdown(f"**Created At:** {detail.created_at.strftime('%d/%m/%Y %H:%M') if detail.created_at else '-'}")
        else:
            st.info("Tidak ada data ditemukan")
