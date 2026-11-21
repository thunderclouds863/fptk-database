# Entry point untuk demo portfolio publik di Streamlit Cloud.
# Terpisah dari app production: menyalakan DEMO_MODE lalu menjalankan app.py.
import os
import runpy

os.environ["DEMO_MODE"] = "1"
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"), run_name="__main__")
