@echo off
REM Pornește aplicația Testify Hardware pe calculatorul de la birou.
cd /d "%~dp0"
if not exist .venv (
  echo Prima pornire: se instaleaza aplicatia...
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
