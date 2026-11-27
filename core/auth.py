# core/auth.py
import bcrypt
import streamlit as st
from sqlalchemy.orm import Session
from core.models import User, AuditLog, MasterDropdown, LoginAttempt
import datetime
import hashlib
import re
import secrets


# Login throttling: lock an account after this many failed attempts within the window.
MAX_FAILED_LOGINS = 5
LOGIN_LOCK_MINUTES = 15
MIN_PASSWORD_LENGTH = 8
# Passwords that were seeded or handed out by older versions of the app.
# A user who still logs in with one of them must set a new password first.
KNOWN_DEFAULT_PASSWORDS = {"password123", "admin123", "it12345"}


BU_CODE_MAPPING = {
    "CMD": {"nama": "PT Cisarua Mountain Dairy, Tbk", "kode": "CMD"},
    "JESS": {"nama": "PT Java Egg Specialities", "kode": "JESS"},
    "MS": {"nama": "PT Macrosentra Niagaboga", "kode": "MS"},
    "MP": {"nama": "PT Macroprima Panganutama", "kode": "MP"},
    "CORP": {"nama": "Corporate", "kode": "CORP"},
}


def invalidate_filter_cache():
    try:
        from core.utils import get_filter_options_from_db
        get_filter_options_from_db.clear()
    except Exception:
        pass


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash or password_hash == "DISABLED":
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def validate_new_password(password: str, confirm: str = None):
    """Return an error message (Indonesian) or None when the password is acceptable."""
    if not password:
        return "Password wajib diisi."
    if confirm is not None and password != confirm:
        return "Konfirmasi password tidak sama."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password minimal {MIN_PASSWORD_LENGTH} karakter."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password harus mengandung huruf dan angka."
    if password.lower() in KNOWN_DEFAULT_PASSWORDS:
        return "Password ini terlalu umum. Gunakan password lain."
    return None


def generate_temp_password() -> str:
    """Random one-time password for admin resets (user must change it at next login)."""
    while True:
        pw = secrets.token_urlsafe(9)
        if re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw):
            return pw


def set_user_password(db: Session, user: User, new_password: str, must_change: bool = False):
    user.password_hash = hash_password(new_password)
    user.must_change_password = must_change
    db.commit()


_DUMMY_HASH = None


def _dummy_verify(password: str):
    """Spend the same bcrypt time for unknown usernames (timing does not reveal existence)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    verify_password(password or "", _DUMMY_HASH)


def _username_key(username: str) -> str:
    return (username or "").strip().lower()[:100]


def _recent_failed_logins(db: Session, key: str, now: datetime.datetime) -> int:
    window_start = now - datetime.timedelta(minutes=LOGIN_LOCK_MINUTES)
    last_success = (
        db.query(LoginAttempt.created_at)
        .filter(LoginAttempt.username_key == key, LoginAttempt.success.is_(True),
                LoginAttempt.created_at >= window_start)
        .order_by(LoginAttempt.created_at.desc())
        .first()
    )
    since = max(window_start, last_success[0]) if last_success else window_start
    return (
        db.query(LoginAttempt)
        .filter(LoginAttempt.username_key == key, LoginAttempt.success.is_(False),
                LoginAttempt.created_at > since)
        .count()
    )


def _record_attempt(db: Session, key: str, success: bool, now: datetime.datetime):
    db.add(LoginAttempt(username_key=key, success=success, created_at=now))
    if not success:
        db.query(LoginAttempt).filter(
            LoginAttempt.created_at < now - datetime.timedelta(days=1)
        ).delete(synchronize_session=False)


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if verify_password(password, user.password_hash):
        return user
    return None


def attempt_login(db: Session, username: str, password: str):
    """Authenticate with lockout. Returns (user, error) where error is None,
    'invalid' or 'locked'.

    Lockout is keyed by the typed username whether or not it exists, and unknown
    usernames cost the same bcrypt time, so neither the message nor the timing
    reveals which usernames exist. Timestamps are app-side so the window does not
    depend on the database server's timezone."""
    username = (username or "").strip()
    key = _username_key(username)
    now = datetime.datetime.now()
    if _recent_failed_logins(db, key, now) >= MAX_FAILED_LOGINS:
        return None, "locked"
    user = db.query(User).filter(User.username == username).first()
    if not user:
        _dummy_verify(password)
        _record_attempt(db, key, False, now)
        db.commit()
        return None, "invalid"
    if not verify_password(password, user.password_hash):
        _record_attempt(db, key, False, now)
        db.add(AuditLog(user_id=user.id, action="LOGIN_FAILED", table_name="users",
                        record_id=user.id, created_at=now))
        db.commit()
        return None, "invalid"
    if password.lower() in KNOWN_DEFAULT_PASSWORDS:
        from core.demo import is_demo
        if not is_demo():
            user.must_change_password = True
    user.last_login = now
    _record_attempt(db, key, True, now)
    db.add(AuditLog(user_id=user.id, action="LOGIN", table_name="users",
                    record_id=user.id, created_at=now))
    db.commit()
    return user, None


def login_user(db: Session, username: str, password: str):
    user, _ = attempt_login(db, username, password)
    return user


