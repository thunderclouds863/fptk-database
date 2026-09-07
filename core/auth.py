import bcrypt
import streamlit as st
from sqlalchemy.orm import Session
from core.models import User, AuditLog, MasterDropdown
import datetime
import hashlib
import re

# ============================================================
# BU CODE MAPPING
# ============================================================
BU_CODE_MAPPING = {
    "CMD": {"nama": "PT Cisarua Mountain Dairy, Tbk", "kode": "CMD"},
    "JESS": {"nama": "PT Java Egg Specialities", "kode": "JESS"},
    "MS": {"nama": "PT Macrosentra Niagaboga", "kode": "MS"},
    "MP": {"nama": "PT Macroprima Panganutama", "kode": "MP"},
    "CORP": {"nama": "Corporate", "kode": "CORP"},
}


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if verify_password(password, user.password_hash):
        return user
    return None


def login_user(db: Session, username: str, password: str):
    user = authenticate_user(db, username, password)
    if user:
        user.last_login = datetime.datetime.now()
        db.commit()
        audit = AuditLog(
            user_id=user.id,
            action="LOGIN",
            table_name="users",
            record_id=user.id
        )
        db.add(audit)
        db.commit()
        return user
    return None


def generate_kode_pic(business_unit: str, pic_name: str) -> str:
    """
    Generate Kode PIC dari BU dan Nama PIC
    Format: {BU}{3 huruf pertama nama}
    Contoh: CMD + Elsi → CMDEls
    """
    if not business_unit or not pic_name:
        return ""
    # Ambil 3 huruf pertama dari nama (hanya huruf)
    name_code = re.sub(r'[^A-Za-z]', '', pic_name)[:3].capitalize()
    return f"{business_unit}{name_code}"


def create_user(db: Session, username: str, password: str, role: str = "user",
                pic_recruiter: str = None, display_name: str = None,
                business_unit: str = None, kode_pic: str = None):
    """
    Create new user with BU and Kode PIC support
    """
    if db.query(User).filter(User.username == username).first():
        return None
    if len(password) < 6:
        return None
    
    # Auto-generate kode_pic jika tidak diisi
    if not kode_pic and business_unit and pic_recruiter:
        kode_pic = generate_kode_pic(business_unit, pic_recruiter)
    
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        pic_recruiter=pic_recruiter,
        display_name=display_name or username,
        business_unit=business_unit,
        kode_pic=kode_pic
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user_id: int, new_password: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    if len(new_password) < 6:
        return False
    user.password_hash = hash_password(new_password)
    db.commit()
    return True


def init_default_users(db: Session):
    """Create 25+ PIC users + 1 Admin + 1 IT if not exist"""
    # Format: (username, display_name, pic_recruiter, business_unit, kode_pic)
    pic_users = [
        # ===== CORPORATE (CORP) =====
        ("adista", "Adista", "Adista", "CORP", "CORPAdi"),
        ("brittney", "Brittney", "Brittney", "CORP", "CORPBrit"),
        ("eli", "Eli", "Eli", "CORP", "CORPEli"),
        ("fiqra", "Fiqra", "Fiqra", "CORP", "CORPFiq"),
        ("karin", "Karin", "Karin", "CORP", "CORPKar"),
        ("kenthansen", "Kenthansen", "Kenthansen", "CORP", "CORPKen"),
        ("kevin", "Kevin", "Kevin", "CORP", "CORPKev"),
        ("marta", "Marta", "Marta", "CORP", "CORPMar"),
        ("omega", "Omega", "Omega", "CORP", "CORPOme"),
        ("salsa", "Salsa", "Salsa", "CORP", "CORPSal"),
        ("valen", "Valendra", "Valendra", "CORP", "CORPVal"),
        ("victor", "Victor", "Victor", "CORP", "CORPVic"),
        ("yeremia", "Yeremia", "Yeremia", "CORP", "CORPYer"),
        ("zwei", "Zwei", "Zwei", "CORP", "CORPZwei"),
        ("desi", "Desi", "Desi", "CORP", "CORPDesi"),
        
        # ===== MP (Macroprima Panganutama) =====
        ("pauline", "Pauline", "Pauline", "MP", "MPPau"),
        ("ratih", "Ratih", "Ratih", "MP", "MPRat"),
        ("achmad", "Achmad", "Achmad", "MP", "MPAch"),
        ("kasanah", "Kasanah", "Kasanah", "MP", "MPKas"),
        ("alma", "Alma", "Alma", "MP", "MPAlm"),
        
        # ===== CMD (Cisarua Mountain Dairy) =====
        ("salwa", "Salwa", "Salwa", "CMD", "CMDSal"),
        ("elsi", "Elsi", "Elsi", "CMD", "CMDEls"),
        ("wahyu", "Wahyu", "Wahyu", "CMD", "CMDWah"),
        
        # ===== JESS (Java Egg Specialities) =====
        ("riska", "Riska", "Riska", "JESS", "JESSRis"),
        ("fiscall", "Fiscall", "Fiscall", "JESS", "JESSFis"),
        
        # ===== MS (Macrosentra Niagaboga) =====
        ("leo", "Leo", "Leo", "MS", "MSLeo"),
        
        # ===== DUMMY/ALIAS UNTUK COMPATIBILITY =====
        ("CMD", "CMD", "CMD", "CMD", "CMD"),
        ("JESS", "JESS", "JESS", "JESS", "JESS"),
        ("MS", "MS", "MS", "MS", "MS"),
        ("MP", "MP", "MP", "MP", "MP"),
    ]
    
    for username, display_name, pic_name, bu, kode in pic_users:
        if not db.query(User).filter(User.username == username).first():
            create_user(db, username, "password123", "user", pic_name, display_name, bu, kode)
    
    # ===== ADMIN =====
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin",
            display_name="Administrator",
            pic_recruiter="Admin",
            business_unit="CORP",
            kode_pic="ADMIN"
        )
        db.add(admin)
        db.commit()
    
    # ===== IT SUPPORT (VIEW-ONLY) =====
    if not db.query(User).filter(User.username == "it").first():
        it_user = User(
            username="it",
            password_hash=hash_password("it123"),
            role="it",
            display_name="IT Support",
            pic_recruiter="IT",
            business_unit="CORP",
            kode_pic="IT"
        )
        db.add(it_user)
        db.commit()


