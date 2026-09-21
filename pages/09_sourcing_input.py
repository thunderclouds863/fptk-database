# pages/09_sourcing_input.py
import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown, CVAttachment
from core.auth import get_current_user, is_it, is_editor, is_admin
from core.utils import (
    safe_int, safe_float, parse_phone, is_valid_email,
    find_duplicate_candidates, get_last_pipeline_stage
)
from core.model_rekrutmen import auto_detect_model_rekrutmen, get_model_options
import base64
import time
import re

COPILOT_AGENT_URL = "https://m365.cloud.microsoft/chat/?titleId=T_e0524666-839c-757c-7ef5-d5e72311417d&source=embedded-builder"
MAX_CV_SIZE_MB = 10
ALLOWED_CV_EXT = ["pdf", "doc", "docx", "jpg", "jpeg", "png", "xlsx", "xlsm", "ppt", "pptx", "txt"]


@st.cache_data(ttl=3600)
def get_master_options_sourcing(_db):
    try:
        master = _db.query(MasterDropdown).filter(MasterDropdown.is_active == True).all()
        pic_options = sorted(set([m.pic_recruiter for m in master if m.pic_recruiter]))
        bu_options = sorted(set([m.bu for m in master if m.bu]))
        return {'pic_options': pic_options, 'bu_options': bu_options}
    except Exception:
        return {'pic_options': [], 'bu_options': []}


@st.cache_data(ttl=3600)
def get_sourcing_options():
    return {
        'sumber_options': ["Jobstreet", "LinkedIn", "Google Form", "Referensi User", "Referensi Karyawan", "Campus Hiring", "Walk-in Interview", "Database Internal", "Freelance", "Lainnya"],
        'jenjang_options': ["SMA/SMK", "D3", "D4", "S1", "S2"],
        'univ_options': ["Universitas Indonesia", "Universitas Gadjah Mada", "Institut Teknologi Bandung", "Universitas Airlangga", "Universitas Padjadjaran", "Universitas Diponegoro", "Universitas Brawijaya", "Institut Pertanian Bogor", "Universitas Sebelas Maret", "Telkom University", "Lainnya"],
        'jurusan_options': ["Manajemen", "Akuntansi", "Teknik Industri", "Teknik Informatika", "Sistem Informasi", "Psikologi", "Ilmu Komunikasi", "Hukum", "Ekonomi", "Lainnya"],
        'fmcg_options': ["", "Ya", "Tidak"],
        'pipeline_options': ["", "V", "X"],
        'university_tier_options': ["Top 3 PTN", "Top 10 PTN", "Top 20 PTN", "Top 10 PTS", "Lainnya"]
    }


@st.cache_data(ttl=3600)
def get_pipeline_stages():
    return [
        {"field": "sourcing_freelance", "label": "Sourcing Freelance"},
        {"field": "sourcing_hr", "label": "Sourcing HR"},
        {"field": "shortlist_cv", "label": "Shortlist CV"},
        {"field": "psikotes", "label": "Psikotes"},
        {"field": "hr_interview", "label": "HR Interview"},
        {"field": "technical_test_case_study", "label": "Technical Test / Case Study"},
        {"field": "market_visit", "label": "Market Visit"},
        {"field": "user_interview", "label": "User Interview"},
        {"field": "panel_interview", "label": "Panel Interview"},
        {"field": "reference_check", "label": "Reference Check"},
        {"field": "mcu", "label": "MCU"},
        {"field": "offering", "label": "Offering"},
        {"field": "day1", "label": "Day 1"}
    ]


UNIV_TIER_MAP = {
    "Universitas Indonesia": "Top 3 PTN", "Universitas Gadjah Mada": "Top 3 PTN",
    "Institut Teknologi Bandung": "Top 3 PTN", "Universitas Airlangga": "Top 10 PTN",
    "IPB University": "Top 10 PTN", "Institut Teknologi Sepuluh Nopember": "Top 10 PTN",
    "Universitas Padjadjaran": "Top 10 PTN", "Universitas Diponegoro": "Top 10 PTN",
    "Universitas Brawijaya": "Top 10 PTN", "Universitas Hasanuddin": "Top 20 PTN",
    "Universitas Sebelas Maret": "Top 20 PTN", "Universitas Sumatera Utara": "Top 20 PTN",
    "Universitas Pendidikan Indonesia": "Top 20 PTN", "Universitas Negeri Yogyakarta": "Top 20 PTN",
    "Universitas Negeri Padang": "Top 20 PTN", "Universitas Negeri Malang": "Top 20 PTN",
    "Universitas Syiah Kuala": "Top 20 PTN", "Universitas Andalas": "Top 20 PTN",
    "Universitas Udayana": "Top 20 PTN", "Universitas Negeri Semarang": "Top 20 PTN",
    "Bina Nusantara University": "Top 10 PTS", "Telkom University": "Top 10 PTS",
    "Institut Teknologi Nasional Bandung": "Top 10 PTS",
    "Universitas Muhammadiyah Yogyakarta": "Top 10 PTS",
    "Universitas Katolik Indonesia Atma Jaya": "Top 10 PTS",
    "Universitas Islam Indonesia": "Top 10 PTS", "Universitas Kristen Petra": "Top 10 PTS",
    "Universitas Trisakti": "Top 10 PTS", "Universitas Pelita Harapan": "Top 10 PTS",
    "Swiss German University": "Top 10 PTS",
}

UNIV_ALIASES = {
    "Universitas Indonesia": ["universitas indonesia", "university of indonesia", "ui"],
    "Universitas Gadjah Mada": ["universitas gadjah mada", "gadjah mada university", "ugm"],
    "Institut Teknologi Bandung": ["institut teknologi bandung", "bandung institute of technology", "itb"],
    "Universitas Airlangga": ["universitas airlangga", "airlangga university", "unair", "airlangga"],
    "IPB University": ["ipb university", "institut pertanian bogor", "bogor agricultural university", "ipb"],
    "Institut Teknologi Sepuluh Nopember": ["institut teknologi sepuluh nopember", "its surabaya", "its"],
    "Universitas Padjadjaran": ["universitas padjadjaran", "padjadjaran university", "unpad", "padjadjaran"],
    "Universitas Diponegoro": ["universitas diponegoro", "diponegoro university", "undip", "diponegoro"],
    "Universitas Brawijaya": ["universitas brawijaya", "brawijaya university", "ub brawijaya", "brawijaya"],
    "Universitas Hasanuddin": ["universitas hasanuddin", "hasanuddin university", "unhas", "hasanuddin"],
    "Universitas Sebelas Maret": ["universitas sebelas maret", "sebelas maret university", "uns", "sebelas maret"],
    "Universitas Sumatera Utara": ["universitas sumatera utara", "university of sumatera utara", "usu"],
    "Universitas Pendidikan Indonesia": ["universitas pendidikan indonesia", "indonesia university of education", "upi"],
    "Universitas Negeri Yogyakarta": ["universitas negeri yogyakarta", "yogyakarta state university", "uny"],
    "Universitas Negeri Padang": ["universitas negeri padang", "padang state university", "unp"],
    "Universitas Negeri Malang": ["universitas negeri malang", "state university of malang", "um"],
    "Universitas Syiah Kuala": ["universitas syiah kuala", "syiah kuala university", "usk", "unsyiah"],
    "Universitas Andalas": ["universitas andalas", "andalas university", "unand"],
    "Universitas Udayana": ["universitas udayana", "udayana university", "unud"],
    "Universitas Negeri Semarang": ["universitas negeri semarang", "semarang state university", "unnes"],
    "Bina Nusantara University": ["bina nusantara", "binus university", "binus", "universitas bina nusantara"],
    "Telkom University": ["telkom university", "universitas telkom", "tel-u", "telkom"],
    "Institut Teknologi Nasional Bandung": ["institut teknologi nasional bandung", "itenas"],
    "Universitas Muhammadiyah Yogyakarta": ["universitas muhammadiyah yogyakarta", "umy"],
    "Universitas Katolik Indonesia Atma Jaya": ["atma jaya", "unika atma jaya", "atma jaya catholic university"],
    "Universitas Islam Indonesia": ["universitas islam indonesia", "uii"],
    "Universitas Kristen Petra": ["universitas kristen petra", "petra christian university", "petra"],
    "Universitas Trisakti": ["universitas trisakti", "trisakti university", "usakti", "trisakti"],
    "Universitas Pelita Harapan": ["universitas pelita harapan", "pelita harapan university", "uph"],
    "Swiss German University": ["swiss german university", "sgu"],
}

