import bcrypt
import streamlit as st
from sqlalchemy.orm import Session
from core.models import User, AuditLog
import datetime
import hashlib
import re

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

def create_user(db: Session, username: str, password: str, role: str = "user", pic_recruiter: str = None, display_name: str = None):
    if db.query(User).filter(User.username == username).first():
        return None
    if len(password) < 6:
        return None
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        pic_recruiter=pic_recruiter,
        display_name=display_name or username
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
    """Create 17 PIC users + 1 Admin if not exist"""
    pic_users = [
        ("CMD", "CMD"),
        ("Brittney", "Brittney"),
        ("Eli", "Eli"),
        ("Fiqra", "Fiqra"),
        ("Karin", "Karin"),
        ("Kenthansen", "Kenthansen"),
        ("Kevin", "Kevin"),
        ("Marta", "Marta"),
        ("Omega", "Omega"),
        ("Pauline", "Pauline"),
        ("Salsa", "Salsa"),
        ("Valendra", "Valendra"),
        ("Victor", "Victor"),
        ("Zwei", "Zwei"),
        ("JESS", "JESS"),
        ("MP", "MP"),
        ("MS", "MS"),
    ]
    
    for username, pic_name in pic_users:
        if not db.query(User).filter(User.username == username).first():
            create_user(db, username, "password123", "user", pic_name)
    
    if not db.query(User).filter(User.username == "admin").first():
        create_user(db, "admin", "admin123", "admin", None, "Administrator")

def get_current_user(db: Session):
    """Ambil user yang sedang login dari session state"""
    if "user_id" not in st.session_state:
        return None
    return db.query(User).filter(User.id == st.session_state.user_id).first()

def is_admin(db: Session):
    """Cek apakah user yang login adalah admin"""
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