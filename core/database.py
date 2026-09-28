# core/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback ke hardcoded jika env tidak ada (untuk Streamlit Cloud)
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres.papyidtpfvgbkucowtjw:OpetSmoky6891_@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()