JURUSAN_ALIASES = {
    "Manajemen": ["manajemen", "management"], "Akuntansi": ["akuntansi", "accounting"],
    "Teknik Industri": ["teknik industri", "industrial engineering"],
    "Teknik Informatika": ["teknik informatika", "informatics", "computer science", "ilmu komputer"],
    "Sistem Informasi": ["sistem informasi", "information system"],
    "Psikologi": ["psikologi", "psychology"],
    "Ilmu Komunikasi": ["ilmu komunikasi", "communication science", "komunikasi"],
    "Hukum": ["hukum", "law"], "Ekonomi": ["ekonomi", "economics"],
}

GENERIC_UNIV_WORDS = {"universitas", "university", "univ", "sekolah", "school", "institut", "institute", "stie", "stmik", "sti", "politeknik", "akademi"}
GENERIC_JURUSAN_WORDS = {"jurusan", "major", "program studi", "prodi", "department"}


def _clean_text(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_univ(raw_val):
    """
    Return tuple (canonical_name, other_name).
    - Kalau match UNIV_ALIASES -> (canonical, "")
    - Kalau gak match -> ("Lainnya", pretty_name)
    """
    if not raw_val or not str(raw_val).strip():
        return "", ""
    raw_str = str(raw_val).strip()
    raw_clean = _clean_text(raw_str)
    for canonical, aliases in UNIV_ALIASES.items():
        for alias in aliases:
            if raw_clean == alias or re.search(rf"\b{re.escape(alias)}\b", raw_clean):
                return canonical, ""
    pretty = " ".join([w.capitalize() for w in raw_str.split()])
    return "Lainnya", pretty


def get_university_tier(univ_name):
    if not univ_name:
        return ""
    return UNIV_TIER_MAP.get(univ_name, "Lainnya")


def normalize_jurusan(raw_val):
    if not raw_val or not str(raw_val).strip():
        return "", ""
    raw_str = str(raw_val).strip()
    raw_clean = _clean_text(raw_str)
    for canonical, aliases in JURUSAN_ALIASES.items():
        for alias in aliases:
            if raw_clean == alias or re.search(rf"\b{re.escape(alias)}\b", raw_clean):
                return canonical, ""
    pretty = " ".join([w.capitalize() for w in raw_str.split()])
    return "Lainnya", pretty


KNOWN_LABELS = [
    "Jenjang Pendidikan", "Nama Universitas/Sekolah", "Nama Universitas/sekolah", "Nama Universitas",
    "Nama Sekolah", "University Tier", "Ipk Tier", "IPK Tier", "Nomor Hp", "Nomor HP",
    "Pernah Di Fmcg?", "Pernah di FMCG?", "Pernah Di FMCG", "Pernah di Fmcg",
    "Last Position", "Last Tenure", "Last Company", "Total Tenure", "Tahun Lulus",
    "Kode Unik", "Posisi FPTK", "Sumber", "Jurusan", "Domisili", "Email", "Nama", "Ipk", "IPK", "HP",
]


def preprocess_cv_text(raw_text):
    if not raw_text:
        return raw_text
    if raw_text.count('\n') > 3:
        return raw_text
    text = raw_text
    labels_sorted = sorted(KNOWN_LABELS, key=len, reverse=True)
    for label in labels_sorted:
        pattern = re.compile(r'(?i)(?<!^)\s*(' + re.escape(label) + r'\s*:)', re.IGNORECASE)
        text = pattern.sub(r'\n\1', text)
    text = text.lstrip('\n')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def parse_cv_text(raw_text):
    parsed = {
        'nama': '', 'email': '', 'hp': '', 'univ': '', 'univ_lain': '',
        'jurusan': '', 'jurusan_lain': '', 'ipk': '', 'tahun_lulus': '', 'domisili': '',
        'last_position': '', 'last_company': '', 'last_tenure': '', 'total_tenure': '',
        'sumber': '', 'posisi': '', 'kode_unik': '', 'jenjang': '', 'fmcg': '',
        'university_tier': ''
    }

    if not raw_text:
        return parsed

    raw_text = preprocess_cv_text(raw_text)
    lines = raw_text.split('\n')

    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(\+62|0)[0-9\s\-\(\)]{9,15}'
    ipk_pattern = r'([0-4][\.,]\d{1,2})'

    email_match = re.search(email_pattern, raw_text)
    if email_match:
        parsed['email'] = email_match.group()

    phone_match = re.search(phone_pattern, raw_text)
    if phone_match:
        parsed['hp'] = re.sub(r'[\s\-\(\)]', '', phone_match.group())

    ipk_match = re.search(ipk_pattern, raw_text)
    if ipk_match:
        parsed['ipk'] = ipk_match.group().replace(',', '.')

    year_matches = re.findall(r'\b(20[0-9]{2})\b', raw_text)
    for y in year_matches:
        y_int = int(y)
        if 1990 <= y_int <= 2030:
            parsed['tahun_lulus'] = y
            break

    for line in lines:
        line = line.strip()
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()

            if not val:
                continue

            if any(k in key for k in ['nama universitas', 'universitas', 'university', 'univ', 'sekolah', 'kampus', 'institut', 'politeknik']):
                univ_dd, univ_lain = normalize_univ(val)
                parsed['univ'] = univ_dd
                parsed['univ_lain'] = univ_lain
                parsed['university_tier'] = get_university_tier(univ_dd)

            elif any(k in key for k in ['nama', 'name', 'full name', 'candidate name']):
                parsed['nama'] = val

            elif any(k in key for k in ['jenjang', 'education', 'level']):
                vl = val.lower()
                if 's1' in vl or 'bachelor' in vl or 'sarjana' in vl:
                    parsed['jenjang'] = 'S1'
                elif 's2' in vl or 'master' in vl or 'magister' in vl:
                    parsed['jenjang'] = 'S2'
                elif 'd3' in vl or 'diploma 3' in vl:
                    parsed['jenjang'] = 'D3'
                elif 'd4' in vl or 'diploma 4' in vl:
                    parsed['jenjang'] = 'D4'
                elif 'smk' in vl or 'vocational' in vl:
                    parsed['jenjang'] = 'SMA/SMK'
                elif 'sma' in vl or 'high school' in vl:
                    parsed['jenjang'] = 'SMA/SMK'
                else:
                    parsed['jenjang'] = val

            elif any(k in key for k in ['jurusan', 'major']):
                jur_dd, jur_lain = normalize_jurusan(val)
                parsed['jurusan'] = jur_dd
                parsed['jurusan_lain'] = jur_lain

            elif any(k in key for k in ['domisili', 'domicile', 'location', 'kota', 'city']):
                parsed['domisili'] = val

            elif any(k in key for k in ['nomor hp', 'no hp', 'hp', 'phone', 'nomor', 'no telp']):
                parsed['hp'] = re.sub(r'[\s\-\(\)]', '', val)

            elif any(k in key for k in ['last position', 'posisi terakhir']):
                parsed['last_position'] = val

            elif any(k in key for k in ['last company', 'perusahaan terakhir', 'company']):
                parsed['last_company'] = val

            elif any(k in key for k in ['last tenure', 'tenure last']):
                parsed['last_tenure'] = val

            elif any(k in key for k in ['total tenure', 'lama kerja', 'pengalaman']):
                parsed['total_tenure'] = val

            elif any(k in key for k in ['sumber', 'source']):
                parsed['sumber'] = val

            elif any(k in key for k in ['pernah di fmcg', 'pernah di fmcg?', 'fmcg']):
                vl = val.lower()
                if 'ya' in vl or 'yes' in vl or vl == 'y':
                    parsed['fmcg'] = 'Ya'
                elif 'tidak' in vl or 'no' in vl or vl == 'n':
                    parsed['fmcg'] = 'Tidak'
                else:
                    parsed['fmcg'] = val

            elif any(k in key for k in ['posisi fptk', 'fptk posisi']):
                parsed['posisi'] = val

            elif any(k in key for k in ['kode unik', 'unique code']):
                parsed['kode_unik'] = val

    if not parsed['nama']:
        for line in lines:
            line = line.strip()
            if line and ':' not in line and len(line) > 2 and not line.startswith('http'):
                parsed['nama'] = line
                break

    if not parsed['jenjang']:
        tl = raw_text.lower()
        if 's1' in tl or 'bachelor' in tl or 'sarjana' in tl:
            parsed['jenjang'] = 'S1'
        elif 's2' in tl or 'master' in tl or 'magister' in tl:
            parsed['jenjang'] = 'S2'
        elif 'd3' in tl or 'diploma 3' in tl:
            parsed['jenjang'] = 'D3'
        elif 'smk' in tl or 'vocational' in tl:
            parsed['jenjang'] = 'SMA/SMK'
        elif 'sma' in tl or 'high school' in tl:
            parsed['jenjang'] = 'SMA/SMK'

    if not parsed['fmcg']:
        tl = raw_text.lower()
        if 'fmcg' in tl:
            if 'ya' in tl or 'yes' in tl:
                parsed['fmcg'] = 'Ya'
            elif 'tidak' in tl or 'no' in tl:
                parsed['fmcg'] = 'Tidak'

    return parsed


def show_duplicate_warning_dialog(db, nama, email, hp):
    duplicates = find_duplicate_candidates(db, nama, email=email, nomor_hp=hp)

    if not duplicates:
        st.session_state["duplicate_action"] = "no_duplicate"
        return

    @st.dialog("⚠️ Kandidat Duplikat Ditemukan")
    def _dialog():
        st.warning(f"⚠️ Kandidat dengan nama **{nama}** sudah pernah diproses!")
        st.caption(f"Ditemukan {len(duplicates)} kandidat dengan nama sama.")

        st.markdown("### 📋 Kandidat yang Sudah Ada:")

        for i, dup in enumerate(duplicates, 1):
            with st.expander(f"#{i} - {dup['nama']} | {dup['kode_unik']}", expanded=(i == 1)):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Kode Unik:** {dup['kode_unik']}")
                    st.markdown(f"**Posisi:** {dup['posisi'] or '-'}")
                    st.markdown(f"**PIC:** {dup['rekruter'] or '-'}")
                    st.markdown(f"**Email:** {dup['email'] or '-'}")
                    st.markdown(f"**No HP:** {dup['nomor_hp'] or '-'}")
                with col2:
                    last = dup.get("last_stage")
                    if last:
                        st.markdown(f"**Tahap Terakhir:** {last['stage_label']}")
                        st.markdown(f"**Status:** {last['status']}")
                        st.markdown(f"**Tanggal:** {last['tanggal'].strftime('%d/%m/%Y') if last['tanggal'] else '-'}")
                    else:
                        st.info("Belum masuk tahap pipeline apapun.")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Lanjut Input (Duplicate)", use_container_width=True, key="dup_continue"):
                st.session_state["duplicate_action"] = "continue"
                st.rerun()
        with col2:
            if st.button("🔄 Transfer Kandidat Lama", use_container_width=True, key="dup_transfer"):
                st.session_state["duplicate_action"] = "transfer"
                st.rerun()

        st.markdown("---")
        if st.button("❌ Batal Input", use_container_width=True, key="dup_cancel"):
            st.session_state["duplicate_action"] = "cancel"
            st.rerun()

    _dialog()


def save_cv_attachments(db, sourcing_id, kode_unik, nama_kandidat, uploaded_files, user):
    saved = 0
    errors = []
    for f in uploaded_files:
        try:
            file_bytes = f.getvalue()
            size_mb = len(file_bytes) / (1024 * 1024)
            if size_mb > MAX_CV_SIZE_MB:
                errors.append(f"{f.name}: melebihi {MAX_CV_SIZE_MB} MB")
                continue
            file_b64 = base64.b64encode(file_bytes).decode('utf-8')
            new_cv = CVAttachment(
                sourcing_id=sourcing_id, kode_unik=kode_unik,
                nama_kandidat=nama_kandidat, file_name=f.name,
                file_data=file_b64, file_size=len(file_bytes),
                file_type=f.type or "application/octet-stream",
                uploaded_by=user.id,
                uploaded_by_name=user.display_name or user.username,
                created_at=datetime.now()
            )
            db.add(new_cv)
            db.commit()
            saved += 1
        except Exception as e:
            errors.append(f"{f.name}: {str(e)}")
            db.rollback()
    return saved, errors


def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input kandidat baru & kelola lampiran CV")

    db = next(get_db())
    if not is_editor(db):
        st.error("❌ Anda tidak memiliki akses untuk input sourcing. Hubungi Admin.")
        return
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return

    admin = is_admin(db)

    with st.spinner("📋 Memuat data..."):
        master_options = get_master_options_sourcing(db)
        sourcing_options = get_sourcing_options()
        pipeline_stages = get_pipeline_stages()

        fptk_list = db.query(FPTK).filter(FPTK.status == 'OP').order_by(FPTK.kode_unik).all()
        fptk_options = [(f.kode_unik, f.posisi, f.pic_recruiter, f.level_number) for f in fptk_list]

    pic_options = master_options['pic_options']
    pipeline_options = sourcing_options['pipeline_options']

    if 'parsed_cv_data' not in st.session_state:
        st.session_state.parsed_cv_data = {}
    if 'show_parsed_form' not in st.session_state:
        st.session_state.show_parsed_form = False

    tab1, tab2 = st.tabs(["📝 Input Kandidat Baru", "📎 Manage CV"])

    with tab1:
        render_input_tab(db, user, admin, pic_options, fptk_options, sourcing_options, pipeline_options, pipeline_stages)

    with tab2:
        render_manage_cv_tab(db, user, admin)


def render_input_tab(db, user, admin, pic_options, fptk_options, sourcing_options, pipeline_options, pipeline_stages):
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("### 🤖 Copilot Agent")
        st.caption("Parsing CV gambar/PDF scan menggunakan Copilot Agent")
    with col2:
        st.link_button("🚀 Buka Copilot Agent", COPILOT_AGENT_URL, use_container_width=True, type="primary")
    with col3:
        st.caption("Upload CV → Copy hasil → Paste di sini")

    st.markdown("---")

    sub1, sub2, sub3 = st.tabs(["📝 Manual Input", "📋 Paste Text", "📦 Batch CV"])

    with sub1:
        st.subheader("Manual Input Kandidat")
        show_manual_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options)

    with sub2:
        st.subheader("Paste Text CV")
        st.caption("Paste hasil copy dari Jobstreet / LinkedIn / Copilot Agent")

        raw_text = st.text_area("Paste teks CV di sini", height=150, key="paste_cv_raw")

        col1, col2 = st.columns([1, 4])
        with col1:
            parse_btn = st.button("🔍 Parse & Tampilkan di Form", use_container_width=True, type="primary", key="btn_parse_paste")

        if parse_btn and raw_text:
            with st.spinner("Memproses..."):
                parsed = parse_cv_text(raw_text)
                if parsed.get('nama'):
                    st.success(f"✅ Data ditemukan: {parsed.get('nama')}")
                    with st.expander("🐛 Debug Parsed Data"):
                        st.json({k: v for k, v in parsed.items() if v})
                    st.session_state.parsed_cv_data = parsed
                    st.session_state.show_parsed_form = True
                else:
                    st.warning("Tidak ada data terdeteksi. Pastikan formatnya 'Nama: ...'")

        if st.session_state.show_parsed_form and st.session_state.parsed_cv_data:
            st.markdown("---")
            st.markdown("### ✏️ Review & Edit Data Sebelum Simpan")
            st.caption("Data dari hasil parse sudah diisi otomatis. Silakan edit jika diperlukan.")

            show_sourcing_form(
                db=db, user=user, pic_options=pic_options,
                fptk_options=fptk_options, sourcing_options=sourcing_options,
                pipeline_options=pipeline_options, pipeline_stages=pipeline_stages,
                initial_data=st.session_state.parsed_cv_data,
                form_key="form_parse_edit", is_parse_mode=True
            )

    with sub3:
        st.subheader("Batch Paste CV (Banyak Kandidat)")
        st.caption("Paste hasil dari Copilot Agent atau multiple CV. Pisahkan dengan separator.")

        separator = st.text_input("Separator kandidat", value="=== CV ===", key="batch_separator")
        batch_text = st.text_area("Paste batch CV di sini", height=300, key="batch_text")

        if batch_text and st.button("🚀 Proses Batch", type="primary", key="btn_process_batch"):
            candidates = [c.strip() for c in batch_text.split(separator) if c.strip()]
            st.info(f"📋 Ditemukan {len(candidates)} kandidat")
            st.session_state.batch_candidates = candidates
            st.session_state.batch_index = 0
            st.rerun()

        if 'batch_candidates' in st.session_state and st.session_state.batch_candidates:
            idx = st.session_state.batch_index
            candidates = st.session_state.batch_candidates

            if idx < len(candidates):
                st.markdown("---")
                st.subheader(f"📄 Kandidat {idx+1} dari {len(candidates)}")

                raw_text = candidates[idx]
                parsed = parse_cv_text(raw_text)

                if parsed.get('nama'):
                    show_sourcing_form(
                        db=db, user=user, pic_options=pic_options,
                        fptk_options=fptk_options, sourcing_options=sourcing_options,
                        pipeline_options=pipeline_options, pipeline_stages=pipeline_stages,
                        initial_data=parsed, form_key=f"form_batch_{idx}",
                        is_parse_mode=True, batch_mode=True
                    )
                else:
                    st.warning(f"⚠️ Kandidat {idx+1} tidak terdeteksi datanya")
                    if st.button("⏭️ Lewati", key=f"skip_{idx}"):
                        st.session_state.batch_index = idx + 1
                        st.rerun()
            else:
                st.success("✅ Semua kandidat selesai diproses!")
                st.session_state.batch_candidates = []
                st.session_state.batch_index = 0


