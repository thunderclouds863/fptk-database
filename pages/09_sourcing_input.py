import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import get_db
from core.models import DBSourcing, FPTK, MasterDropdown
from core.auth import get_current_user, is_it, is_editor
from core.utils import safe_int, parse_phone, is_valid_email
import time
import re

COPILOT_AGENT_URL = "https://m365.cloud.microsoft/chat/?titleId=T_e0524666-839c-757c-7ef5-d5e72311417d&source=embedded-builder"

# ============================================================
# CACHE FUNCTIONS
# ============================================================

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
        {"field": "sourcing_freelance", "label": "Sourcing Freelance", "desc": "Sourcing oleh freelance"},
        {"field": "sourcing_hr", "label": "Sourcing HR", "desc": "Sourcing oleh HR internal"},
        {"field": "shortlist_cv", "label": "Shortlist CV", "desc": "CV sudah di-shortlist"},
        {"field": "psikotes", "label": "Psikotes", "desc": "Tes psikotes"},
        {"field": "hr_interview", "label": "HR Interview", "desc": "Interview dengan HR"},
        {"field": "technical_test_case_study", "label": "Technical Test / Case Study", "desc": "Tes teknis / case study"},
        {"field": "market_visit", "label": "Market Visit", "desc": "Kunjungan ke pasar / outlet"},
        {"field": "user_interview", "label": "User Interview", "desc": "Interview dengan user"},
        {"field": "panel_interview", "label": "Panel Interview", "desc": "Interview panel"},
        {"field": "reference_check", "label": "Reference Check", "desc": "Cek referensi"},
        {"field": "mcu", "label": "MCU", "desc": "Medical Check Up"},
        {"field": "offering", "label": "Offering", "desc": "Penawaran"},
        {"field": "day1", "label": "Day 1", "desc": "Hari pertama kerja"}
    ]


# ============================================================
# UNIVERSITY TIER MAP
# ============================================================

UNIV_TIER_MAP = {
    "Universitas Indonesia": "Top 3 PTN",
    "Universitas Gadjah Mada": "Top 3 PTN",
    "Institut Teknologi Bandung": "Top 3 PTN",
    "Universitas Airlangga": "Top 10 PTN",
    "IPB University": "Top 10 PTN",
    "Institut Teknologi Sepuluh Nopember": "Top 10 PTN",
    "Universitas Padjadjaran": "Top 10 PTN",
    "Universitas Diponegoro": "Top 10 PTN",
    "Universitas Brawijaya": "Top 10 PTN",
    "Universitas Hasanuddin": "Top 20 PTN",
    "Universitas Sebelas Maret": "Top 20 PTN",
    "Universitas Sumatera Utara": "Top 20 PTN",
    "Universitas Pendidikan Indonesia": "Top 20 PTN",
    "Universitas Negeri Yogyakarta": "Top 20 PTN",
    "Universitas Negeri Padang": "Top 20 PTN",
    "Universitas Negeri Malang": "Top 20 PTN",
    "Universitas Syiah Kuala": "Top 20 PTN",
    "Universitas Andalas": "Top 20 PTN",
    "Universitas Udayana": "Top 20 PTN",
    "Universitas Negeri Semarang": "Top 20 PTN",
    "Bina Nusantara University": "Top 10 PTS",
    "Telkom University": "Top 10 PTS",
    "Institut Teknologi Nasional Bandung": "Top 10 PTS",
    "Universitas Muhammadiyah Yogyakarta": "Top 10 PTS",
    "Universitas Katolik Indonesia Atma Jaya": "Top 10 PTS",
    "Universitas Islam Indonesia": "Top 10 PTS",
    "Universitas Kristen Petra": "Top 10 PTS",
    "Universitas Trisakti": "Top 10 PTS",
    "Universitas Pelita Harapan": "Top 10 PTS",
    "Swiss German University": "Top 10 PTS",
}


