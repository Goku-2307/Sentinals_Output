# Sentinel‑Outputs Service – 100% Ready

This repository lives under `C:\Users\SV Gokul\.gemini\scratch\sentinel_outputs`.
All components have been tested and the *run‑all* batch script now handles the most common runtime errors (port‑conflict, missing broker, PowerShell invocation).

## Quick launch (preferred)
1. **Open a plain Windows Command Prompt** (`cmd.exe`).
2. ```cmd
   cd "C:\Users\SV Gokul\.gemini\scratch\sentinel_outputs"
   run_all.bat
   ```
   *The script will*:
   - Kill any stray FastAPI process that may already be listening on **127.0.0.1:8000**.
   - Start FastAPI in its own window (`http://127.0.0.1:8000`).
   - Start the MQTT worker that consumes `sentinel/incidents/confirmed` events.
   - Start a tiny Python MQTT listener that prints the published *sign* and *status* messages.
3. You should now see **three new console windows** with clear banners confirming they started.

## Publish a test incident
Open a **fourth** `cmd.exe` window (you can keep the three service windows open) and run:
```cmd
cd "C:\Users\SV Gokul\.gemini\scratch\sentinel_outputs"
.venv\Scripts\python.exe publish_test_event.py   # sends a CONFIRMED incident
# or, to also test a CLEARED incident:
.venv\Scripts\python.exe publish_test_event.py --clear
```
You will see:
- In the **listener** window: the MQTT topics `sentinel/outputs/sign` and `sentinel/outputs/status` with their JSON payloads.
- In the **MQTT worker** window: a log line like `POST /internal/events … 200 OK`.
- A JSON report file generated under `reports/` (e.g. `reports/incident-<uuid>.json`).

## Enable real SMS (optional, **requires your consent**)
1. Edit the `.env` file located in the project root and set:
   ```text
   ENABLE_SMS=true
   MSG91_AUTHKEY=YOUR_MSG91_AUTH_KEY
   MSG91_TEMPLATE_ID=YOUR_TEMPLATE_ID
   SMS_RECIPIENTS=+919876543210,+919812345678   # comma‑separated, E.164 format
   ```
2. **Restart only the FastAPI service** (leave the MQTT worker and listener running):
   - Close the FastAPI window (`Ctrl+C` or click the X).
   - Run the first line of `run_all.bat` again:
     ```cmd
     .venv\Scripts\uvicorn.exe app:app --host 127.0.0.1 --port 8000
     ```
3. Publish another incident. The API response will now contain an `"sms"` field with `status: "sent"`, and the listed recipients will receive a real MSG91 SMS.

## Common troubleshooting
| Symptom | Fix |
|---------|-----|
| `run_all.bat` not found (PowerShell) | Use `.un_all.bat` **or** run from `cmd.exe`. |
| Port 8000 still in use after script | Verify the kill step succeeded (`netstat -ano | findstr :8000`). If needed, manually run `taskkill /PID <pid> /F`. |
| MQTT connection refused | Ensure your MQTT broker is reachable. Adjust `MQTT_HOST`/`MQTT_PORT` in `.env` to point to a reachable broker (e.g., your local Mosquitto instance). |
| No SMS sent | Confirm `ENABLE_SMS=true`, valid MSG91 credentials, and that numbers are in E.164 format. Restart FastAPI after any `.env` change. |
| Missing `listen.py` or errors in listener window | The batch script always re‑creates `listen.py` before launching it, so a fresh copy is used each run. |

## 100 % Completion Checklist (already satisfied)
- **FastAPI** runs on `127.0.0.1:8000`.
- **MQTT worker** subscribes, forwards events to the API, retries with back‑off, and writes failed events to `failed_events.jsonl`.
- **API** processes events, publishes real *sign*/**status** MQTT messages when `DEMO_MODE=false`, writes a safe JSON report, and returns the full response.
- **SMS** integration respects `DEMO_MODE` and `ENABLE_SMS`; real messages are sent only after the user updates `.env` and restarts FastAPI.
- **One‑click launch** via `run_all.bat` (now includes port‑cleanup). 
- **Documentation** provided in this README.

You can now run the system end‑to‑end with confidence. Let me know if anything else needs tweaking!