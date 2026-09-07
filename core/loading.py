import streamlit as st
import time

def show_loading(message="Memuat data...", duration=0.3):
    """Tampilkan loading indicator dengan spinner"""
    with st.spinner(message):
        time.sleep(duration)
    return True

@st.dialog("⏳ Loading...", width="small")
def loading_dialog(message="Memproses..."):
    st.markdown(f"### {message}")
    st.progress(0, text="Mohon tunggu...")
    for i in range(100):
        time.sleep(0.02)
        st.progress(i+1, text=f"Loading... {i+1}%")
    st.success("✅ Selesai!")