# ============================================================
# NORMALIZER
# ============================================================

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
    "Manajemen": ["manajemen", "management"],
    "Akuntansi": ["akuntansi", "accounting"],
    "Teknik Industri": ["teknik industri", "industrial engineering"],
    "Teknik Informatika": ["teknik informatika", "informatics", "computer science", "ilmu komputer"],
    "Sistem Informasi": ["sistem informasi", "information system"],
    "Psikologi": ["psikologi", "psychology"],
    "Ilmu Komunikasi": ["ilmu komunikasi", "communication science", "komunikasi"],
    "Hukum": ["hukum", "law"],
    "Ekonomi": ["ekonomi", "economics"],
}

GENERIC_UNIV_WORDS = {"universitas", "university", "univ", "sekolah", "school"}
GENERIC_JURUSAN_WORDS = {"jurusan", "major", "program studi", "prodi", "department"}


def _clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_univ(raw_val: str):
    if not raw_val or not str(raw_val).strip():
        return "", ""
    raw_clean = _clean_text(str(raw_val))
    for canonical, aliases in UNIV_ALIASES.items():
        for alias in aliases:
            if raw_clean == alias or re.search(rf"\b{re.escape(alias)}\b", raw_clean):
                return canonical, ""
    pretty = " ".join([w.capitalize() for w in str(raw_val).split()])
    return "Lainnya", pretty


def get_university_tier(univ_name: str) -> str:
    if not univ_name:
        return ""
    return UNIV_TIER_MAP.get(univ_name, "Lainnya")


def normalize_jurusan(raw_val: str):
    if not raw_val or not str(raw_val).strip():
        return "", ""
    raw_clean = _clean_text(str(raw_val))
    for canonical, aliases in JURUSAN_ALIASES.items():
        for alias in aliases:
            if raw_clean == alias or re.search(rf"\b{re.escape(alias)}\b", raw_clean):
                return canonical, ""
    pretty = " ".join([w.capitalize() for w in str(raw_val).split()])
    return "Lainnya", pretty


# ============================================================
# PREPROCESS
# ============================================================

KNOWN_LABELS = [
    "Jenjang Pendidikan",
    "Nama Universitas/Sekolah",
    "Nama Universitas/sekolah",
    "Nama Universitas",
    "Nama Sekolah",
    "University Tier",
    "Ipk Tier",
    "IPK Tier",
    "Nomor Hp",
    "Nomor HP",
    "Pernah Di Fmcg?",
    "Pernah di FMCG?",
    "Pernah Di FMCG",
    "Pernah di Fmcg",
    "Last Position",
    "Last Tenure",
    "Last Company",
    "Total Tenure",
    "Tahun Lulus",
    "Kode Unik",
    "Posisi FPTK",
    "Sumber",
    "Jurusan",
    "Domisili",
    "Email",
    "Nama",
    "Ipk",
    "IPK",
    "HP",
]


def preprocess_cv_text(raw_text: str) -> str:
    if not raw_text:
        return raw_text
    if raw_text.count('\n') > 3:
        return raw_text

    text = raw_text
    labels_sorted = sorted(KNOWN_LABELS, key=len, reverse=True)

    for label in labels_sorted:
        pattern = re.compile(
            r'(?i)(?<!^)\s*(' + re.escape(label) + r'\s*:)',
            re.IGNORECASE
        )
        text = pattern.sub(r'\n\1', text)

    text = text.lstrip('\n')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


# ============================================================
# PARSE CV
# ============================================================

