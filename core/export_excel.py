# core/export_excel.py
"""
Export database tables to a multi-sheet Excel workbook.
"""

import io
import pandas as pd
from datetime import datetime, date
from decimal import Decimal

from core.models import (
    User, UploadCycle, UploadStatus, UploadLog,
    FPTK, DBKodePosisi, DBSourcing, MasterDropdown,
    Blacklist, AuditLog, Evidence, UploadTemplate,
    TransferHistory, FPTKDeleteRequest, SourcingDeleteRequest,
    BlacklistRequest, CandidateTransfer, CVAttachment,
    RecruitmentProgress,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe(value):
    """Convert non-JSON/Excel-friendly values to serializable equivalents."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value
    if isinstance(value, (dict, list)):
        return str(value)
    return value


def _rows_to_df(items, columns):
    """Build a DataFrame from ORM objects given a list of (col_name, attr_name)."""
    data = []
    for item in items:
        row = {}
        for col, attr in columns:
            row[col] = _safe(getattr(item, attr, None))
        data.append(row)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------
def _build_users_df(db):
    items = db.query(User).all()
    cols = [
        ('id', 'id'), ('username', 'username'), ('role', 'role'),
        ('business_unit', 'business_unit'), ('kode_pic', 'kode_pic'),
        ('pic_recruiter', 'pic_recruiter'), ('display_name', 'display_name'),
        ('created_at', 'created_at'), ('last_login', 'last_login'),
    ]
    return _rows_to_df(items, cols)


def _build_upload_cycles_df(db):
    items = db.query(UploadCycle).all()
    cols = [
        ('id', 'id'), ('cycle_name', 'cycle_name'),
        ('created_by', 'created_by'), ('created_at', 'created_at'),
        ('started_at', 'started_at'), ('ended_at', 'ended_at'),
    ]
    return _rows_to_df(items, cols)


def _build_upload_status_df(db):
    items = db.query(UploadStatus).all()
    cols = [
        ('id', 'id'), ('cycle_id', 'cycle_id'), ('user_id', 'user_id'),
        ('status', 'status'), ('first_compile_at', 'first_compile_at'),
        ('done_at', 'done_at'),
    ]
    return _rows_to_df(items, cols)


def _build_upload_logs_df(db):
    items = db.query(UploadLog).all()
    cols = [
        ('id', 'id'), ('cycle_id', 'cycle_id'), ('user_id', 'user_id'),
        ('file_name', 'file_name'), ('file_size_bytes', 'file_size_bytes'),
        ('file_hash', 'file_hash'), ('status', 'status'),
        ('record_count', 'record_count'), ('error_details', 'error_details'),
        ('uploaded_at', 'uploaded_at'),
    ]
    return _rows_to_df(items, cols)


def _build_fptk_df(db):
    items = db.query(FPTK).all()
    cols = [
        ('id', 'id'), ('kode_unik', 'kode_unik'), ('posisi', 'posisi'),
        ('kode_pic', 'kode_pic'), ('fptk_date_real', 'fptk_date_real'),
        ('fptk_date_kode', 'fptk_date_kode'), ('kode_angka', 'kode_angka'),
        ('business_unit', 'business_unit'), ('direktorat', 'direktorat'),
        ('divisi', 'divisi'), ('department', 'department'),
        ('level_fptk', 'level_fptk'), ('level_number', 'level_number'),
        ('alasan_permintaan_fptk', 'alasan_permintaan_fptk'),
        ('category_fptk', 'category_fptk'), ('pic_recruiter', 'pic_recruiter'),
        ('filter_kategorisasi_fptk', 'filter_kategorisasi_fptk'),
        ('vacancy', 'vacancy'), ('status', 'status'),
        ('week_fptk_date', 'week_fptk_date'),
        ('month_fptk_date', 'month_fptk_date'),
        ('fptk_cancel_date', 'fptk_cancel_date'),
        ('week_cancel_date', 'week_cancel_date'),
        ('month_cancel_date', 'month_cancel_date'),
        ('offering_date', 'offering_date'),
        ('week_offering_date', 'week_offering_date'),
        ('month_offering', 'month_offering'),
        ('jumlah_sla', 'jumlah_sla'), ('deadline_sla', 'deadline_sla'),
        ('detail_sla', 'detail_sla'),
        ('keterangan_lulus_sla', 'keterangan_lulus_sla'),
        ('keterangan_tidak_lulus_sla', 'keterangan_tidak_lulus_sla'),
        ('keterangan_cancel', 'keterangan_cancel'),
        ('nama_kandidat', 'nama_kandidat'),
        ('estimasi_join', 'estimasi_join'),
        ('kebutuhan_laptop', 'kebutuhan_laptop'),
        ('lokasi_onboarding', 'lokasi_onboarding'),
        ('tanggal_upload_web', 'tanggal_upload_web'),
        ('user_manager', 'user_manager'), ('indirect_user', 'indirect_user'),
        ('lokasi_kerja', 'lokasi_kerja'), ('lokasi_hr', 'lokasi_hr'),
        ('status_karyawan', 'status_karyawan'), ('kode_bu', 'kode_bu'),
        ('fptk_availability', 'fptk_availability'), ('remark', 'remark'),
        ('created_at', 'created_at'), ('last_updated_at', 'last_updated_at'),
        ('last_compile_action', 'last_compile_action'),
        ('source_file', 'source_file'),
        ('source_file_hash', 'source_file_hash'),
        ('source_user_id', 'source_user_id'),
        ('source_cycle_id', 'source_cycle_id'), ('is_sto', 'is_sto'),
    ]
    return _rows_to_df(items, cols)


def _build_db_kode_posisi_df(db):
    items = db.query(DBKodePosisi).all()
    cols = [
        ('id', 'id'), ('kode', 'kode'), ('position', 'position'),
        ('location', 'location'), ('business_unit', 'business_unit'),
        ('division_chris', 'division_chris'),
        ('department_chris', 'department_chris'),
        ('user_manager', 'user_manager'), ('indirect_user', 'indirect_user'),
        ('directorate', 'directorate'), ('year', 'year'),
    ]
    return _rows_to_df(items, cols)


def _build_db_sourcing_df(db):
    items = db.query(DBSourcing).all()
    cols = [
        ('id', 'id'), ('no', 'no'), ('sourcing_date', 'sourcing_date'),
        ('kode_unik', 'kode_unik'), ('posisi', 'posisi'),
        ('model_rekrutmen', 'model_rekrutmen'), ('rekruter', 'rekruter'),
        ('sumber_sourcing', 'sumber_sourcing'), ('nama', 'nama'),
        ('nama_universitas_top10', 'nama_universitas_top10'),
        ('nama_universitas_lainnya', 'nama_universitas_lainnya'),
        ('jenjang_pendidikan', 'jenjang_pendidikan'),
        ('jurusan', 'jurusan'), ('jurusan_lainnya', 'jurusan_lainnya'),
        ('tahun_lulus', 'tahun_lulus'), ('ipk', 'ipk'),
        ('skor_bahasa_inggris', 'skor_bahasa_inggris'),
        ('university_tier', 'university_tier'), ('ipk_tier', 'ipk_tier'),
        ('nomor_hp', 'nomor_hp'), ('email', 'email'),
        ('domisili', 'domisili'), ('last_position', 'last_position'),
        ('last_tenure', 'last_tenure'), ('last_company', 'last_company'),
        ('total_tenure', 'total_tenure'),
        ('pernah_di_fmcg', 'pernah_di_fmcg'),
        ('sourcing_freelance', 'sourcing_freelance'),
        ('tanggal_sourcing_freelance', 'tanggal_sourcing_freelance'),
        ('sourcing_hr', 'sourcing_hr'),
        ('detail_keterangan_sourcing_hr', 'detail_keterangan_sourcing_hr'),
        ('tanggal_sourcing', 'tanggal_sourcing'),
        ('shortlist_cv', 'shortlist_cv'),
        ('detail_keterangan_shortlist_cv', 'detail_keterangan_shortlist_cv'),
        ('tanggal_shortlist_cv', 'tanggal_shortlist_cv'),
        ('psikotes', 'psikotes'), ('kode_psikotes', 'kode_psikotes'),
        ('detail_keterangan_psikotes', 'detail_keterangan_psikotes'),
        ('tanggal_psikotes', 'tanggal_psikotes'),
        ('nilai_logika', 'nilai_logika'), ('nilai_iq', 'nilai_iq'),
        ('nilai_daya_tangkap', 'nilai_daya_tangkap'),
        ('nilai_ra', 'nilai_ra'), ('disc', 'disc'),
        ('hr_interview', 'hr_interview'),
        ('detail_keterangan_hr_interview', 'detail_keterangan_hr_interview'),
        ('tanggal_hr_interview', 'tanggal_hr_interview'),
        ('technical_test_case_study', 'technical_test_case_study'),
        ('detail_keterangan_technical_test', 'detail_keterangan_technical_test'),
        ('tanggal_technical_test', 'tanggal_technical_test'),
        ('market_visit', 'market_visit'),
        ('detail_market_visit', 'detail_market_visit'),
        ('tanggal_market_visit', 'tanggal_market_visit'),
        ('user_interview', 'user_interview'),
        ('detail_keterangan_user_interview', 'detail_keterangan_user_interview'),
        ('tanggal_user_interview', 'tanggal_user_interview'),
        ('panel_interview', 'panel_interview'),
        ('detail_keterangan_panel_interview', 'detail_keterangan_panel_interview'),
        ('tanggal_panel_interview', 'tanggal_panel_interview'),
        ('reference_check', 'reference_check'),
        ('detail_keterangan_reference_check', 'detail_keterangan_reference_check'),
        ('tanggal_reference_check', 'tanggal_reference_check'),
        ('mcu', 'mcu'), ('detail_keterangan_mcu', 'detail_keterangan_mcu'),
        ('tanggal_mcu', 'tanggal_mcu'),
        ('offering', 'offering'),
        ('detail_keterangan_offering', 'detail_keterangan_offering'),
        ('tanggal_offering', 'tanggal_offering'),
        ('notes', 'notes'), ('day1', 'day1'),
        ('detail_keterangan_day1', 'detail_keterangan_day1'),
        ('tanggal_day1', 'tanggal_day1'),
        ('is_blacklisted', 'is_blacklisted'),
        ('blacklisted_at', 'blacklisted_at'),
        ('blacklisted_by', 'blacklisted_by'),
        ('blacklist_reason', 'blacklist_reason'),
        ('created_at', 'created_at'), ('last_updated_at', 'last_updated_at'),
        ('last_compile_action', 'last_compile_action'),
        ('source_file', 'source_file'),
        ('source_file_hash', 'source_file_hash'),
        ('source_user_id', 'source_user_id'),
        ('source_cycle_id', 'source_cycle_id'),
    ]
    return _rows_to_df(items, cols)


def _build_master_dropdown_df(db):
    items = db.query(MasterDropdown).all()
    cols = [
        ('id', 'id'), ('kode_pic', 'kode_pic'), ('bu', 'bu'),
        ('alasan', 'alasan'), ('category_fptk', 'category_fptk'),
        ('pic_recruiter', 'pic_recruiter'), ('filter_fptk', 'filter_fptk'),
        ('status', 'status'), ('lokasi_onboarding', 'lokasi_onboarding'),
        ('detail_sla', 'detail_sla'), ('keterangan_0', 'keterangan_0'),
        ('keterangan_1', 'keterangan_1'),
        ('keterangan_cancel', 'keterangan_cancel'),
        ('nama_direktorat', 'nama_direktorat'), ('model', 'model'),
        ('sumber_sourcing', 'sumber_sourcing'),
        ('jenjang_pendidikan', 'jenjang_pendidikan'),
        ('nama_universitas_top10', 'nama_universitas_top10'),
        ('jurusan', 'jurusan'), ('university_tier', 'university_tier'),
        ('ipk_tier', 'ipk_tier'), ('divisi', 'divisi'),
        ('department', 'department'),
        ('keterangan_tidak_lolos_sourcing_1', 'keterangan_tidak_lolos_sourcing_1'),
        ('keterangan_tidak_lolos_sourcing_2', 'keterangan_tidak_lolos_sourcing_2'),
        ('keterangan_tidak_lolos_psikotes', 'keterangan_tidak_lolos_psikotes'),
        ('keterangan_tidak_lolos_hr_interview', 'keterangan_tidak_lolos_hr_interview'),
        ('keterangan_tidak_lolos_user_panel', 'keterangan_tidak_lolos_user_panel'),
        ('keterangan_tidak_lolos_technical_test', 'keterangan_tidak_lolos_technical_test'),
        ('keterangan_tidak_lolos_market_visit', 'keterangan_tidak_lolos_market_visit'),
        ('keterangan_tidak_lolos_reference_check', 'keterangan_tidak_lolos_reference_check'),
        ('keterangan_tidak_menerima_offer', 'keterangan_tidak_menerima_offer'),
        ('keterangan_tidak_lolos_mcu', 'keterangan_tidak_lolos_mcu'),
        ('keterangan_tidak_hadir_day1', 'keterangan_tidak_hadir_day1'),
        ('lokasi_pic_recruiter', 'lokasi_pic_recruiter'),
        ('is_active', 'is_active'),
    ]
    return _rows_to_df(items, cols)


def _build_blacklist_df(db):
    items = db.query(Blacklist).all()
    cols = [
        ('id', 'id'), ('key_value', 'key_value'),
        ('created_at', 'created_at'),
    ]
    return _rows_to_df(items, cols)


def _build_audit_logs_df(db):
    items = db.query(AuditLog).all()
    cols = [
        ('id', 'id'), ('user_id', 'user_id'), ('action', 'action'),
        ('table_name', 'table_name'), ('record_id', 'record_id'),
        ('old_value', 'old_value'), ('new_value', 'new_value'),
        ('ip_address', 'ip_address'), ('user_agent', 'user_agent'),
        ('created_at', 'created_at'),
    ]
    return _rows_to_df(items, cols)


def _build_evidence_df(db):
    """Build Evidence dataframe for export."""
    items = db.query(Evidence).all()
    cols = [
        ('id', 'id'), ('kode_unik', 'kode_unik'), ('posisi', 'posisi'),
        ('tanggal', 'tanggal'), ('file_name', 'file_name'),
        ('file_key', 'file_key'),                     # ← FIXED (was file_path)
        ('file_size', 'file_size'), ('file_type', 'file_type'),
        ('total_cv', 'total_cv'), ('keterangan', 'keterangan'),
        ('pic_recruiter', 'pic_recruiter'), ('user_id', 'user_id'),
        ('created_at', 'created_at'),
    ]
    return _rows_to_df(items, cols)


def _build_upload_templates_df(db):
    """Build UploadTemplate dataframe for export."""
    items = db.query(UploadTemplate).all()
    cols = [
        ('id', 'id'), ('file_name', 'file_name'),
        ('file_key', 'file_key'),                     # ← FIXED (was file_path)
        ('file_type', 'file_type'), ('uploaded_by', 'uploaded_by'),
        ('version', 'version'), ('is_active', 'is_active'),
        ('template_type', 'template_type'),
        ('created_at', 'created_at'),
    ]
    return _rows_to_df(items, cols)


def _build_transfer_history_df(db):
    items = db.query(TransferHistory).all()
    cols = [
        ('id', 'id'), ('fptk_id', 'fptk_id'), ('kode_unik', 'kode_unik'),
        ('posisi', 'posisi'), ('from_pic', 'from_pic'), ('to_pic', 'to_pic'),
        ('reason', 'reason'), ('transferred_by', 'transferred_by'),
        ('transferred_by_name', 'transferred_by_name'),
        ('created_at', 'created_at'),
    ]
    return _rows_to_df(items, cols)


def _build_fptk_delete_requests_df(db):
    items = db.query(FPTKDeleteRequest).all()
    cols = [
        ('id', 'id'), ('fptk_id', 'fptk_id'), ('kode_unik', 'kode_unik'),
        ('posisi', 'posisi'), ('pic_recruiter', 'pic_recruiter'),
        ('reason', 'reason'), ('status', 'status'),
        ('requested_by', 'requested_by'),
        ('requested_by_name', 'requested_by_name'),
        ('requested_at', 'requested_at'), ('reviewed_by', 'reviewed_by'),
        ('reviewed_by_name', 'reviewed_by_name'),
        ('reviewed_at', 'reviewed_at'), ('admin_notes', 'admin_notes'),
    ]
    return _rows_to_df(items, cols)


def _build_sourcing_delete_requests_df(db):
    items = db.query(SourcingDeleteRequest).all()
    cols = [
        ('id', 'id'), ('sourcing_id', 'sourcing_id'),
        ('kode_unik', 'kode_unik'), ('nama', 'nama'), ('posisi', 'posisi'),
        ('pic_recruiter', 'pic_recruiter'), ('reason', 'reason'),
        ('status', 'status'), ('requested_by', 'requested_by'),
        ('requested_by_name', 'requested_by_name'),
        ('requested_at', 'requested_at'), ('reviewed_by', 'reviewed_by'),
        ('reviewed_by_name', 'reviewed_by_name'),
        ('reviewed_at', 'reviewed_at'), ('admin_notes', 'admin_notes'),
    ]
    return _rows_to_df(items, cols)


def _build_blacklist_requests_df(db):
    items = db.query(BlacklistRequest).all()
    cols = [
        ('id', 'id'), ('sourcing_id', 'sourcing_id'),
        ('kode_unik', 'kode_unik'), ('nama', 'nama'), ('posisi', 'posisi'),
        ('action', 'action'), ('reason', 'reason'), ('status', 'status'),
        ('requested_by', 'requested_by'),
        ('requested_by_name', 'requested_by_name'),
        ('requested_at', 'requested_at'), ('reviewed_by', 'reviewed_by'),
        ('reviewed_by_name', 'reviewed_by_name'),
        ('reviewed_at', 'reviewed_at'), ('admin_notes', 'admin_notes'),
    ]
    return _rows_to_df(items, cols)


def _build_candidate_transfers_df(db):
    items = db.query(CandidateTransfer).all()
    cols = [
        ('id', 'id'), ('sourcing_id', 'sourcing_id'),
        ('old_kode_unik', 'old_kode_unik'), ('new_kode_unik', 'new_kode_unik'),
        ('nama', 'nama'), ('posisi', 'posisi'),
        ('old_pipeline_stage', 'old_pipeline_stage'),
        ('new_pipeline_stage', 'new_pipeline_stage'),
        ('reason', 'reason'), ('transferred_by', 'transferred_by'),
        ('transferred_by_name', 'transferred_by_name'),
        ('transferred_at', 'transferred_at'),
    ]
    return _rows_to_df(items, cols)


def _build_cv_attachments_df(db):
    """Build CVAttachment dataframe for export."""
    items = db.query(CVAttachment).all()
    cols = [
        ('id', 'id'), ('sourcing_id', 'sourcing_id'),
        ('kode_unik', 'kode_unik'), ('nama_kandidat', 'nama_kandidat'),
        ('file_name', 'file_name'),
        ('file_key', 'file_key'),                     # ← FIXED (was file_path)
        ('file_size', 'file_size'), ('file_type', 'file_type'),
        ('uploaded_by', 'uploaded_by'),
        ('uploaded_by_name', 'uploaded_by_name'),
        ('created_at', 'created_at'),
    ]
    return _rows_to_df(items, cols)


def _build_recruitment_progress_df(db):
    items = db.query(RecruitmentProgress).all()
    cols = [
        ('id', 'id'), ('fptk_id', 'fptk_id'), ('kode_unik', 'kode_unik'),
        ('posisi', 'posisi'), ('pic_recruiter', 'pic_recruiter'),
        ('week_number', 'week_number'), ('year', 'year'),
        ('week_label', 'week_label'),
        ('progress_this_week', 'progress_this_week'),
        ('next_action', 'next_action'), ('status', 'status'),
        ('created_by', 'created_by'), ('created_by_name', 'created_by_name'),
        ('created_at', 'created_at'), ('updated_at', 'updated_at'),
    ]
    return _rows_to_df(items, cols)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def export_database_to_excel(db):
    """
    Export every table to a separate sheet in a single Excel workbook.
    Returns a BytesIO buffer ready to be passed to st.download_button.
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        _build_users_df(db).to_excel(writer, sheet_name='Users', index=False)
        _build_upload_cycles_df(db).to_excel(writer, sheet_name='UploadCycles', index=False)
        _build_upload_status_df(db).to_excel(writer, sheet_name='UploadStatus', index=False)
        _build_upload_logs_df(db).to_excel(writer, sheet_name='UploadLogs', index=False)
        _build_fptk_df(db).to_excel(writer, sheet_name='FPTK', index=False)
        _build_db_kode_posisi_df(db).to_excel(writer, sheet_name='DBKodePosisi', index=False)
        _build_db_sourcing_df(db).to_excel(writer, sheet_name='DBSourcing', index=False)
        _build_master_dropdown_df(db).to_excel(writer, sheet_name='MasterDropdown', index=False)
        _build_blacklist_df(db).to_excel(writer, sheet_name='Blacklist', index=False)
        _build_audit_logs_df(db).to_excel(writer, sheet_name='AuditLogs', index=False)
        _build_evidence_df(db).to_excel(writer, sheet_name='Evidence', index=False)
        _build_upload_templates_df(db).to_excel(writer, sheet_name='UploadTemplates', index=False)
        _build_transfer_history_df(db).to_excel(writer, sheet_name='TransferHistory', index=False)
        _build_fptk_delete_requests_df(db).to_excel(writer, sheet_name='FPTKDeleteRequests', index=False)
        _build_sourcing_delete_requests_df(db).to_excel(writer, sheet_name='SourcingDeleteRequests', index=False)
        _build_blacklist_requests_df(db).to_excel(writer, sheet_name='BlacklistRequests', index=False)
        _build_candidate_transfers_df(db).to_excel(writer, sheet_name='CandidateTransfers', index=False)
        _build_cv_attachments_df(db).to_excel(writer, sheet_name='CVAttachments', index=False)
        _build_recruitment_progress_df(db).to_excel(writer, sheet_name='RecruitmentProgress', index=False)

    buffer.seek(0)
    return buffer
