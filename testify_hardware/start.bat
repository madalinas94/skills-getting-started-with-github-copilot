@echo off
REM Porneste aplicatia Testify Hardware (dublu-click pe acest fisier).
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python nu este instalat. Descarcati-l de pe https://www.python.org/downloads/
  echo La instalare bifati "Add python.exe to PATH", apoi porniti din nou acest fisier.
  echo.
  pause
  exit /b 1
)
if not exist .venv (
  echo Prima pornire: se instaleaza aplicatia, dureaza un minut...
  python -m venv .venv
  .venv\Scripts\python -m pip install --quiet -r requirements.txt
)
echo Aplicatia porneste. Se deschide in browser la http://localhost:8000
echo Pentru oprire, inchideti aceasta fereastra.
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8000"
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
