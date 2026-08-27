import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
import os
import tempfile
from core.models import (
    User, UploadCycle, UploadStatus, UploadLog,
    FPTK, DBKodePosisi, DBSourcing, MasterDropdown,
    Blacklist, AuditLog, Evidence
)


def export_database_to_excel(db: Session, filename: str = None) -> str:
    """
    Export semua data dari database ke Excel dengan format yang sesuai
    dengan file Master - Database FIX (1).xlsx
    
    Returns:
        str: Path ke file Excel yang dihasilkan
    """
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Master_Database_Export_{timestamp}.xlsx"
    
    # Pastikan direktori export ada
    export_dir = "exports"
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    
    filepath = os.path.join(export_dir, filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        
        # ============================================================
        # 1. SHEET: Blacklist Candidate
        # ============================================================
        blacklist_data = db.query(Blacklist).all()
        
        blacklist_rows = []
        for idx, item in enumerate(blacklist_data, 1):
            # Parse key_value dengan format: "Nama|Posisi|Lokasi|BU|Kategori|Alasan|PIC"
            parts = item.key_value.split('|') if item.key_value else []
            
            blacklist_rows.append({
                'No': idx,
                'Last Update': item.created_at,
                'Business Unit': parts[0] if len(parts) > 0 else '',
                'Posisi': parts[1] if len(parts) > 1 else '',
                'Lokasi': parts[2] if len(parts) > 2 else '',
                'Nama Kandidat': parts[3] if len(parts) > 3 else '',
                'Kategori': parts[4] if len(parts) > 4 else '',
                'Alasan Tidak Proceed': parts[5] if len(parts) > 5 else '',
                'PIC Rekruter': parts[6] if len(parts) > 6 else ''
            })
        
        df_blacklist = pd.DataFrame(blacklist_rows)
        df_blacklist.to_excel(writer, sheet_name='Blacklist Candidate', index=False)
        
        # ============================================================
        # 2. SHEET: DB Kode Posisi
        # ============================================================
        db_kode_data = db.query(DBKodePosisi).all()
        
        db_kode_rows = []
        for item in db_kode_data:
            db_kode_rows.append({
                'KODE_ANGKA': item.kode,
                'POSISI_KEBUTUHAN_TA': item.position,
                'LOKASI_ONBOARDING': item.location,
                'BUSINESS UNIT': item.business_unit,
                'DIVISI_SESUAI_SO': item.division_chris,
                'DEPARTMENT': item.department_chris,
                'USER (MANAGER)': item.user_manager,
                'INDIRECT USER': item.indirect_user,
                'DIREKTORAT': item.directorate,
                'YEAR': item.year
            })
        
        df_db_kode = pd.DataFrame(db_kode_rows)
        df_db_kode.to_excel(writer, sheet_name='DB Kode Posisi', index=False)
        
        # ============================================================
        # 3. SHEET: FPTK
        # ============================================================
        fptk_data = db.query(FPTK).all()
        
        fptk_rows = []
        for item in fptk_data:
            fptk_rows.append({
                'Kode PIC': item.kode_pic,
                'FPTK Date (Real)': item.fptk_date_real,
                'Kode Angka': item.kode_angka,
                'FPTK Date (Kode)': item.fptk_date_kode,
                'Kode Unik': item.kode_unik,
                'Posisi': item.posisi,
                'Business Unit': item.business_unit,
                'Direktorat': item.direktorat,
                'Divisi': item.divisi,
                'Department': item.department,
                'Level FPTK': item.level_fptk,
                'Level Number': item.level_number,
                'Alasan Permintaan FPTK': item.alasan_permintaan_fptk,
                'Category FPTK': item.category_fptk,
                'PIC Recruiter': item.pic_recruiter,
                'Filter Kategorisasi FPTK': item.filter_kategorisasi_fptk,
                'Vacancy': item.vacancy,
                'Status': item.status,
                'Week FPTK Date (Kode)': item.week_fptk_date,
                'Month FPTK Date': item.month_fptk_date,
                'FPTK Cancel Date': item.fptk_cancel_date,
                'Week Cancel Date': item.week_cancel_date,
                'Month Cancel Date': item.month_cancel_date,
                'Offering Date': item.offering_date,
                'Week Offering Date': item.week_offering_date,
                'Month Offering': item.month_offering,
                'Jumlah SLA': item.jumlah_sla,
                'Deadline pemenuhan SLA': item.deadline_sla,
                'Detail SLA': item.detail_sla,
                'Keterangan Lulus SLA': item.keterangan_lulus_sla,
                'Keterangan Tidak Lulus SLA': item.keterangan_tidak_lulus_sla,
                'Keterangan Cancel': item.keterangan_cancel,
                'Nama Kandidat': item.nama_kandidat,
                'Estimasi Join': item.estimasi_join,
                'Kebutuhan Laptop': item.kebutuhan_laptop,
                'Lokasi Onboarding': item.lokasi_onboarding,
                'Tanggal Upload ke Website': item.tanggal_upload_web,
                'User (Manager)': item.user_manager,
                'Indirect User': item.indirect_user,
                'Lokasi Kerja': item.lokasi_kerja,
                'Lokasi HR': item.lokasi_hr,
                'Status Karyawan': item.status_karyawan,
                'Kode BU': item.kode_bu,
                'FPTK Availability': item.fptk_availability,
                'Remark': item.remark,
                'Created At': item.created_at,
                'Last Updated At': item.last_updated_at,
                'Last Compile Action': item.last_compile_action,
                'Source File': item.source_file,
                'is_sto': item.is_sto
            })
        
        df_fptk = pd.DataFrame(fptk_rows)
        df_fptk.to_excel(writer, sheet_name='FPTK', index=False)
        
        # ============================================================
        # 4. SHEET: DB Sourcing
        # ============================================================
        sourcing_data = db.query(DBSourcing).all()
        
        sourcing_rows = []
        for idx, item in enumerate(sourcing_data, 1):
            sourcing_rows.append({
                'No': idx,
                'Kode Unik': item.kode_unik,
                'Posisi': item.posisi,
                'Model Rekrutmen': item.model_rekrutmen,
                'Rekruter': item.rekruter,
                'Sumber Sourcing': item.sumber_sourcing,
                'Nama': item.nama,
                'Nama Universitas/Sekolah (TOP 10)': item.nama_universitas_top10,
                'Nama Universitas/Sekolah Lainnya': item.nama_universitas_lainnya,
                'Jenjang Pendidikan': item.jenjang_pendidikan,
                'Jurusan': item.jurusan,
                'Tahun Lulus': item.tahun_lulus,
                'IPK': float(item.ipk) if item.ipk else None,
                'Skor Bahasa Inggris': item.skor_bahasa_inggris,
                'University Tier': item.university_tier,
                'IPK Tier': item.ipk_tier,
                'Nomor HP': item.nomor_hp,
                'Email': item.email,
                'Domisili': item.domisili,
                'Last Position': item.last_position,
                'Last Tenure': item.last_tenure,
                'Last Company': item.last_company,
                'Total Tenure': item.total_tenure,
                'Berpengalaman di industri FMCG': item.pernah_di_fmcg,
                'Sourcing Freelance': item.sourcing_freelance,
                'Tanggal Sourcing Freelance': item.tanggal_sourcing_freelance,
                'Sourcing HR': item.sourcing_hr,
                'Detail Keterangan Sourcing HR': item.detail_keterangan_sourcing_hr,
                'Tanggal Sourcing': item.tanggal_sourcing,
                'Shortlist CV': item.shortlist_cv,
                'Detail Keterangan Shortlist CV': item.detail_keterangan_shortlist_cv,
                'Tanggal Shortlist CV': item.tanggal_shortlist_cv,
                'Psikotes': item.psikotes,
                'Kode Psikotes': item.kode_psikotes,
                'Detail Keterangan Psikotes': item.detail_keterangan_psikotes,
                'Tanggal Psikotes / Cek psikotes': item.tanggal_psikotes,
                'Nilai Logika': item.nilai_logika,
                'Nilai IQ': item.nilai_iq,
                'Nilai Daya Tangkap': item.nilai_daya_tangkap,
                'Nilai RA': item.nilai_ra,
                'DISC': item.disc,
                'HR Interview': item.hr_interview,
                'Detail Keterangan HR Interview': item.detail_keterangan_hr_interview,
                'Tanggal HR Interview': item.tanggal_hr_interview,
                'Technical Test/ Case Study': item.technical_test_case_study,
                'Detail Keterangan Technical Test/ Case Study': item.detail_keterangan_technical_test,
                'Tanggal Technical Test/ Case Study': item.tanggal_technical_test,
                'Market Visit': item.market_visit,
                'Detail Market Visit': item.detail_market_visit,
                'Tanggal Market Visit': item.tanggal_market_visit,
                'User Interview': item.user_interview,
                'Detail Keterangan User Interview': item.detail_keterangan_user_interview,
                'Tanggal User Interview': item.tanggal_user_interview,
                'Panel Interview': item.panel_interview,
                'Detail Keterangan Panel Interview': item.detail_keterangan_panel_interview,
                'Tanggal Panel Interview': item.tanggal_panel_interview,
                'Reference Check': item.reference_check,
                'Detail Keterangan Reference Check': item.detail_keterangan_reference_check,
                'Tanggal Reference Check': item.tanggal_reference_check,
                'MCU': item.mcu,
                'Detail Keterangan MCU': item.detail_keterangan_mcu,
                'Tanggal MCU': item.tanggal_mcu,
                'Offering': item.offering,
                'Detail Keterangan Offering': item.detail_keterangan_offering,
                'Tanggal Offering': item.tanggal_offering,
                'Notes': item.notes,
                'Day 1': item.day1,
                'Detail Keterangan Day 1': item.detail_keterangan_day1,
                'Tanggal Day 1': item.tanggal_day1,
                'Sourcing Date': item.sourcing_date,
                'Created At': item.created_at,
                'Last Updated At': item.last_updated_at,
                'Last Compile Action': item.last_compile_action,
                'Source File': item.source_file
            })
        
        df_sourcing = pd.DataFrame(sourcing_rows)
        df_sourcing.to_excel(writer, sheet_name='DB Sourcing', index=False)
        
        # ============================================================
        # 5. SHEET: Grafik MPP
        # ============================================================
        # Buat ringkasan data untuk grafik
        fptk_all = db.query(FPTK).all()
        
        # Group by week
        week_stats = {}
        for item in fptk_all:
            week = item.week_fptk_date
            if week is not None:
                if week not in week_stats:
                    week_stats[week] = {
                        'diterima': 0,
                        'closed': 0,
                        'cancel': 0,
                        'op': 0
                    }
                week_stats[week]['diterima'] += 1
                if item.status == 'Closed':
                    week_stats[week]['closed'] += 1
                elif item.status == 'Cancel':
                    week_stats[week]['cancel'] += 1
                elif item.status == 'OP':
                    week_stats[week]['op'] += 1
        
        # Buat rows untuk Grafik MPP
        weeks = list(range(1, 54))
        
        # Row: Jumlah FPTK Diterima (akumulatif)
        diterima_row = ['Jumlah FPTK Diterima']
        cumulative = 0
        for w in weeks:
            count = week_stats.get(w, {}).get('diterima', 0)
            cumulative += count
            diterima_row.append(cumulative if cumulative > 0 else '')
        
        # Row: Jumlah FPTK Diproses
        diproses_row = ['Jumlah FPTK Diproses']
        for w in weeks:
            stats = week_stats.get(w, {})
            val = stats.get('diterima', 0) - stats.get('closed', 0)
            diproses_row.append(val if val > 0 else '')
        
        # Row: Pemenuhan (terima offer)
        pemenuhan_row = ['Pemenuhan (terima offer)']
        cumulative = 0
        for w in weeks:
            count = week_stats.get(w, {}).get('closed', 0)
            cumulative += count
            pemenuhan_row.append(cumulative if cumulative > 0 else '')
        
        # Row: Sisa FPTK
        sisa_row = ['Sisa FPTK']
        for w in weeks:
            stats = week_stats.get(w, {})
            val = stats.get('diterima', 0) - stats.get('closed', 0)
            sisa_row.append(val if val > 0 else '')
        
        # Row: Cancel
        cancel_row = ['Cancel']
        cumulative = 0
        for w in weeks:
            count = week_stats.get(w, {}).get('cancel', 0)
            cumulative += count
            cancel_row.append(cumulative if cumulative > 0 else '')
        
        grafik_rows = [diterima_row, diproses_row, pemenuhan_row, sisa_row, cancel_row]
        df_grafik = pd.DataFrame(grafik_rows)
        df_grafik.to_excel(writer, sheet_name='Grafik MPP', index=False)
        
        # ============================================================
        # 6. SHEET: Recruiter Performance
        # ============================================================
        # Ambil semua recruiter unik
        recruiters = db.query(FPTK.pic_recruiter).distinct().all()
        recruiter_list = [r[0] for r in recruiters if r[0] is not None]
        
        perf_rows = []
        for recruiter in recruiter_list:
            op_count = db.query(FPTK).filter(
                FPTK.pic_recruiter == recruiter,
                FPTK.status == 'OP'
            ).count()
            closed_count = db.query(FPTK).filter(
                FPTK.pic_recruiter == recruiter,
                FPTK.status == 'Closed'
            ).count()
            cancel_count = db.query(FPTK).filter(
                FPTK.pic_recruiter == recruiter,
                FPTK.status == 'Cancel'
            ).count()
            
            # Hitung SLA
            closed_sla = db.query(FPTK).filter(
                FPTK.pic_recruiter == recruiter,
                FPTK.status == 'Closed',
                FPTK.keterangan_lulus_sla.isnot(None)
            ).count()
            
            closed_no_sla = db.query(FPTK).filter(
                FPTK.pic_recruiter == recruiter,
                FPTK.status == 'Closed',
                FPTK.keterangan_tidak_lulus_sla.isnot(None)
            ).count()
            
            op_no_sla = db.query(FPTK).filter(
                FPTK.pic_recruiter == recruiter,
                FPTK.status == 'OP',
                FPTK.keterangan_tidak_lulus_sla.isnot(None)
            ).count()
            
            perf_rows.append({
                'Nama Recruiter': recruiter,
                'Open': op_count,
                'Closed': closed_count,
                'Cancel': cancel_count,
                'Total': op_count + closed_count + cancel_count,
                'Closed Sesuai SLA': closed_sla,
                'Closed Tidak Sesuai SLA': closed_no_sla,
                'OP Lewat SLA': op_no_sla
            })
        
        df_perf = pd.DataFrame(perf_rows)
        df_perf.to_excel(writer, sheet_name='Recruiter Performance', index=False)
        
        # ============================================================
        # 7. SHEET: Master Dropdown
        # ============================================================
        dropdown_data = db.query(MasterDropdown).all()
        
        dropdown_rows = []
        for item in dropdown_data:
            dropdown_rows.append({
                'kode_pic': item.kode_pic,
                'bu': item.bu,
                'alasan': item.alasan,
                'category_fptk': item.category_fptk,
                'pic_recruiter': item.pic_recruiter,
                'filter_fptk': item.filter_fptk,
                'status': item.status,
                'lokasi_onboarding': item.lokasi_onboarding,
                'detail_sla': item.detail_sla,
                'keterangan_0': item.keterangan_0,
                'keterangan_1': item.keterangan_1,
                'keterangan_cancel': item.keterangan_cancel,
                'nama_direktorat': item.nama_direktorat,
                'model': item.model,
                'sumber_sourcing': item.sumber_sourcing,
                'jenjang_pendidikan': item.jenjang_pendidikan,
                'nama_universitas_top10': item.nama_universitas_top10,
                'jurusan': item.jurusan,
                'university_tier': item.university_tier,
                'ipk_tier': item.ipk_tier,
                'is_active': item.is_active
            })
        
        df_dropdown = pd.DataFrame(dropdown_rows)
        df_dropdown.to_excel(writer, sheet_name='Master Dropdown', index=False)
        
        # ============================================================
        # 8. SHEET: Evidence
        # ============================================================
        evidence_data = db.query(Evidence).all()
        
        evidence_rows = []
        for item in evidence_data:
            evidence_rows.append({
                'kode_unik': item.kode_unik,
                'posisi': item.posisi,
                'tanggal': item.tanggal,
                'file_name': item.file_name,
                'file_path': item.file_path,
                'file_size': item.file_size,
                'total_cv': item.total_cv,
                'pic_recruiter': item.pic_recruiter,
                'created_at': item.created_at
            })
        
        df_evidence = pd.DataFrame(evidence_rows)
        df_evidence.to_excel(writer, sheet_name='Evidence', index=False)
    
    return filepath


def export_single_sheet(db: Session, sheet_name: str) -> pd.DataFrame:
    """
    Export single sheet untuk preview atau download terpisah
    """
    if sheet_name == "Blacklist Candidate":
        data = db.query(Blacklist).all()
        rows = []
        for idx, item in enumerate(data, 1):
            parts = item.key_value.split('|') if item.key_value else []
            rows.append({
                'No': idx,
                'Last Update': item.created_at,
                'Business Unit': parts[0] if len(parts) > 0 else '',
                'Posisi': parts[1] if len(parts) > 1 else '',
                'Lokasi': parts[2] if len(parts) > 2 else '',
                'Nama Kandidat': parts[3] if len(parts) > 3 else '',
                'Kategori': parts[4] if len(parts) > 4 else '',
                'Alasan Tidak Proceed': parts[5] if len(parts) > 5 else '',
                'PIC Rekruter': parts[6] if len(parts) > 6 else ''
            })
        return pd.DataFrame(rows)
    
    elif sheet_name == "DB Kode Posisi":
        data = db.query(DBKodePosisi).all()
        rows = []
        for item in data:
            rows.append({
                'KODE_ANGKA': item.kode,
                'POSISI_KEBUTUHAN_TA': item.position,
                'LOKASI_ONBOARDING': item.location,
                'BUSINESS UNIT': item.business_unit,
                'DIVISI_SESUAI_SO': item.division_chris,
                'DEPARTMENT': item.department_chris,
                'USER (MANAGER)': item.user_manager,
                'INDIRECT USER': item.indirect_user,
                'DIREKTORAT': item.directorate,
                'YEAR': item.year
            })
        return pd.DataFrame(rows)
    
    elif sheet_name == "FPTK":
        data = db.query(FPTK).all()
        rows = []
        for item in data:
            rows.append({
                'Kode PIC': item.kode_pic,
                'FPTK Date (Real)': item.fptk_date_real,
                'Kode Angka': item.kode_angka,
                'FPTK Date (Kode)': item.fptk_date_kode,
                'Kode Unik': item.kode_unik,
                'Posisi': item.posisi,
                'Business Unit': item.business_unit,
                'Direktorat': item.direktorat,
                'Divisi': item.divisi,
                'Department': item.department,
                'Level FPTK': item.level_fptk,
                'Level Number': item.level_number,
                'Alasan Permintaan FPTK': item.alasan_permintaan_fptk,
                'Category FPTK': item.category_fptk,
                'PIC Recruiter': item.pic_recruiter,
                'Filter Kategorisasi FPTK': item.filter_kategorisasi_fptk,
                'Vacancy': item.vacancy,
                'Status': item.status,
                'Week FPTK Date (Kode)': item.week_fptk_date,
                'Month FPTK Date': item.month_fptk_date,
                'FPTK Cancel Date': item.fptk_cancel_date,
                'Week Cancel Date': item.week_cancel_date,
                'Month Cancel Date': item.month_cancel_date,
                'Offering Date': item.offering_date,
                'Week Offering Date': item.week_offering_date,
                'Month Offering': item.month_offering,
                'Jumlah SLA': item.jumlah_sla,
                'Deadline pemenuhan SLA': item.deadline_sla,
                'Detail SLA': item.detail_sla,
                'Keterangan Lulus SLA': item.keterangan_lulus_sla,
                'Keterangan Tidak Lulus SLA': item.keterangan_tidak_lulus_sla,
                'Keterangan Cancel': item.keterangan_cancel,
                'Nama Kandidat': item.nama_kandidat,
                'Estimasi Join': item.estimasi_join,
                'Kebutuhan Laptop': item.kebutuhan_laptop,
                'Lokasi Onboarding': item.lokasi_onboarding,
                'Tanggal Upload ke Website': item.tanggal_upload_web,
                'User (Manager)': item.user_manager,
                'Indirect User': item.indirect_user,
                'Lokasi Kerja': item.lokasi_kerja,
                'Lokasi HR': item.lokasi_hr,
                'Status Karyawan': item.status_karyawan,
                'Kode BU': item.kode_bu,
                'FPTK Availability': item.fptk_availability,
                'Remark': item.remark,
                'Created At': item.created_at,
                'Last Updated At': item.last_updated_at,
                'Last Compile Action': item.last_compile_action,
                'Source File': item.source_file,
                'is_sto': item.is_sto
            })
        return pd.DataFrame(rows)
    
    elif sheet_name == "DB Sourcing":
        data = db.query(DBSourcing).all()
        rows = []
        for idx, item in enumerate(data, 1):
            rows.append({
                'No': idx,
                'Kode Unik': item.kode_unik,
                'Posisi': item.posisi,
                'Model Rekrutmen': item.model_rekrutmen,
                'Rekruter': item.rekruter,
                'Sumber Sourcing': item.sumber_sourcing,
                'Nama': item.nama,
                'Nama Universitas/Sekolah (TOP 10)': item.nama_universitas_top10,
                'Nama Universitas/Sekolah Lainnya': item.nama_universitas_lainnya,
                'Jenjang Pendidikan': item.jenjang_pendidikan,
                'Jurusan': item.jurusan,
                'Tahun Lulus': item.tahun_lulus,
                'IPK': float(item.ipk) if item.ipk else None,
                'Skor Bahasa Inggris': item.skor_bahasa_inggris,
                'University Tier': item.university_tier,
                'IPK Tier': item.ipk_tier,
                'Nomor HP': item.nomor_hp,
                'Email': item.email,
                'Domisili': item.domisili,
                'Last Position': item.last_position,
                'Last Tenure': item.last_tenure,
                'Last Company': item.last_company,
                'Total Tenure': item.total_tenure,
                'Berpengalaman di industri FMCG': item.pernah_di_fmcg,
                'Sourcing Freelance': item.sourcing_freelance,
                'Tanggal Sourcing Freelance': item.tanggal_sourcing_freelance,
                'Sourcing HR': item.sourcing_hr,
                'Detail Keterangan Sourcing HR': item.detail_keterangan_sourcing_hr,
                'Tanggal Sourcing': item.tanggal_sourcing,
                'Shortlist CV': item.shortlist_cv,
                'Detail Keterangan Shortlist CV': item.detail_keterangan_shortlist_cv,
                'Tanggal Shortlist CV': item.tanggal_shortlist_cv,
                'Psikotes': item.psikotes,
                'Kode Psikotes': item.kode_psikotes,
                'Detail Keterangan Psikotes': item.detail_keterangan_psikotes,
                'Tanggal Psikotes / Cek psikotes': item.tanggal_psikotes,
                'Nilai Logika': item.nilai_logika,
                'Nilai IQ': item.nilai_iq,
                'Nilai Daya Tangkap': item.nilai_daya_tangkap,
                'Nilai RA': item.nilai_ra,
                'DISC': item.disc,
                'HR Interview': item.hr_interview,
                'Detail Keterangan HR Interview': item.detail_keterangan_hr_interview,
                'Tanggal HR Interview': item.tanggal_hr_interview,
                'Technical Test/ Case Study': item.technical_test_case_study,
                'Detail Keterangan Technical Test/ Case Study': item.detail_keterangan_technical_test,
                'Tanggal Technical Test/ Case Study': item.tanggal_technical_test,
                'Market Visit': item.market_visit,
                'Detail Market Visit': item.detail_market_visit,
                'Tanggal Market Visit': item.tanggal_market_visit,
                'User Interview': item.user_interview,
                'Detail Keterangan User Interview': item.detail_keterangan_user_interview,
                'Tanggal User Interview': item.tanggal_user_interview,
                'Panel Interview': item.panel_interview,
                'Detail Keterangan Panel Interview': item.detail_keterangan_panel_interview,
                'Tanggal Panel Interview': item.tanggal_panel_interview,
                'Reference Check': item.reference_check,
                'Detail Keterangan Reference Check': item.detail_keterangan_reference_check,
                'Tanggal Reference Check': item.tanggal_reference_check,
                'MCU': item.mcu,
                'Detail Keterangan MCU': item.detail_keterangan_mcu,
                'Tanggal MCU': item.tanggal_mcu,
                'Offering': item.offering,
                'Detail Keterangan Offering': item.detail_keterangan_offering,
                'Tanggal Offering': item.tanggal_offering,
                'Notes': item.notes,
                'Day 1': item.day1,
                'Detail Keterangan Day 1': item.detail_keterangan_day1,
                'Tanggal Day 1': item.tanggal_day1,
                'Sourcing Date': item.sourcing_date,
                'Created At': item.created_at,
                'Last Updated At': item.last_updated_at,
                'Last Compile Action': item.last_compile_action,
                'Source File': item.source_file
            })
        return pd.DataFrame(rows)
    
    elif sheet_name == "Master Dropdown":
        data = db.query(MasterDropdown).all()
        rows = []
        for item in data:
            rows.append({
                'kode_pic': item.kode_pic,
                'bu': item.bu,
                'alasan': item.alasan,
                'category_fptk': item.category_fptk,
                'pic_recruiter': item.pic_recruiter,
                'filter_fptk': item.filter_fptk,
                'status': item.status,
                'lokasi_onboarding': item.lokasi_onboarding,
                'detail_sla': item.detail_sla,
                'keterangan_0': item.keterangan_0,
                'keterangan_1': item.keterangan_1,
                'keterangan_cancel': item.keterangan_cancel,
                'nama_direktorat': item.nama_direktorat,
                'model': item.model,
                'sumber_sourcing': item.sumber_sourcing,
                'jenjang_pendidikan': item.jenjang_pendidikan,
                'nama_universitas_top10': item.nama_universitas_top10,
                'jurusan': item.jurusan,
                'university_tier': item.university_tier,
                'ipk_tier': item.ipk_tier,
                'is_active': item.is_active
            })
        return pd.DataFrame(rows)
    
    elif sheet_name == "Evidence":
        data = db.query(Evidence).all()
        rows = []
        for item in data:
            rows.append({
                'kode_unik': item.kode_unik,
                'posisi': item.posisi,
                'tanggal': item.tanggal,
                'file_name': item.file_name,
                'file_path': item.file_path,
                'file_size': item.file_size,
                'total_cv': item.total_cv,
                'pic_recruiter': item.pic_recruiter,
                'created_at': item.created_at
            })
        return pd.DataFrame(rows)
    
    else:
        return pd.DataFrame()
