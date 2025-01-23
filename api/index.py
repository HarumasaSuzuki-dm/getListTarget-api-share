from fastapi import FastAPI
import os
import subprocess

app = FastAPI()

@app.get("/")
def root():
    # Streamlitアプリをバックグラウンドで起動
    subprocess.Popen(["streamlit", "run", "streamlit_app_send.py", "--server.port=8501", "--server.address=0.0.0.0"])
    return {"message": "Streamlit app is running"}