def init_master_dropdown(db: Session):
    """Seed default master data jika kosong"""
    if db.query(MasterDropdown).count() > 0:
        return  # sudah ada data
    
    default_data = [
        {"kode_pic": "CORPPau", "bu": "PT CISARUA MOUNTAIN DAIRY, TBK", "alasan": "Karyawan Lama Keluar", "category_fptk": "NEW", "pic_recruiter": "Pauline", "filter_fptk": "CLAP FGDP", "status": "OP", "lokasi_onboarding": "HO Meruya", "detail_sla": "OP belum lewat SLA", "keterangan_0": "Area minim sumber daya", "keterangan_1": "Kandidat hasil referensi User", "keterangan_cancel": "Keterangan FPTK tidak sesuai kebutuhan", "nama_direktorat": "CEO Office", "model": "Model 1", "sumber_sourcing": "Jobstreet", "jenjang_pendidikan": "SMA/SMK", "nama_universitas_top10": "Universitas Indonesia", "jurusan": "IPA", "university_tier": "Top 3 PTN", "ipk_tier": "Lebih dari 3,5"},
        {"kode_pic": "CORPKar", "bu": "PT MACROSENTRA NIAGABOGA", "alasan": "Penambahan Personil", "category_fptk": "REPLACEMENT", "pic_recruiter": "Karin", "filter_fptk": "Level 1-2", "status": "Closed", "lokasi_onboarding": "Semarang", "detail_sla": "OP tidak lulus SLA", "keterangan_0": "User tidak responsif", "keterangan_1": "Talent pool besar", "keterangan_cancel": "FPTK diisi dengan karyawan mutasi/promosi", "nama_direktorat": "CEO, Corsec, & Investor Relation", "model": "Model 2", "sumber_sourcing": "LinkedIn", "jenjang_pendidikan": "D3", "nama_universitas_top10": "Universitas Gadjah Mada", "jurusan": "IPS", "university_tier": "Top 10 PTN", "ipk_tier": "Lebih dari 3,2"},
        {"kode_pic": "CORPTih", "bu": "PT JAVA EGG SPECIALITIES", "alasan": "Jabatan Baru", "category_fptk": "", "pic_recruiter": "Ratih", "filter_fptk": "STO", "status": "Cancel", "lokasi_onboarding": "Cikupa", "detail_sla": "Closed lulus SLA", "keterangan_0": "Kandidat mengundurkan diri", "keterangan_1": "User responsif dalam proses seleksi", "keterangan_cancel": "Karyawan existing batal resign", "nama_direktorat": "Commercial CMD", "model": "Model 3", "sumber_sourcing": "Google Form", "jenjang_pendidikan": "D4", "nama_universitas_top10": "Institut Teknologi Bandung", "jurusan": "Administrasi Bisnis", "university_tier": "Top 20 PTN", "ipk_tier": "Kurang dari 3,5"},
        {"kode_pic": "CORPLex", "bu": "PT MACROPRIMA PANGANUTAMA", "alasan": "Karyawan Lama Mutasi", "category_fptk": "", "pic_recruiter": "Alexa", "filter_fptk": "Level 3", "status": "OP", "lokasi_onboarding": "Sentul", "detail_sla": "Closed tidak lulus SLA", "keterangan_0": "Kendala biaya/hasil Medical Check Up", "keterangan_1": "FPTK, urgent dan butuh cepat", "keterangan_cancel": "Melalui proses Internal Hiring", "nama_direktorat": "Commercial JES", "model": "Model 4", "sumber_sourcing": "Referensi User", "jenjang_pendidikan": "S1", "nama_universitas_top10": "Universitas Airlangga", "jurusan": "Administrasi Niaga", "university_tier": "Top 10 PTS", "ipk_tier": "Kurang dari 3,2"},
        {"kode_pic": "CORPMar", "bu": "PT ARTHA RASA CIMORY", "alasan": "Karyawan Lama Promosi", "category_fptk": "", "pic_recruiter": "Marta", "filter_fptk": "Level 4", "status": "", "lokasi_onboarding": "Pasuruan", "detail_sla": "Cancel FPTK", "keterangan_0": "Kandidat, tidak sesuai preferensi user", "keterangan_1": "Kandidat tersedia dari talent pool existing", "keterangan_cancel": "Posisi di-hold oleh user", "nama_direktorat": "Commercial MP", "model": "", "sumber_sourcing": "Referensi Karyawan", "jenjang_pendidikan": "S2", "nama_universitas_top10": "Universitas Padjadjaran", "jurusan": "Administrasi Publik", "university_tier": "Lainnya", "ipk_tier": ""},
        {"kode_pic": "CORPBrit", "bu": "PT MACROTAMA BINASANTIKA", "alasan": "", "category_fptk": "", "pic_recruiter": "Brittney", "filter_fptk": "", "status": "", "lokasi_onboarding": "Area Sales", "detail_sla": "", "keterangan_0": "User mengubah kualifikasi kandidat", "keterangan_1": "Kandidat hasil referensi karyawan", "keterangan_cancel": "Karyawan existing batal resign", "nama_direktorat": "Finance & Business Support", "model": "", "sumber_sourcing": "Campus Hiring", "jenjang_pendidikan": "", "nama_universitas_top10": "Universitas Diponegoro", "jurusan": "Agribisnis", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CORPOme", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Omega", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "Kandidat meminta penyesuaian kompensasi di luar budget", "keterangan_1": "Kualifikasi posisi mudah ditemukan di market", "keterangan_cancel": "Perubahan struktur organisasi", "nama_direktorat": "Logistic & Distribution", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Universitas Brawijaya", "jurusan": "Agroteknologi", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CORPZwei", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Zwei", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "Posisi sempat di-hold sementara oleh user", "keterangan_1": "", "keterangan_cancel": "FPTK dibuat duplikat", "nama_direktorat": "Manufacture CMD", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Institut Pertanian Bogor", "jurusan": "Akuntansi", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CORPKen", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Kenthansen", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "Kendala administrasi atau dokumen kandidat", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Manufacture JES", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Universitas Sebelas Maret", "jurusan": "Analisis Kimia", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CORPDesi", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Desi", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "Kendala medical check-up", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Manufacture MP", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Telkom University", "jurusan": "Analitik Bisnis", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CMDEls", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Elsi", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "Hari libur/cuti bersama memengaruhi proses", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Procurement CMD & Corporate", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Aktuaria", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CMDSal", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Salwa", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Procurement MP & JES", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "SMA/SMK", "nama_universitas_top10": "Lainnya", "jurusan": "Arsitektur", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "CMDWah", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Wahyu", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Sales General Trade CMD", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Asuransi", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "MPAch", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Achmad", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Sales General Trade JES", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Bioinformatika", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "MPKas", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Kasanah", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Sales General Trade MP", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Biologi", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "MPEli", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Eli", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Sales International Market", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Bioteknologi", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "MPGab", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Gabbie", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "Sales Modern Trade", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Bisnis dan Manajemen", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "MSLeo", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Leo", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Bisnis Digital", "university_tier": "", "ipk_tier": ""},
        {"kode_pic": "JESSFis", "bu": "", "alasan": "", "category_fptk": "", "pic_recruiter": "Fiscall", "filter_fptk": "", "status": "", "lokasi_onboarding": "", "detail_sla": "", "keterangan_0": "", "keterangan_1": "", "keterangan_cancel": "", "nama_direktorat": "", "model": "", "sumber_sourcing": "", "jenjang_pendidikan": "", "nama_universitas_top10": "Lainnya", "jurusan": "Bisnis Internasional", "university_tier": "", "ipk_tier": ""},
    ]
    
    for data in default_data:
        master = MasterDropdown(**data)
        db.add(master)
    
    db.commit()


def get_current_user(db: Session):
    """Ambil user yang sedang login dari session state"""
    if "user_id" not in st.session_state:
        return None
    return db.query(User).filter(User.id == st.session_state.user_id).first()


def is_admin(db: Session):
    """Cek apakah user yang login adalah admin"""
    user = get_current_user(db)
    return user and user.role == "admin"


def is_it(db: Session) -> bool:
    """Cek apakah user adalah IT (view-only)"""
    user = get_current_user(db)
    return user and user.role == "it"


def is_editor(db: Session) -> bool:
    """Cek apakah user bisa melakukan aksi edit/upload"""
    user = get_current_user(db)
    return user and user.role in ["admin", "user"]


def can_edit_data(db: Session) -> bool:
    """Cek apakah user bisa edit data (hanya admin)"""
    user = get_current_user(db)
    return user and user.role == "admin"


def login_required():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.warning("⚠️ Silakan login terlebih dahulu.")
        st.stop()


def hash_file(file_data: bytes) -> str:
    return hashlib.sha256(file_data).hexdigest()


def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