def parse_cv_text(raw_text: str) -> dict:
    parsed = {
        'nama': '', 'email': '', 'hp': '',
        'univ': '', 'univ_lain': '',
        'jurusan': '', 'jurusan_lain': '',
        'ipk': '', 'tahun_lulus': '', 'domisili': '',
        'last_position': '', 'last_company': '',
        'last_tenure': '', 'total_tenure': '',
        'sumber': '', 'posisi': '', 'kode_unik': '',
        'jenjang': '', 'fmcg': '',
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

    year_match = re.search(r'(20[0-9]{2})', raw_text)
    if year_match:
        parsed['tahun_lulus'] = year_match.group()

    univ_label_seen = False
    jurusan_label_seen = False

    for line in lines:
        line = line.strip()
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()

            # Tandai label sudah muncul (walau val kosong)
            if any(k in key for k in ['nama universitas', 'universitas', 'university', 'univ', 'sekolah']):
                univ_label_seen = True
            if any(k in key for k in ['jurusan', 'major']):
                jurusan_label_seen = True

            # Khusus jurusan: kalau label ada tapi kosong → tetap "Lainnya" + field kosong
            if any(k in key for k in ['jurusan', 'major']):
                if not val:
                    parsed['jurusan'] = "Lainnya"
                    parsed['jurusan_lain'] = ""
                    continue

            # Khusus univ: kalau label ada tapi kosong → tetap "Lainnya" + field kosong
            if any(k in key for k in ['nama universitas', 'universitas', 'university', 'univ', 'sekolah']):
                if not val:
                    parsed['univ'] = "Lainnya"
                    parsed['univ_lain'] = ""
                    parsed['university_tier'] = "Lainnya"
                    continue

            if not val:
                continue

            # URUTAN: cek univ SEBELUM nama
            if any(k in key for k in ['nama universitas', 'universitas', 'university', 'univ', 'sekolah']):
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

    # Fallback nama
    if not parsed['nama']:
        for line in lines:
            line = line.strip()
            if line and ':' not in line and len(line) > 2 and not line.startswith('http'):
                parsed['nama'] = line
                break

    # Fallback jenjang
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

    # Fallback FMCG
    if not parsed['fmcg']:
        tl = raw_text.lower()
        if 'fmcg' in tl:
            if 'ya' in tl or 'yes' in tl:
                parsed['fmcg'] = 'Ya'
            elif 'tidak' in tl or 'no' in tl:
                parsed['fmcg'] = 'Tidak'

    # Fallback univ — hanya kalau label univ TIDAK PERNAH muncul
    if not parsed['univ'] and not univ_label_seen:
        univ_dd, univ_lain = normalize_univ(raw_text)
        if univ_dd and univ_dd != "Lainnya":
            parsed['univ'] = univ_dd
            parsed['university_tier'] = get_university_tier(univ_dd)
        elif univ_dd == "Lainnya" and univ_lain:
            ul_clean = univ_lain.strip().lower()
            if ul_clean not in GENERIC_UNIV_WORDS:
                parsed['univ'] = "Lainnya"
                parsed['univ_lain'] = univ_lain
                parsed['university_tier'] = "Lainnya"

    # Fallback jurusan — hanya kalau label jurusan TIDAK PERNAH muncul
    if not parsed['jurusan'] and not jurusan_label_seen:
        jur_dd, jur_lain = normalize_jurusan(raw_text)
        if jur_dd and jur_dd != "Lainnya":
            parsed['jurusan'] = jur_dd
        elif jur_dd == "Lainnya" and jur_lain:
            jl_clean = jur_lain.strip().lower()
            if jl_clean not in GENERIC_JURUSAN_WORDS:
                parsed['jurusan'] = "Lainnya"
                parsed['jurusan_lain'] = jur_lain

    return parsed


# ============================================================
# MAIN ENTRY
# ============================================================

def show_sourcing_input():
    st.title("👤 Input Sourcing / CV")
    st.markdown("Input kandidat baru ke DB Sourcing")

    db = next(get_db())
    if not is_editor(db):
        st.error("❌ Anda tidak memiliki akses untuk input sourcing. Hubungi Admin.")
        return
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login.")
        return

    with st.spinner("📋 Memuat data..."):
        master_options = get_master_options_sourcing(db)
        sourcing_options = get_sourcing_options()
        pipeline_stages = get_pipeline_stages()

        fptk_list = db.query(FPTK).filter(FPTK.status == 'OP').order_by(FPTK.kode_unik).all()
        fptk_options = [(f.kode_unik, f.posisi, f.pic_recruiter) for f in fptk_list]

    pic_options = master_options['pic_options']
    pipeline_options = sourcing_options['pipeline_options']

    if 'parsed_cv_data' not in st.session_state:
        st.session_state.parsed_cv_data = {}
    if 'show_parsed_form' not in st.session_state:
        st.session_state.show_parsed_form = False

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

    tab1, tab2, tab3 = st.tabs(["📝 Manual Input", "📋 Paste Text", "📦 Batch CV"])

    with tab1:
        st.subheader("Manual Input Kandidat")
        show_manual_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options)

    with tab2:
        st.subheader("Paste Text CV")
        st.caption("Paste hasil copy dari Jobstreet / LinkedIn / Copilot Agent")

        raw_text = st.text_area("Paste teks CV di sini", height=150)

        col1, col2 = st.columns([1, 4])
        with col1:
            parse_btn = st.button("🔍 Parse & Tampilkan di Form", use_container_width=True, type="primary")

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
                db=db, user=user,
                pic_options=pic_options,
                fptk_options=fptk_options,
                sourcing_options=sourcing_options,
                pipeline_options=pipeline_options,
                initial_data=st.session_state.parsed_cv_data,
                form_key="form_parse_edit",
                is_parse_mode=True
            )

    with tab3:
        st.subheader("Batch Paste CV (Banyak Kandidat)")
        st.caption("Paste hasil dari Copilot Agent atau multiple CV. Pisahkan dengan separator.")

        separator = st.text_input("Separator kandidat", value="=== CV ===")
        batch_text = st.text_area("Paste batch CV di sini", height=300)

        if batch_text and st.button("🚀 Proses Batch", type="primary"):
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
                        db=db, user=user,
                        pic_options=pic_options,
                        fptk_options=fptk_options,
                        sourcing_options=sourcing_options,
                        pipeline_options=pipeline_options,
                        initial_data=parsed,
                        form_key=f"form_batch_{idx}",
                        is_parse_mode=True,
                        batch_mode=True
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


