@echo off
rem -----------------------------------------------------------------
rem Sentinel-Outputs – one-click launch for Windows cmd
rem -----------------------------------------------------------------

rem Change to the project directory (adjust if you moved the folder)
cd /d "C:\Users\SV Gokul\.gemini\scratch\sentinel_outputs"

rem ---------------------------------------------------------------
rem Helper: kill any existing FastAPI process on port 8000
rem ---------------------------------------------------------------
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing previous FastAPI process PID %%a
    taskkill /PID %%a /F >nul 2>&1
)

rem ---- 1️⃣ Start FastAPI (uvicorn) ---------------------------------
rem The leading "start" opens a new console window.
rem The empty title ("") prevents the window from being named "cmd".
start "" ".venv\Scripts\uvicorn.exe" app:app --host 127.0.0.1 --port 8000

rem ---- 2️⃣ Start the MQTT worker -----------------------------------
start "" ".venv\Scripts\python.exe" mqtt_worker.py

rem ---- 3️⃣ Simple Python MQTT listener -----------------
rem This listener prints sign/status messages using the real config.
start "" ".venv\Scripts\python.exe" listen_outputs.py

rem ---- 4️⃣ All done -------------------------------------------------
echo.
echo --------------------------------------------------------------
echo All three services have been launched in separate windows.
echo   • FastAPI   : http://127.0.0.1:8000
echo   • MQTT worker is listening on the broker defined in .env
echo   • Python listener shows the sign & status MQTT messages
echo.
echo To publish a test incident run (in a new cmd window):
echo   cd "C:\Users\SV Gokul\.gemini\scratch\sentinel_outputs"
echo   ".venv\Scripts\python.exe" publish_test_event.py   (or add --clear)
echo --------------------------------------------------------------
pause
