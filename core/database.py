# core/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback untuk Streamlit Cloud (baca dari st.secrets)
if not DATABASE_URL:
    try:
        import streamlit as st
        DATABASE_URL = st.secrets["connections"]["postgresql"]["url"]
    except Exception:
        raise ValueError(
            "DATABASE_URL tidak ditemukan. "
            "Set di .env (lokal) atau st.secrets (Streamlit Cloud)."
        )

# Konversi postgres:// ke postgresql:// (SQLAlchemy butuh ini)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Pastikan sslmode=require (Neon butuh SSL)
if "sslmode" not in DATABASE_URL:
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL += f"{separator}sslmode=require"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Buat semua tabel jika belum ada (dipanggil saat startup)."""
    from core import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """Generator session untuk Streamlit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()