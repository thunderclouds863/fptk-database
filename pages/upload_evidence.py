import streamlit as st
import pandas as pd
from core.database import get_db
from core.models import DBSourcing, FPTK, Evidence, User
from core.auth import get_current_user, is_admin
from datetime import datetime
import hashlib
import os
import base64

# ============================================================
# 🔥🔥🔥 CACHE FUNCTIONS (GANTI ke st.cache_resource) 🔥🔥🔥
# ============================================================

@st.cache_resource(ttl=3600)
def get_pic_options_evidence(_db):
    """Mengambil opsi PIC - cache 1 jam"""
    try:
        pic_list = ["Semua"] + [u[0] for u in _db.query(User.pic_recruiter).filter(User.role == "user").distinct().all() if u[0]]
        return pic_list
    except:
        return ["Semua"]


@st.cache_resource(ttl=300)
def get_sourcing_kode_unik(_db):
    """Mengambil daftar kode_unik dari sourcing - cache 5 menit"""
    try:
        data = _db.query(DBSourcing.kode_unik, DBSourcing.posisi).filter(
            DBSourcing.kode_unik.isnot(None)
        ).distinct().all()
        return data
    except:
        return []


def check_column_exists(table, column_name, db):
    """Cek apakah kolom ada di tabel"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        columns = [c['name'] for c in inspector.get_columns(table)]
        return column_name in columns
    except:
        return False


def show_upload_evidence():
    st.title("📎 Upload Evidence Sourcing")
    st.markdown("Upload bukti evidence sourcing dan lihat histori upload.")
    
    db = next(get_db())
    user = get_current_user(db)
    if not user:
        st.warning("Silakan login terlebih dahulu.")
        return
    
    admin = is_admin(db)
    
    # ============================================================
    # CEK APAKAH KOLOM file_data ADA
    # ============================================================
    has_file_data = check_column_exists('evidences', 'file_data', db)
    
    if not has_file_data:
        st.warning("⚠️ Kolom 'file_data' belum ada di database. File tidak akan disimpan di database.")
        st.info("💡 Jalankan SQL: ALTER TABLE evidences ADD COLUMN file_data TEXT;")
    
    # ============================================================
    # LOAD FROM CACHE
    # ============================================================
    with st.spinner("📋 Memuat data..."):
        sourcing_data = get_sourcing_kode_unik(db)
        pic_list = get_pic_options_evidence(db)
    
    if not sourcing_data:
        st.warning("Belum ada data sourcing dengan Kode Unik.")
        return
    
    # ============================================================
    # UPLOAD EVIDENCE
    # ============================================================
    st.subheader("📤 Upload Evidence Baru")
    
    posisi_options = {}
    for s in sourcing_data:
        if s.posisi:
            key = f"{s.posisi[:50]} | {s.kode_unik}"
            posisi_options[key] = s.kode_unik
    
    selected = st.selectbox("Pilih Posisi / Kode Unik", list(posisi_options.keys()))
    kode_unik = posisi_options[selected]
    posisi_text = selected.split(" | ")[0]
    
    tanggal = st.date_input("Tanggal Evidence", datetime.now())
    
    total_cv = db.query(DBSourcing).filter(
        DBSourcing.kode_unik == kode_unik,
        DBSourcing.sourcing_date == tanggal
    ).count()
    
    st.metric("📊 Jumlah CV", total_cv)
    
    uploaded_file = st.file_uploader(
        "Pilih file bukti evidence (PDF, Image, Excel)",
        type=["pdf", "jpg", "jpeg", "png", "xlsx", "xlsm"]
    )
    
    if uploaded_file:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")
        
        if st.button("💾 Upload Evidence", type="primary"):
            file_bytes = uploaded_file.getvalue()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            file_name = uploaded_file.name
            
            clean_posisi = posisi_text.replace(" ", "_").replace("/", "_")[:40]
            safe_name = f"{tanggal.strftime('%Y-%m-%d')}_{clean_posisi}_{total_cv}_CV.{file_name.split('.')[-1]}"
            
            try:
                file_data_b64 = None
                if has_file_data:
                    file_data_b64 = base64.b64encode(file_bytes).decode('utf-8')
                
                new_evidence = Evidence(
                    kode_unik=kode_unik,
                    posisi=posisi_text,
                    tanggal=tanggal,
                    file_name=safe_name,
                    file_path=f"evidence/{safe_name}",
                    file_size=len(file_bytes),
                    total_cv=total_cv,
                    pic_recruiter=user.pic_recruiter or user.username,
                    user_id=user.id,
                    created_at=datetime.now()
                )
                
                if has_file_data:
                    new_evidence.file_data = file_data_b64
                
                db.add(new_evidence)
                db.commit()
                
                st.success("✅ Evidence berhasil direkam!")
                st.info(f"📋 Nama file: {safe_name}")
                st.info(f"📋 Total CV: {total_cv}")
                
                if has_file_data:
                    st.info("📁 File disimpan di database")
                else:
                    st.warning("⚠️ File tidak disimpan di database (kolom file_data tidak ada)")
                
                st.download_button(
                    "📥 Download File",
                    file_bytes,
                    safe_name,
                    uploaded_file.type
                )
                
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                db.rollback()
    
    # ============================================================
    # HISTORI EVIDENCE
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Histori Evidence")
    
    col1, col2 = st.columns(2)
    with col1:
        pic_filter = st.selectbox("Filter PIC", ["Semua"] + pic_list)
    with col2:
        search_filter = st.text_input("Cari (Kode Unik / Posisi)", placeholder="Ketik keyword...")
    
    query = db.query(Evidence)
    if pic_filter != "Semua":
        query = query.filter(Evidence.pic_recruiter == pic_filter)
    if search_filter:
        query = query.filter(
            (Evidence.kode_unik.ilike(f"%{search_filter}%")) |
            (Evidence.posisi.ilike(f"%{search_filter}%"))
        )
    
    evidences = query.order_by(Evidence.created_at.desc()).limit(100).all()
    
    if evidences:
        data = []
        for e in evidences:
            data.append({
                "ID": e.id,
                "Kode Unik": e.kode_unik,
                "Posisi": e.posisi[:40] + "..." if len(e.posisi or "") > 40 else e.posisi,
                "Tanggal": e.tanggal.strftime("%d/%m/%Y") if e.tanggal else "-",
                "File": e.file_name,
                "CV": e.total_cv,
                "PIC": e.pic_recruiter,
                "Upload": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "-"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=300)
        
        if st.button("📥 Export CSV"):
            csv = df.to_csv(index=False)
            st.download_button("Download", csv, f"evidence_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        
        # ============================================================
        # DETAIL EVIDENCE
        # ============================================================
        st.markdown("---")
        st.subheader("🔍 Detail Evidence")
        
        selected_id = st.selectbox("Pilih ID untuk lihat detail", [e.id for e in evidences])
        if selected_id:
            detail = db.query(Evidence).filter(Evidence.id == selected_id).first()
            if detail:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Kode Unik:** {detail.kode_unik}")
                    st.markdown(f"**Posisi:** {detail.posisi}")
                with col2:
                    st.markdown(f"**Tanggal:** {detail.tanggal.strftime('%d/%m/%Y') if detail.tanggal else '-'}")
                    st.markdown(f"**Total CV:** {detail.total_cv}")
                with col3:
                    st.markdown(f"**File:** {detail.file_name}")
                    st.markdown(f"**PIC:** {detail.pic_recruiter}")
                
                st.markdown("---")
                st.markdown("### 📎 File Evidence")
                
                if has_file_data and hasattr(detail, 'file_data') and detail.file_data:
                    try:
                        image_data = base64.b64decode(detail.file_data)
                        st.image(image_data, caption=detail.file_name, use_container_width=True)
                        
                        st.download_button(
                            "📥 Download File",
                            image_data,
                            detail.file_name,
                            mime="application/octet-stream"
                        )
                    except Exception as e:
                        st.error(f"Error menampilkan gambar: {str(e)}")
                else:
                    st.info("💡 File tidak ditemukan di database")
                    
                    if detail.file_path and os.path.exists(detail.file_path):
                        with open(detail.file_path, "rb") as f:
                            file_data = f.read()
                        st.download_button(
                            "📥 Download File (dari path)",
                            file_data,
                            detail.file_name,
                            mime="application/octet-stream"
                        )
                
                if admin:
                    st.markdown("---")
                    if st.button("🗑️ Hapus Evidence", type="secondary"):
                        db.delete(detail)
                        db.commit()
                        st.success("Data berhasil dihapus!")
                        st.rerun()
    else:
        st.info("Belum ada evidence yang diupload.")


if __name__ == "__main__":
    show_upload_evidence()
