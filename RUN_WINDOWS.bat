@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py seed_demo
if errorlevel 1 goto failed
echo.
echo MediTrust will open at http://127.0.0.1:8000
echo Keep this window open. Press Ctrl+C to stop the server.
echo For phones, see the SAME-WI-FI setup in README.md.
echo.
".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
goto end
:failed
echo.
echo Setup stopped. Read the error above. Python 3.12 or newer is required.
pause
:end
endlocal