# ============================================================
# FORM SOURCING (REUSABLE)
# ============================================================

def show_sourcing_form(db, user, pic_options, fptk_options, sourcing_options, pipeline_options,
                       initial_data=None, form_key="sourcing_form", is_parse_mode=False, batch_mode=False):

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

    # ============================================================
    # AUTO-FIX UNIV & JURUSAN
    # Kalau nilai TIDAK ADA di dropdown → pilih "Lainnya"
    # Kalau sudah "Lainnya" → tetap "Lainnya" (field Lainnya bisa kosong)
    # ============================================================

    # ---------- UNIVERSITAS ----------
    univ_original = univ
    if univ_original and univ_original not in univ_options:
        univ = "Lainnya"
        if not univ_lain_init and univ_original.strip().lower() not in GENERIC_UNIV_WORDS:
            univ_lain_init = univ_original
    elif univ_original == "Lainnya":
        # Tetap "Lainnya", biarkan field Lainnya apa adanya (bisa kosong)
        univ = "Lainnya"
        if univ_lain_init and univ_lain_init.strip().lower() in GENERIC_UNIV_WORDS:
            univ_lain_init = ""
    elif univ_original in univ_options and univ_original != "":
        univ = univ_original
        univ_lain_init = ""
    else:
        univ = ""
        univ_lain_init = ""

    # ---------- JURUSAN ----------
    jurusan_original = jurusan
    if jurusan_original and jurusan_original not in jurusan_options:
        jurusan = "Lainnya"
        if not jurusan_lain_init and jurusan_original.strip().lower() not in GENERIC_JURUSAN_WORDS:
            jurusan_lain_init = jurusan_original
    elif jurusan_original == "Lainnya":
        # Tetap "Lainnya", biarkan field Lainnya apa adanya (bisa kosong)
        jurusan = "Lainnya"
        if jurusan_lain_init and jurusan_lain_init.strip().lower() in GENERIC_JURUSAN_WORDS:
            jurusan_lain_init = ""
    elif jurusan_original in jurusan_options and jurusan_original != "":
        jurusan = jurusan_original
        jurusan_lain_init = ""
    else:
        jurusan = ""
        jurusan_lain_init = ""

    # FPTK dropdown
    fptk_display = []
    fptk_map = {}
    fptk_posisi_map = {}
    for kode, pos, pic in fptk_options:
        display = f"{kode} - {pos[:50]}"
        fptk_display.append(display)
        fptk_map[display] = kode
        fptk_posisi_map[display] = pos

    default_fptk_index = 0
    if kode_unik or posisi:
        for idx, (kode, pos, pic) in enumerate(fptk_options):
            if kode_unik and kode == kode_unik:
                default_fptk_index = idx
                break
            if posisi and pos == pos:
                default_fptk_index = idx
                break

    if is_parse_mode and initial_data:
        st.info(f"📋 Data dari parse: **{nama}**")

    with st.form(form_key):
        col1, col2 = st.columns(2)
        with col1:
            nama_input = st.text_input("Nama *", value=nama)

            if fptk_display:
                selected_fptk = st.selectbox(
                    "Pilih FPTK (Kode Unik - Posisi)",
                    fptk_display,
                    index=min(default_fptk_index, len(fptk_display) - 1)
                )
                kode_unik_input = fptk_map.get(selected_fptk, '')
                posisi_input = fptk_posisi_map.get(selected_fptk, '')
                st.text_input("Kode Unik (auto)", value=kode_unik_input, disabled=True)
                st.text_input("Posisi (auto)", value=posisi_input, disabled=True)
            else:
                st.warning("⚠️ Tidak ada FPTK OP yang tersedia. Buat FPTK dulu.")
                kode_unik_input = ''
                posisi_input = ''
                selected_fptk = None

            pic_recruiter_input = st.selectbox("PIC Recruiter *", [""] + pic_options)
            hp_input = st.text_input("No HP", value=hp)
            email_input = st.text_input("Email", value=email)
            sumber_input = st.selectbox("Sumber *", [""] + sumber_options,
                                       index=([""] + sumber_options).index(sumber) if sumber in sumber_options else 0)
            domisili_input = st.text_input("Domisili", value=domisili)

        with col2:
            jenjang_input = st.selectbox("Jenjang", [""] + jenjang_options,
                                        index=([""] + jenjang_options).index(jenjang) if jenjang in jenjang_options else 0)

            # UNIVERSITAS
            default_univ_index = 0
            if univ in univ_options:
                default_univ_index = ([""] + univ_options).index(univ) if univ != "" else 0
            elif univ:
                default_univ_index = ([""] + univ_options).index("Lainnya")

            univ_input = st.selectbox(
                "Universitas", [""] + univ_options,
                index=default_univ_index,
                key=f"{form_key}_univ"
            )

            if univ_input == "Lainnya":
                univ_lain = st.text_input(
                    "Univ Lainnya *",
                    value=univ_lain_init
                    # key DIHILANGKAN → tidak nyangkut antar render
                )
            else:
                univ_lain = ""

            tier_auto = get_university_tier(univ_input) if univ_input and univ_input != "Lainnya" else "Lainnya"
            st.text_input("University Tier (auto)", value=tier_auto, disabled=True)

            # JURUSAN
            default_jur_index = 0
            if jurusan in jurusan_options:
                default_jur_index = ([""] + jurusan_options).index(jurusan) if jurusan != "" else 0
            elif jurusan:
                default_jur_index = ([""] + jurusan_options).index("Lainnya")

            jurusan_input = st.selectbox(
                "Jurusan", [""] + jurusan_options,
                index=default_jur_index,
                key=f"{form_key}_jurusan"
            )

            if jurusan_input == "Lainnya":
                jurusan_lain = st.text_input(
                    "Jurusan Lainnya *",
                    value=jurusan_lain_init
                    # key DIHILANGKAN → tidak nyangkut antar render
                )
            else:
                jurusan_lain = ""

            ipk_input = st.text_input("IPK", value=ipk, placeholder="Contoh: 3.50")

            try:
                default_tahun = int(tahun_lulus) if tahun_lulus and str(tahun_lulus).isdigit() else None
            except:
                default_tahun = None
            tahun_lulus_input = st.number_input("Tahun Lulus", min_value=1990, max_value=2030, step=1,
                                                value=default_tahun)
            fmcg_input = st.selectbox("Pernah di FMCG?", [""] + fmcg_options,
                                     index=([""] + fmcg_options).index(fmcg) if fmcg in fmcg_options else 0)

        st.markdown("---")
        st.markdown("### Riwayat Pekerjaan")
        col1, col2 = st.columns(2)
        with col1:
            last_position_input = st.text_input("Last Position", value=last_position)
            last_company_input = st.text_input("Last Company", value=last_company)
        with col2:
            last_tenure_input = st.text_input("Last Tenure", value=last_tenure)
            total_tenure_input = st.text_input("Total Tenure", value=total_tenure)

        st.markdown("---")
        st.markdown("### Pipeline (Status awal)")
        st.markdown("#### Sourcing Freelance (Pipeline Awal)")
        col1, col2 = st.columns(2)
        with col1:
            sourcing_freelance_input = st.selectbox("Sourcing Freelance", [""] + pipeline_opts)
        with col2:
            if sourcing_freelance_input:
                tanggal_sourcing_freelance_input = st.date_input("Tanggal Sourcing Freelance", datetime.now())
            else:
                tanggal_sourcing_freelance_input = None
                st.date_input("Tanggal Sourcing Freelance", datetime.now(), disabled=True)

        st.markdown("#### Sourcing HR")
        col1, col2 = st.columns(2)
        with col1:
            sourcing_hr_input = st.selectbox("Sourcing HR", [""] + pipeline_opts)
        with col2:
            if sourcing_hr_input:
                tanggal_sourcing_input = st.date_input("Tanggal Sourcing HR", datetime.now())
            else:
                tanggal_sourcing_input = None
                st.date_input("Tanggal Sourcing HR", datetime.now(), disabled=True)

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
            try:
                existing = db.query(DBSourcing).filter(DBSourcing.nama == nama_input).first()
                if existing:
                    st.warning(f"⚠️ Nama '{nama_input}' sudah ada!")

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
                    domisili=domisili_input,
                    jenjang_pendidikan=jenjang_input,
                    nama_universitas_top10=univ_input if univ_input != "Lainnya" else "",
                    nama_universitas_lainnya=univ_lain if univ_input == "Lainnya" else "",
                    jurusan=jurusan_input if jurusan_input != "Lainnya" else "",
                    jurusan_lainnya=jurusan_lain if jurusan_input == "Lainnya" else "",
                    university_tier=tier_final,
                    ipk=safe_int(ipk_input.replace(',', '.')) if ipk_input else None,
                    tahun_lulus=tahun_lulus_input if tahun_lulus_input and tahun_lulus_input > 0 else None,
                    nomor_hp=hp_input,
                    email=email_input,
                    last_position=last_position_input,
                    last_company=last_company_input,
                    last_tenure=last_tenure_input,
                    total_tenure=total_tenure_input,
                    pernah_di_fmcg=fmcg_input,
                    sourcing_freelance=sourcing_freelance_input if sourcing_freelance_input else None,
                    tanggal_sourcing_freelance=tanggal_sourcing_freelance_input if sourcing_freelance_input else None,
                    sourcing_hr=sourcing_hr_input if sourcing_hr_input else None,
                    tanggal_sourcing=tanggal_sourcing_input if sourcing_hr_input else None,
                    sourcing_date=datetime.now().date(),
                    source_user_id=user.id,
                    created_at=datetime.now(),
                    last_compile_action="MANUAL_INPUT"
                )
                db.add(new)
                db.commit()
                st.success(f"✅ '{nama_input}' berhasil disimpan! Tier: {tier_final}")
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
    show_sourcing_form(
        db=db, user=user,
        pic_options=pic_options,
        fptk_options=fptk_options,
        sourcing_options=sourcing_options,
        pipeline_options=pipeline_options,
        initial_data=None,
        form_key="form_manual",
        is_parse_mode=False,
        batch_mode=False
    )
