# core/demo.py
"""DEMO_MODE support for the public portfolio demo.

Set DEMO_MODE=1 (env var or Streamlit secret). The app then uses a local SQLite
database when DATABASE_URL is not set, generic demo accounts, local file storage
instead of Cloudflare R2, and auto-seeded dummy data. Nothing changes when unset.
"""
import os
import random
from datetime import date, timedelta


def is_demo() -> bool:
    val = os.getenv("DEMO_MODE")
    if val is None:
        try:
            import streamlit as st
            val = str(st.secrets.get("DEMO_MODE", "0"))
        except Exception:
            val = "0"
    return str(val).lower() in ("1", "true", "yes")


DEMO_USERS = [
    # username, display_name, pic_name, business_unit, kode_pic
    ("recruiter1", "Recruiter Satu", "Recruiter1", "CORP", "CORPRec1"),
    ("recruiter2", "Recruiter Dua", "Recruiter2", "MP", "MPRec2"),
]
DEMO_PASSWORD = "demo123"

_POSITIONS = [
    ("Brand Manager", "Commercial", "Marketing", "Brand", 4),
    ("Area Sales Manager - Jawa Barat", "Sales", "Sales Operation", "Sales", 4),
    ("Supervisor Produksi", "Operation", "Manufacturing", "Production", 3),
    ("QA Staff", "Operation", "Quality", "QA", 2),
    ("Data Analyst", "Corporate", "IT & Digital", "Data", 3),
    ("HR Business Partner", "Corporate", "Human Capital", "HRBP", 3),
    ("Sales Taking Order - Bekasi", "Sales", "Sales Operation", "Sales", 2),
    ("Warehouse Supervisor", "Operation", "Supply Chain", "Warehouse", 3),
    ("Finance Staff", "Corporate", "Finance", "Accounting", 2),
    ("Continuous Improvement Specialist", "Operation", "Manufacturing", "CI", 3),
    ("Digital Marketing Specialist", "Commercial", "Marketing", "Digital", 3),
    ("Maintenance Technician", "Operation", "Engineering", "Maintenance", 2),
]
_STAGES = ["sourcing_hr", "shortlist_cv", "psikotes", "hr_interview", "user_interview", "offering"]


def seed_demo_data(db):
    from core.models import FPTK, DBSourcing, UploadCycle, User
    from core.utils import calculate_sla_days, calculate_deadline_sla, calculate_detail_sla
    from core.upload_cycle import create_upload_cycle

    if not db.query(UploadCycle.id).first():
        admin = db.query(User).filter(User.username == "demo_admin").first()
        create_upload_cycle(db, "Demo Cycle", admin.id if admin else None)
    if db.query(FPTK.id).first():
        return
    rnd = random.Random(42)
    today = date.today()
    for i, (pos, direk, div, dept, lvl) in enumerate(_POSITIONS, start=1):
        user = DEMO_USERS[i % 2]
        fdate = today - timedelta(days=rnd.randint(10, 120))
        status = rnd.choice(["OP", "OP", "Closed", "Cancel"]) if i > 2 else "OP"
        sla = calculate_sla_days(lvl)
        deadline = calculate_deadline_sla(fdate, sla)
        offering = fdate + timedelta(days=rnd.randint(14, 50)) if status == "Closed" else None
        kode = f"DEMO{i:03d}"
        db.add(FPTK(
            kode_unik=kode, posisi=pos, kode_pic=user[4], fptk_date_real=fdate, fptk_date_kode=fdate,
            business_unit=user[3], direktorat=direk, divisi=div, department=dept,
            level_fptk=f"{lvl}A", level_number=lvl, alasan_permintaan_fptk="Penambahan headcount",
            category_fptk="New Position", pic_recruiter=user[2],
            filter_kategorisasi_fptk="Staff" if lvl <= 2 else "Middle", vacancy=1, status=status,
            month_fptk_date=fdate.strftime("%B"), offering_date=offering, jumlah_sla=sla,
            deadline_sla=deadline, detail_sla=calculate_detail_sla(status, deadline, offering),
            lokasi_kerja=rnd.choice(["Jakarta", "Bogor", "Bandung", "Surabaya"]), kode_bu=user[3],
            fptk_availability="V",
        ))
        for j in range(1, rnd.randint(3, 6)):
            reached = rnd.randint(1, len(_STAGES))
            vals = {}
            for k, st_name in enumerate(_STAGES[:reached]):
                vals[st_name] = "V" if k < reached - 1 else rnd.choice(["V", "X"])
                vals[f"tanggal_{st_name}" if st_name != "sourcing_hr" else "tanggal_sourcing"] = fdate + timedelta(days=3 * (k + 1))
            db.add(DBSourcing(
                sourcing_date=fdate + timedelta(days=2), kode_unik=kode, posisi=pos,
                rekruter=user[2], sumber_sourcing=rnd.choice(["LinkedIn", "JobStreet", "Referral", "Glints"]),
                nama=f"Kandidat Demo {i}-{j}", jenjang_pendidikan=rnd.choice(["S1", "D3", "S2"]),
                jurusan=rnd.choice(["Teknik Industri", "Manajemen", "Statistika", "Teknik Kimia"]),
                tahun_lulus=rnd.randint(2015, 2024), ipk=round(rnd.uniform(2.9, 3.9), 2),
                email=f"kandidat{i}{j}@example.com", nomor_hp="0800000000",
                domisili=rnd.choice(["Jakarta", "Bogor", "Bandung"]), **vals,
            ))
    db.commit()