def render_manage_cv_tab(db, user, admin):
    st.markdown("### 📎 Manage Lampiran CV")
    st.caption("Upload CV untuk kandidat yang sudah ada, lihat, atau hapus.")

    with st.sidebar:
        st.markdown("### 🔍 Filter CV")
        search_cv = st.text_input("Cari (Nama / Kode Unik / File)", placeholder="Ketik keyword...", key="search_cv")
        uploaded_by_filter = st.text_input("Filter Upload By", placeholder="Nama uploader...", key="uploader_filter")

        if st.button("🔄 Reset Filter", use_container_width=True, key="reset_cv_filter"):
            st.rerun()

    sub1, sub2 = st.tabs(["📤 Upload CV untuk Kandidat", "📂 Daftar & Lihat CV"])

    with sub1:
        st.subheader("Upload CV")

        query = db.query(DBSourcing).order_by(DBSourcing.sourcing_date.desc())
        if not admin:
            query = query.filter(DBSourcing.rekruter == user.pic_recruiter)

        all_candidates = query.limit(1000).all()

        if not all_candidates:
            st.warning("Belum ada kandidat di DB Sourcing.")
        else:
            cand_options = {}
            for c in all_candidates:
                display = f"{c.kode_unik} | {c.nama} | {c.posisi or '-'}"
                cand_options[display] = c.id

            selected_display = st.selectbox("Pilih Kandidat", list(cand_options.keys()), key="cv_upload_cand")
            selected_id = cand_options.get(selected_display)

            if selected_id:
                candidate = db.query(DBSourcing).filter(DBSourcing.id == selected_id).first()
                if candidate:
                    st.info(f"📋 **{candidate.nama}** | Kode Unik: {candidate.kode_unik}")

                    existing_cvs = db.query(CVAttachment).filter(
                        CVAttachment.sourcing_id == selected_id
                    ).all()

                    if existing_cvs:
                        st.markdown(f"**{len(existing_cvs)} CV sudah terlampir**")

                    uploaded_files = st.file_uploader(
                        "Pilih file CV", type=ALLOWED_CV_EXT,
                        accept_multiple_files=True, key="cv_uploader_manage"
                    )

                    if uploaded_files and st.button(f"📤 Upload {len(uploaded_files)} File", type="primary", key="btn_upload_cv_manage"):
                        saved, errors = save_cv_attachments(
                            db, selected_id, candidate.kode_unik, candidate.nama,
                            uploaded_files, user
                        )
                        st.success(f"✅ Berhasil upload {saved} file!")
                        if errors:
                            st.warning(f"⚠️ Error: {len(errors)} file")
                            with st.expander("Detail Error"):
                                for err in errors:
                                    st.text(err)
                        st.balloons()
                        time.sleep(1)
                        st.rerun()

    with sub2:
        st.subheader("Daftar CV")

        query = db.query(CVAttachment).order_by(CVAttachment.created_at.desc())

        if search_cv:
            s = search_cv.strip()
            query = query.filter(
                (CVAttachment.nama_kandidat.ilike(f"%{s}%")) |
                (CVAttachment.kode_unik.ilike(f"%{s}%")) |
                (CVAttachment.file_name.ilike(f"%{s}%"))
            )

        if uploaded_by_filter:
            query = query.filter(CVAttachment.uploaded_by_name.ilike(f"%{uploaded_by_filter}%"))

        total = query.count()

        col1, col2 = st.columns(2)
        col1.metric("Total CV", total)

        if total > 0:
            df_all = pd.read_sql(query.statement, db.bind)
            total_size = df_all['file_size'].sum() if 'file_size' in df_all else 0
            col2.metric("Total Size", f"{total_size / (1024*1024):.2f} MB")

        if total == 0:
            st.info("Belum ada CV yang diupload.")
            return

        cv_list = query.limit(200).all()

        data = []
        for cv in cv_list:
            data.append({
                "ID": cv.id, "Nama Kandidat": cv.nama_kandidat, "Kode Unik": cv.kode_unik,
                "File": cv.file_name, "Size (KB)": round((cv.file_size or 0) / 1024, 1),
                "Upload By": cv.uploaded_by_name or "-",
                "Tgl Upload": cv.created_at.strftime("%d/%m/%Y %H:%M") if cv.created_at else "-",
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=400, hide_index=True)

        st.markdown("---")
        st.markdown("### 📂 Lihat & Download")

        select_options = {}
        for cv in cv_list:
            display = f"#{cv.id} | {cv.nama_kandidat} | {cv.file_name}"
            select_options[display] = cv.id

        selected_display = st.selectbox("Pilih CV", list(select_options.keys()), key="cv_view_select")
        selected_cv_id = select_options.get(selected_display)

        if selected_cv_id:
            cv_detail = db.query(CVAttachment).filter(CVAttachment.id == selected_cv_id).first()
            if cv_detail:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Kandidat:** {cv_detail.nama_kandidat}")
                    st.markdown(f"**Kode Unik:** {cv_detail.kode_unik}")
                    st.markdown(f"**File:** {cv_detail.file_name}")
                    st.markdown(f"**Size:** {(cv_detail.file_size or 0) / 1024:.1f} KB")
                    st.markdown(f"**Upload By:** {cv_detail.uploaded_by_name or '-'}")

                with col2:
                    try:
                        file_bytes = base64.b64decode(cv_detail.file_data)
                        st.download_button(
                            "⬇️ Download CV", file_bytes, cv_detail.file_name,
                            mime=cv_detail.file_type or "application/octet-stream",
                            key=f"dl_cv_mgr_{cv_detail.id}", use_container_width=True
                        )
                        file_lower = cv_detail.file_name.lower()
                        if file_lower.endswith(('.jpg', '.jpeg', '.png')):
                            st.image(file_bytes, caption=cv_detail.file_name, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

                if admin:
                    st.markdown("---")
                    if st.button("🗑️ Hapus CV Ini", type="secondary", key=f"del_cv_mgr_{cv_detail.id}"):
                        try:
                            db.delete(cv_detail)
                            db.commit()
                            st.success("CV berhasil dihapus!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            db.rollback()


def show_sourcing_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options,
                       pipeline_stages, initial_data=None, form_key="sourcing_form",
                       is_parse_mode=False, batch_mode=False):

    sumber_options = sourcing_options['sumber_options']
    jenjang_options = sourcing_options['jenjang_options']
    univ_options = sourcing_options['univ_options']
    jurusan_options = sourcing_options['jurusan_options']
    fmcg_options = sourcing_options['fmcg_options']
    pipeline_opts = pipeline_options

    nama = initial_data.get('nama', '') if initial_data else ''
    email = initial_data.get('email', '') if initial_data else ''
    hp = initial_data.get('hp', '') if initial_data else ''
    univ = initial_data.get('univ', '') if initial_data else ''
    univ_lain_init = initial_data.get('univ_lain', '') if initial_data else ''
    jurusan = initial_data.get('jurusan', '') if initial_data else ''
    jurusan_lain_init = initial_data.get('jurusan_lain', '') if initial_data else ''
    ipk = initial_data.get('ipk', '') if initial_data else ''
    tahun_lulus = initial_data.get('tahun_lulus', '') if initial_data else ''
    domisili = initial_data.get('domisili', '') if initial_data else ''
    jenjang = initial_data.get('jenjang', '') if initial_data else ''
    last_position = initial_data.get('last_position', '') if initial_data else ''
    last_company = initial_data.get('last_company', '') if initial_data else ''
    last_tenure = initial_data.get('last_tenure', '') if initial_data else ''
    total_tenure = initial_data.get('total_tenure', '') if initial_data else ''
    fmcg = initial_data.get('fmcg', '') if initial_data else ''
    sumber = initial_data.get('sumber', '') if initial_data else ''
    posisi = initial_data.get('posisi', '') if initial_data else ''
    kode_unik = initial_data.get('kode_unik', '') if initial_data else ''

    univ_original = univ
    if univ_original and univ_original not in univ_options:
        univ = "Lainnya"
        if not univ_lain_init:
            univ_lain_init = univ_original
    elif univ_original == "Lainnya":
        univ = "Lainnya"
    elif univ_original in univ_options and univ_original != "":
        univ = univ_original
        univ_lain_init = ""
    else:
        univ = ""
        univ_lain_init = ""

    jurusan_original = jurusan
    if jurusan_original and jurusan_original not in jurusan_options:
        jurusan = "Lainnya"
        if not jurusan_lain_init:
            jurusan_lain_init = jurusan_original
    elif jurusan_original == "Lainnya":
        jurusan = "Lainnya"
    elif jurusan_original in jurusan_options and jurusan_original != "":
        jurusan = jurusan_original
        jurusan_lain_init = ""
    else:
        jurusan = ""
        jurusan_lain_init = ""

    fptk_display = []
    fptk_map = {}
    fptk_posisi_map = {}
    fptk_level_map = {}
    for kode, pos, pic, lvl in fptk_options:
        display = f"{kode} - {pos[:50]}"
        fptk_display.append(display)
        fptk_map[display] = kode
        fptk_posisi_map[display] = pos
        fptk_level_map[display] = lvl

    default_fptk_index = 0
    if kode_unik or posisi:
        for idx, (kode, pos, pic, lvl) in enumerate(fptk_options):
            if kode_unik and kode == kode_unik:
                default_fptk_index = idx
                break
            if posisi and pos == posisi:
                default_fptk_index = idx
                break

    if is_parse_mode and initial_data:
        st.info(f"📋 Data dari parse: **{nama}**")

    model_options_local = [""] + get_model_options()

    with st.form(form_key):
        st.markdown("### 📋 Data Pribadi")
        col1, col2 = st.columns(2)
        with col1:
            nama_input = st.text_input("Nama *", value=nama)

            if fptk_display:
                selected_fptk = st.selectbox(
                    "Pilih FPTK (Kode Unik - Posisi)",
                    fptk_display,
                    index=min(default_fptk_index, len(fptk_display) - 1),
                    key=f"{form_key}_fptk_select"
                )
                kode_unik_input = fptk_map.get(selected_fptk, '')
                posisi_input = fptk_posisi_map.get(selected_fptk, '')
                level_input = fptk_level_map.get(selected_fptk, None)
                st.text_input("Kode Unik (auto)", value=kode_unik_input, disabled=True)
                st.text_input("Posisi (auto)", value=posisi_input, disabled=True)
            else:
                st.warning("⚠️ Tidak ada FPTK OP yang tersedia. Buat FPTK dulu.")
                kode_unik_input = ''
                posisi_input = ''
                level_input = None
                selected_fptk = None

            pic_recruiter_input = st.selectbox("PIC Recruiter *", [""] + pic_options, key=f"{form_key}_pic")
            hp_input = st.text_input("No HP", value=hp)
            email_input = st.text_input("Email", value=email)

            sumber_input = st.selectbox("Sumber *", [""] + sumber_options,
                                       index=([""] + sumber_options).index(sumber) if sumber in sumber_options else 0,
                                       key=f"{form_key}_sumber")

            auto_model = auto_detect_model_rekrutmen(posisi_input, level_input)
            model_default_idx = model_options_local.index(auto_model) if auto_model in model_options_local else 0
            st.caption(f"ℹ️ Model auto-detect dari posisi FPTK: **{auto_model or 'Belum terdeteksi'}**")
            model_rekrutmen_input = st.selectbox("Model Rekrutmen", model_options_local, index=model_default_idx, key=f"{form_key}_model")

            domisili_input = st.text_input("Domisili", value=domisili)

        with col2:
            jenjang_input = st.selectbox("Jenjang", [""] + jenjang_options,
                                        index=([""] + jenjang_options).index(jenjang) if jenjang in jenjang_options else 0,
                                        key=f"{form_key}_jenjang")

            default_univ_index = 0
            if univ in univ_options:
                default_univ_index = ([""] + univ_options).index(univ) if univ != "" else 0
            elif univ:
                default_univ_index = ([""] + univ_options).index("Lainnya")

            univ_input = st.selectbox("Universitas", [""] + univ_options, index=default_univ_index, key=f"{form_key}_univ")

            if univ_input == "Lainnya":
                univ_lain = st.text_input("Univ Lainnya *", value=univ_lain_init, key=f"{form_key}_univ_lain")
            else:
                univ_lain = ""

            tier_auto = get_university_tier(univ_input) if univ_input and univ_input != "Lainnya" else "Lainnya"
            st.text_input("University Tier (auto)", value=tier_auto, disabled=True)

            default_jur_index = 0
            if jurusan in jurusan_options:
                default_jur_index = ([""] + jurusan_options).index(jurusan) if jurusan != "" else 0
            elif jurusan:
                default_jur_index = ([""] + jurusan_options).index("Lainnya")

            jurusan_input = st.selectbox("Jurusan", [""] + jurusan_options, index=default_jur_index, key=f"{form_key}_jurusan")

            if jurusan_input == "Lainnya":
                jurusan_lain = st.text_input("Jurusan Lainnya *", value=jurusan_lain_init, key=f"{form_key}_jurusan_lain")
            else:
                jurusan_lain = ""

            ipk_input = st.text_input("IPK", value=ipk, placeholder="Contoh: 3.50")

            try:
                default_tahun = int(tahun_lulus) if tahun_lulus and str(tahun_lulus).isdigit() else None
            except Exception:
                default_tahun = None

            if default_tahun is not None and (default_tahun < 1990 or default_tahun > 2030):
                default_tahun = None

            tahun_lulus_input = st.number_input("Tahun Lulus", min_value=1990, max_value=2030, step=1, value=default_tahun)
            fmcg_input = st.selectbox("Pernah di FMCG?", [""] + fmcg_options,
                                     index=([""] + fmcg_options).index(fmcg) if fmcg in fmcg_options else 0,
                                     key=f"{form_key}_fmcg")

        st.markdown("---")
        st.markdown("### 💼 Riwayat Pekerjaan")
        col1, col2 = st.columns(2)
        with col1:
            last_position_input = st.text_input("Last Position", value=last_position)
            last_company_input = st.text_input("Last Company", value=last_company)
        with col2:
            last_tenure_input = st.text_input("Last Tenure", value=last_tenure)
            total_tenure_input = st.text_input("Total Tenure", value=total_tenure)

        st.markdown("---")
        st.markdown("### 📎 Lampiran CV")
        st.caption(f"Max {MAX_CV_SIZE_MB} MB per file. Format: {', '.join(ALLOWED_CV_EXT)}. Bisa multiple.")
        cv_files_input = st.file_uploader(
            "Upload CV (opsional)", type=ALLOWED_CV_EXT,
            accept_multiple_files=True, key=f"{form_key}_cv_uploader"
        )

        st.markdown("---")
        st.markdown("### 📊 Pipeline (Status awal)")
        pipeline_inputs = {}

        with st.expander("Sourcing Freelance", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                sf_input = st.selectbox("Sourcing Freelance", [""] + pipeline_opts, key=f"{form_key}_sf")
            with col2:
                if sf_input:
                    tsf_input = st.date_input("Tanggal Sourcing Freelance", datetime.now(), key=f"{form_key}_tsf")
                else:
                    tsf_input = None
                    st.date_input("Tanggal Sourcing Freelance", datetime.now(), disabled=True, key=f"{form_key}_tsf_dis")
            pipeline_inputs['sourcing_freelance'] = sf_input if sf_input else None
            pipeline_inputs['tanggal_sourcing_freelance'] = tsf_input if sf_input else None

        with st.expander("Sourcing HR", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                shr_input = st.selectbox("Sourcing HR", [""] + pipeline_opts, key=f"{form_key}_shr")
            with col2:
                if shr_input:
                    tshr_input = st.date_input("Tanggal Sourcing HR", datetime.now(), key=f"{form_key}_tshr")
                else:
                    tshr_input = None
                    st.date_input("Tanggal Sourcing HR", datetime.now(), disabled=True, key=f"{form_key}_tshr_dis")
            pipeline_inputs['sourcing_hr'] = shr_input if shr_input else None
            pipeline_inputs['tanggal_sourcing'] = tshr_input if shr_input else None
            pipeline_inputs['detail_keterangan_sourcing_hr'] = st.text_area("Detail Keterangan Sourcing HR", key=f"{form_key}_dkshr") or None

        with st.expander("Shortlist CV", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                scv_input = st.selectbox("Shortlist CV", [""] + pipeline_opts, key=f"{form_key}_scv")
            with col2:
                if scv_input:
                    tscv_input = st.date_input("Tanggal Shortlist CV", datetime.now(), key=f"{form_key}_tscv")
                else:
                    tscv_input = None
                    st.date_input("Tanggal Shortlist CV", datetime.now(), disabled=True, key=f"{form_key}_tscv_dis")
            pipeline_inputs['shortlist_cv'] = scv_input if scv_input else None
            pipeline_inputs['tanggal_shortlist_cv'] = tscv_input if scv_input else None
            pipeline_inputs['detail_keterangan_shortlist_cv'] = st.text_area("Detail Keterangan Shortlist CV", key=f"{form_key}_dkscv") or None

        with st.expander("Psikotes", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                psikotes_input = st.selectbox("Psikotes", [""] + pipeline_opts, key=f"{form_key}_psikotes")
                kode_psikotes_input = st.text_input("Kode Psikotes", key=f"{form_key}_kpsikotes")
            with col2:
                if psikotes_input:
                    tpsikotes_input = st.date_input("Tanggal Psikotes", datetime.now(), key=f"{form_key}_tpsikotes")
                else:
                    tpsikotes_input = None
                    st.date_input("Tanggal Psikotes", datetime.now(), disabled=True, key=f"{form_key}_tpsikotes_dis")
                nilai_logika_input = st.text_input("Nilai Logika", key=f"{form_key}_nlogika")
                nilai_iq_input = st.text_input("Nilai IQ", key=f"{form_key}_niq")
            col3, col4 = st.columns(2)
            with col3:
                nilai_daya_tangkap_input = st.text_input("Nilai Daya Tangkap", key=f"{form_key}_ndaya")
                nilai_ra_input = st.text_input("Nilai RA", key=f"{form_key}_nra")
            with col4:
                disc_input = st.text_input("DISC", key=f"{form_key}_disc")

            pipeline_inputs['psikotes'] = psikotes_input if psikotes_input else None
            pipeline_inputs['kode_psikotes'] = kode_psikotes_input or None
            pipeline_inputs['nilai_logika'] = nilai_logika_input or None
            pipeline_inputs['nilai_iq'] = nilai_iq_input or None
            pipeline_inputs['nilai_daya_tangkap'] = nilai_daya_tangkap_input or None
            pipeline_inputs['nilai_ra'] = nilai_ra_input or None
            pipeline_inputs['disc'] = disc_input or None
            pipeline_inputs['tanggal_psikotes'] = tpsikotes_input if psikotes_input else None
            pipeline_inputs['detail_keterangan_psikotes'] = st.text_area("Detail Keterangan Psikotes", key=f"{form_key}_dkpsikotes") or None

        with st.expander("HR Interview", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                hri_input = st.selectbox("HR Interview", [""] + pipeline_opts, key=f"{form_key}_hri")
            with col2:
                if hri_input:
                    thri_input = st.date_input("Tanggal HR Interview", datetime.now(), key=f"{form_key}_thri")
                else:
                    thri_input = None
                    st.date_input("Tanggal HR Interview", datetime.now(), disabled=True, key=f"{form_key}_thri_dis")
            pipeline_inputs['hr_interview'] = hri_input if hri_input else None
            pipeline_inputs['tanggal_hr_interview'] = thri_input if hri_input else None
            pipeline_inputs['detail_keterangan_hr_interview'] = st.text_area("Detail Keterangan HR Interview", key=f"{form_key}_dkhri") or None

        with st.expander("Technical Test / Case Study", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                tt_input = st.selectbox("Technical Test", [""] + pipeline_opts, key=f"{form_key}_tt")
            with col2:
                if tt_input:
                    ttt_input = st.date_input("Tanggal Technical Test", datetime.now(), key=f"{form_key}_ttt")
                else:
                    ttt_input = None
                    st.date_input("Tanggal Technical Test", datetime.now(), disabled=True, key=f"{form_key}_ttt_dis")
            pipeline_inputs['technical_test_case_study'] = tt_input if tt_input else None
            pipeline_inputs['tanggal_technical_test'] = ttt_input if tt_input else None
            pipeline_inputs['detail_keterangan_technical_test'] = st.text_area("Detail Keterangan Technical Test", key=f"{form_key}_dktt") or None

        with st.expander("Market Visit", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                mv_input = st.selectbox("Market Visit", [""] + pipeline_opts, key=f"{form_key}_mv")
            with col2:
                if mv_input:
                    tmv_input = st.date_input("Tanggal Market Visit", datetime.now(), key=f"{form_key}_tmv")
                else:
                    tmv_input = None
                    st.date_input("Tanggal Market Visit", datetime.now(), disabled=True, key=f"{form_key}_tmv_dis")
            pipeline_inputs['market_visit'] = mv_input if mv_input else None
            pipeline_inputs['tanggal_market_visit'] = tmv_input if mv_input else None
            pipeline_inputs['detail_market_visit'] = st.text_area("Detail Market Visit", key=f"{form_key}_dkmv") or None

        with st.expander("User Interview", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                ui_input = st.selectbox("User Interview", [""] + pipeline_opts, key=f"{form_key}_ui")
            with col2:
                if ui_input:
                    tui_input = st.date_input("Tanggal User Interview", datetime.now(), key=f"{form_key}_tui")
                else:
                    tui_input = None
                    st.date_input("Tanggal User Interview", datetime.now(), disabled=True, key=f"{form_key}_tui_dis")
            pipeline_inputs['user_interview'] = ui_input if ui_input else None
            pipeline_inputs['tanggal_user_interview'] = tui_input if ui_input else None
            pipeline_inputs['detail_keterangan_user_interview'] = st.text_area("Detail Keterangan User Interview", key=f"{form_key}_dkui") or None

        with st.expander("Panel Interview", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                pi_input = st.selectbox("Panel Interview", [""] + pipeline_opts, key=f"{form_key}_pi")
            with col2:
                if pi_input:
                    tpi_input = st.date_input("Tanggal Panel Interview", datetime.now(), key=f"{form_key}_tpi")
                else:
                    tpi_input = None
                    st.date_input("Tanggal Panel Interview", datetime.now(), disabled=True, key=f"{form_key}_tpi_dis")
            pipeline_inputs['panel_interview'] = pi_input if pi_input else None
            pipeline_inputs['tanggal_panel_interview'] = tpi_input if pi_input else None
            pipeline_inputs['detail_keterangan_panel_interview'] = st.text_area("Detail Keterangan Panel Interview", key=f"{form_key}_dkpi") or None

        with st.expander("Reference Check", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                rc_input = st.selectbox("Reference Check", [""] + pipeline_opts, key=f"{form_key}_rc")
            with col2:
                if rc_input:
                    trc_input = st.date_input("Tanggal Reference Check", datetime.now(), key=f"{form_key}_trc")
                else:
                    trc_input = None
                    st.date_input("Tanggal Reference Check", datetime.now(), disabled=True, key=f"{form_key}_trc_dis")
            pipeline_inputs['reference_check'] = rc_input if rc_input else None
            pipeline_inputs['tanggal_reference_check'] = trc_input if rc_input else None
            pipeline_inputs['detail_keterangan_reference_check'] = st.text_area("Detail Keterangan Reference Check", key=f"{form_key}_dkrc") or None

        with st.expander("MCU", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                mcu_input = st.selectbox("MCU", [""] + pipeline_opts, key=f"{form_key}_mcu")
            with col2:
                if mcu_input:
                    tmcu_input = st.date_input("Tanggal MCU", datetime.now(), key=f"{form_key}_tmcu")
                else:
                    tmcu_input = None
                    st.date_input("Tanggal MCU", datetime.now(), disabled=True, key=f"{form_key}_tmcu_dis")
            pipeline_inputs['mcu'] = mcu_input if mcu_input else None
            pipeline_inputs['tanggal_mcu'] = tmcu_input if mcu_input else None
            pipeline_inputs['detail_keterangan_mcu'] = st.text_area("Detail Keterangan MCU", key=f"{form_key}_dkmcu") or None

        with st.expander("Offering", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                off_input = st.selectbox("Offering", [""] + pipeline_opts, key=f"{form_key}_off")
            with col2:
                if off_input:
                    toff_input = st.date_input("Tanggal Offering", datetime.now(), key=f"{form_key}_toff")
                else:
                    toff_input = None
                    st.date_input("Tanggal Offering", datetime.now(), disabled=True, key=f"{form_key}_toff_dis")
            pipeline_inputs['offering'] = off_input if off_input else None
            pipeline_inputs['tanggal_offering'] = toff_input if off_input else None
            pipeline_inputs['detail_keterangan_offering'] = st.text_area("Detail Keterangan Offering", key=f"{form_key}_dkoff") or None

        with st.expander("Day 1", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                d1_input = st.selectbox("Day 1", [""] + pipeline_opts, key=f"{form_key}_d1")
            with col2:
                if d1_input:
                    td1_input = st.date_input("Tanggal Day 1", datetime.now(), key=f"{form_key}_td1")
                else:
                    td1_input = None
                    st.date_input("Tanggal Day 1", datetime.now(), disabled=True, key=f"{form_key}_td1_dis")
            pipeline_inputs['day1'] = d1_input if d1_input else None
            pipeline_inputs['tanggal_day1'] = td1_input if d1_input else None
            pipeline_inputs['detail_keterangan_day1'] = st.text_area("Detail Keterangan Day 1", key=f"{form_key}_dkd1") or None

        st.markdown("---")
        st.markdown("### 📝 Catatan")
        notes_input = st.text_area("Notes / Catatan", key=f"{form_key}_notes") or None

        col1, col2 = st.columns([1, 4])
        with col1:
            submitted = st.form_submit_button("💾 Simpan", type="primary")
        if is_parse_mode:
            with col2:
                if st.form_submit_button("🔄 Reset / Parse Ulang", type="secondary"):
                    st.session_state.parsed_cv_data = {}
                    st.session_state.show_parsed_form = False
                    for k in list(st.session_state.keys()):
                        if k.startswith(form_key):
                            del st.session_state[k]
                    st.rerun()

    if submitted:
        errors = []
        if not nama_input:
            errors.append("Nama wajib diisi")
        if not sumber_input:
            errors.append("Sumber wajib diisi")
        if not pic_recruiter_input:
            errors.append("PIC Recruiter wajib diisi")
        if not fptk_display:
            errors.append("Tidak ada FPTK OP yang tersedia")
        elif not selected_fptk:
            errors.append("Pilih FPTK")
        if univ_input == "Lainnya" and not univ_lain:
            errors.append("Universitas Lainnya wajib diisi karena memilih 'Lainnya'")
        if jurusan_input == "Lainnya" and not jurusan_lain:
            errors.append("Jurusan Lainnya wajib diisi karena memilih 'Lainnya'")

        if errors:
            for err in errors:
                st.error(f"❌ {err}")
        else:
            duplicates = find_duplicate_candidates(db, nama_input, email=email_input, nomor_hp=hp_input)
            dup_action = st.session_state.get("duplicate_action", None)

            if duplicates and dup_action is None:
                show_duplicate_warning_dialog(db, nama_input, email_input, hp_input)
                st.stop()

            if dup_action == "cancel":
                st.session_state["duplicate_action"] = None
                st.info("❌ Input dibatalkan.")
                st.stop()

            if duplicates and dup_action == "transfer":
                st.session_state["duplicate_action"] = None
                st.info("🔄 Silakan pilih FPTK tujuan di halaman **Sourcing View → tab Transfer Kandidat**.")
                st.stop()

            st.session_state["duplicate_action"] = None

            try:
                existing = db.query(DBSourcing).filter(DBSourcing.nama == nama_input).first()
                if existing:
                    st.warning(f"⚠️ Nama '{nama_input}' sudah ada di database.")

                last_no = db.query(DBSourcing).order_by(DBSourcing.no.desc()).first()
                next_no = (last_no.no + 1) if last_no and last_no.no else 1

                tier_final = get_university_tier(univ_input) if univ_input and univ_input != "Lainnya" else "Lainnya"

                new = DBSourcing(
                    no=next_no,
                    nama=nama_input,
                    posisi=posisi_input,
                    kode_unik=kode_unik_input,
                    rekruter=pic_recruiter_input,
                    sumber_sourcing=sumber_input,
                    model_rekrutmen=model_rekrutmen_input if model_rekrutmen_input else None,
                    domisili=domisili_input,
                    jenjang_pendidikan=jenjang_input,
                    nama_universitas_top10=univ_input if univ_input != "Lainnya" else "",
                    nama_universitas_lainnya=univ_lain if univ_input == "Lainnya" else "",
                    jurusan=jurusan_input if jurusan_input != "Lainnya" else "",
                    jurusan_lainnya=jurusan_lain if jurusan_input == "Lainnya" else "",
                    university_tier=tier_final,
                    ipk=safe_float(ipk_input.replace(',', '.')) if ipk_input else None,
                    tahun_lulus=tahun_lulus_input if tahun_lulus_input and tahun_lulus_input > 0 else None,
                    nomor_hp=hp_input,
                    email=email_input,
                    last_position=last_position_input,
                    last_company=last_company_input,
                    last_tenure=last_tenure_input,
                    total_tenure=total_tenure_input,
                    pernah_di_fmcg=fmcg_input,
                    sourcing_date=datetime.now().date(),
                    notes=notes_input,
                    source_user_id=user.id,
                    created_at=datetime.now(),
                    last_compile_action="MANUAL_INPUT"
                )

                for field_name, value in pipeline_inputs.items():
                    if hasattr(new, field_name):
                        setattr(new, field_name, value)

                db.add(new)
                db.commit()
                db.refresh(new)

                st.success(f"✅ '{nama_input}' berhasil disimpan! Tier: {tier_final}")

                if cv_files_input:
                    saved, cv_errors = save_cv_attachments(
                        db, new.id, kode_unik_input, nama_input,
                        cv_files_input, user
                    )
                    if saved > 0:
                        st.info(f"📎 {saved} CV berhasil diupload!")
                    if cv_errors:
                        st.warning(f"⚠️ {len(cv_errors)} CV gagal:")
                        for err in cv_errors:
                            st.text(err)

                st.balloons()

                if is_parse_mode:
                    st.session_state.parsed_cv_data = {}
                    st.session_state.show_parsed_form = False
                    for k in list(st.session_state.keys()):
                        if k.startswith(form_key):
                            del st.session_state[k]

                if batch_mode:
                    if 'batch_index' in st.session_state:
                        st.session_state.batch_index += 1
                    st.rerun()

                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()


def show_manual_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options):
    pipeline_stages = [
        {"field": "sourcing_freelance", "label": "Sourcing Freelance"},
        {"field": "sourcing_hr", "label": "Sourcing HR"},
        {"field": "shortlist_cv", "label": "Shortlist CV"},
        {"field": "psikotes", "label": "Psikotes"},
        {"field": "hr_interview", "label": "HR Interview"},
        {"field": "technical_test_case_study", "label": "Technical Test / Case Study"},
        {"field": "market_visit", "label": "Market Visit"},
        {"field": "user_interview", "label": "User Interview"},
        {"field": "panel_interview", "label": "Panel Interview"},
        {"field": "reference_check", "label": "Reference Check"},
        {"field": "mcu", "label": "MCU"},
        {"field": "offering", "label": "Offering"},
        {"field": "day1", "label": "Day 1"}
    ]

    show_sourcing_form(
        db=db, user=user, pic_options=pic_options,
        fptk_options=fptk_options, sourcing_options=sourcing_options,
        pipeline_options=pipeline_options, pipeline_stages=pipeline_stages,
        initial_data=None, form_key="form_manual",
        is_parse_mode=False, batch_mode=False
    )