def generate_kode_pic(business_unit: str, pic_name: str) -> str:
    if not business_unit or not pic_name:
        return ""
    name_code = re.sub(r'[^A-Za-z]', '', pic_name)[:3].capitalize()
    return f"{business_unit}{name_code}"


def create_user(db: Session, username: str, password: str, role: str = "user",
                pic_recruiter: str = None, display_name: str = None,
                business_unit: str = None, kode_pic: str = None,
                email: str = None, must_change_password: bool = False,
                enforce_policy: bool = True):
    if db.query(User).filter(User.username == username).first():
        return None
    if enforce_policy and validate_new_password(password):
        return None
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        pic_recruiter=pic_recruiter,
        display_name=display_name or username,
        business_unit=business_unit,
        kode_pic=kode_pic,
        email=normalize_email(email),
        must_change_password=must_change_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    invalidate_filter_cache()
    return user


def reset_password(db: Session, user_id: int, new_password: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    if validate_new_password(new_password):
        return False
    set_user_password(db, user, new_password, must_change=True)
    return True


def normalize_email(email):
    email = (email or "").strip().lower()
    return email or None


def is_valid_email(email) -> bool:
    return bool(email) and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


def _get_setting(name):
    import os
    val = os.getenv(name)
    if val:
        return val
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def init_default_users(db: Session):
    from core.demo import is_demo, DEMO_USERS, DEMO_PASSWORD
    if is_demo():
        for username, display_name, pic_name, bu, kode in DEMO_USERS:
            if not db.query(User).filter(User.username == username).first():
                create_user(db, username, DEMO_PASSWORD, "user", pic_name, display_name, bu, kode,
                            enforce_policy=False)
        if not db.query(User).filter(User.username == "demo_admin").first():
            db.add(User(username="demo_admin", password_hash=hash_password(DEMO_PASSWORD), role="admin",
                        display_name="Demo Admin", pic_recruiter="Admin", business_unit="CORP", kode_pic="ADMIN"))
            db.commit()
        invalidate_filter_cache()
        return

    pic_users = [
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
        ("pauline", "Pauline", "Pauline", "MP", "MPPau"),
        ("ratih", "Ratih", "Ratih", "MP", "MPRat"),
        ("achmad", "Achmad", "Achmad", "MP", "MPAch"),
        ("kasanah", "Kasanah", "Kasanah", "MP", "MPKas"),
        ("alma", "Alma", "Alma", "MP", "MPAlm"),
        ("salwa", "Salwa", "Salwa", "CMD", "CMDSal"),
        ("elsi", "Elsi", "Elsi", "CMD", "CMDEls"),
        ("wahyu", "Wahyu", "Wahyu", "CMD", "CMDWah"),
        ("riska", "Riska", "Riska", "JESS", "JESSRis"),
        ("fiscall", "Fiscall", "Fiscall", "JESS", "JESSFis"),
        ("leo", "Leo", "Leo", "MS", "MSLeo"),
    ]

    # Recruiter (PIC) accounts are seeded without a usable password: an admin sets
    # a temporary password from User Management. Existing accounts are untouched.
    for username, display_name, pic_name, bu, kode in pic_users:
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, password_hash="DISABLED", role="user",
                        pic_recruiter=pic_name, display_name=display_name,
                        business_unit=bu, kode_pic=kode))
    db.commit()

    # Optional operator shortcut: INITIAL_ADMIN_PASSWORD (env var or Streamlit secret)
    # creates the first admin. Otherwise the first-run setup screen is used
    # (core/first_run.py). No password is hardcoded in the source.
    # It also serves as the deliberate, server-side recovery procedure if every
    # admin account has been lost, because only someone with access to the
    # deployment's settings can set it.
    initial_pw = _get_setting("INITIAL_ADMIN_PASSWORD")
    if initial_pw and not active_admin_exists(db) and \
            not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", password_hash=hash_password(initial_pw), role="admin",
                    display_name="Administrator", pic_recruiter="Admin",
                    business_unit="CORP", kode_pic="ADMIN", must_change_password=True))
        db.commit()

    invalidate_filter_cache()


def init_master_dropdown(db: Session):
    if db.query(MasterDropdown).count() > 0:
        return

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
    invalidate_filter_cache()


def get_current_user(db: Session):
    if "user_id" not in st.session_state:
        return None
    return db.query(User).filter(User.id == st.session_state.user_id).first()


def active_admin_exists(db: Session) -> bool:
    """True when at least one admin account can actually log in."""
    return db.query(User.id).filter(
        User.role == "admin",
        User.password_hash != "DISABLED",
        ~User.username.like("inactive\\_%", escape="\\"),
    ).first() is not None


def is_admin(db: Session):
    user = get_current_user(db)
    return user and user.role == "admin"


def is_it(db: Session) -> bool:
    user = get_current_user(db)
    return user and user.role == "it"


def is_editor(db: Session) -> bool:
    user = get_current_user(db)
    if not user:
        return False
    return user.role in ["admin", "user"]


def can_edit_data(db: Session) -> bool:
    user = get_current_user(db)
    return user and user.role == "admin"


def login_required():
    if "user_id" not in st.session_state or st.session_state.user_id is None:
        st.warning("Silakan login terlebih dahulu.")
        st.stop()


def hash_file(file_data: bytes) -> str:
    return hashlib.sha256(file_data).hexdigest()


def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
