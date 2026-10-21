# Deployment Checklist – Making Sentinel‑Outputs Live on a Web Portal

This document lists the concrete tasks you need to perform to move the **Sentinel‑Outputs** service from a local development setup to a production‑ready web portal (e.g., a public URL, cloud hosting, or an internal intranet).  Follow the steps in order; each step includes a short description and the command (or UI action) you should run.

---

## 1️⃣ Prepare the Codebase
1. **Commit the current state**
   ```bash
   cd "C:\Users\SV Gokul\.gemini\scratch\sentinel_outputs"
   git init   # if not already a repo
   git add .
   git commit -m "Ready for production"
   ```
2. **Create a `requirements.txt`** (if missing) so the cloud build can reinstall dependencies:
   ```bash
   .venv\Scripts\pip freeze > requirements.txt
   ```
3. **Ensure a clean `.env.example`** – contains placeholder values only.  Do **not** commit real secrets.

---

## 2️⃣ Choose a Hosting Platform
| Platform | Typical steps | When to use |
|----------|---------------|------------|
| **Google Cloud Run** (fully managed) | - Enable Cloud Run & Container Registry. <br> - Build a Docker image (see Dockerfile below). <br> - Deploy to Cloud Run with `--allow‑unauthenticated`. | Public internet‑facing service, auto‑scaling, no VM management. |
| **Compute Engine VM** (Ubuntu/Windows) | - Spin up a VM. <br> - Install Docker or Python env. <br> - Run the service (systemd or `screen`). | Need custom OS config or persistent storage. |
| **App Engine (Standard)** | - Add `app.yaml`. <br> - Deploy with `gcloud app deploy`. | Simple Python web app with automatic scaling. |
| **Azure App Service / AWS Elastic Beanstalk** | Similar steps: container‑ize or use a `requirements.txt`+`Procfile`. | Multi‑cloud preference. |

*Pick one – the checklist continues assuming **Google Cloud Run** (the most straightforward for a FastAPI service).*

---

## 3️⃣ Containerise the Application (Docker)
Create a **Dockerfile** in the project root:
```dockerfile
# Use the official lightweight Python image
FROM python:3.12-slim

# Install OS‑level deps (required for paho‑mqtt & uvicorn)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

# Create a non‑root user
RUN useradd -m appuser
WORKDIR /app

# Copy only the needed files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Switch to non‑root user
USER appuser

# Expose the FastAPI port (default 8000)
EXPOSE 8000

# Command to run – we start the three processes via a small shell script
CMD ["/bin/sh", "-c", "\
    uvicorn app:app --host 0.0.0.0 --port 8000 &\
    python mqtt_worker.py &\
    python listen.py\
"]
```

Build and push the image (replace `<PROJECT_ID>` and `<REGION>`):
```bash
gcloud builds submit --tag gcr.io/<PROJECT_ID>/sentinel-outputs
```

---

## 4️⃣ Deploy to Cloud Run
```bash
# Deploy, exposing the service publicly
gcloud run deploy sentinel-outputs \
    --image gcr.io/<PROJECT_ID>/sentinel-outputs \
    --platform managed \
    --region <REGION> \
    --allow-unauthenticated \
    --port 8000
```
*Take note of the generated URL (e.g., `https://sentinel-outputs-xxxx.a.run.app`).*

---

## 5️⃣ Configure Environment Variables in Cloud Run
1. Open the Cloud Run console → **Edit & Deploy New Revision**.
2. Under **Variables & Secrets**, add the following **key/value** pairs (use **Secret Manager** for any real credentials):
   - `DEMO_MODE` = `false`
   - `ENABLE_SMS` = `true` *(or `false` if you only want demo mode)*
   - `MQTT_HOST` = `test.mosquitto.org`
   - `MQTT_PORT` = `1883`
   - `MSG91_AUTHKEY` = **Secret** (`msg91-authkey`)
   - `MSG91_TEMPLATE_ID` = **Secret** (`msg91-template-id`)
   - `SMS_RECIPIENTS` = `+919876543210,+919812345678`
   - Any other custom config (e.g., `CORS_ORIGIN`, `API_KEY`).
3. Save & **Deploy**.

---

## 6️⃣ Secure MQTT Communication (Production‑grade)
1. **Prefer a private MQTT broker** (e.g., Cloud IoT Core, Mosquitto on a VM, or a managed MQTT service). Update `MQTT_HOST`/`MQTT_PORT` accordingly.
2. Enable **TLS** on the broker and set `MQTT_TLS=true` in `.env` (code already supports TLS via `paho‑mqtt`).
3. If using a public broker, consider adding **username/password** auth and set `MQTT_USER` / `MQTT_PASS` in the env.

---

## 7️⃣ Enable Real SMS (optional but required for production)
1. **Create a MSG91 account** and obtain:
   - **Auth Key**
   - **Flow Template ID** for the SMS you want to send.
2. Store these securely in **Secret Manager** (as shown in step 5).
3. Set `ENABLE_SMS=true` in the Cloud Run env variables.
4. Verify the phone numbers are in **E.164** format (`+91xxxxxxxxxx`).
5. Deploy a new revision to apply the changes.
6. Test by publishing a CONFIRMED incident; you should receive an SMS.

---

## 8️⃣ Observability & Logging
- **Cloud Logging**: Cloud Run automatically streams stdout/stderr. Ensure your logs contain `INFO` statements from FastAPI, MQTT worker, and SMS module.
- **Health endpoint**: `GET /health` returns `{"status":"ok"}` – configure a **Google Cloud Monitoring** uptime check against this URL.
- **Metrics** (optional): expose Prometheus metrics via `fastapi-prometheus` and scrape with Cloud Monitoring.

---

## 9️⃣ Test the Live Deployment
```bash
# 1️⃣ Verify FastAPI is reachable
curl https://<YOUR_CLOUD_RUN_URL>/health

# 2️⃣ Publish a test incident (replace URL with your Cloud Run endpoint)
python publish_test_event.py   # this script contacts the public MQTT broker, which forwards to your Cloud Run service

# 3️⃣ In the Cloud Run Logs view, you should see:
#    - Incoming POST /internal/events
#    - MQTT publish calls (sign & status)
#    - SMS request/response (if enabled)
```
If everything appears, the service is live.

---

## 🔟 Optional – Front‑end / Web Portal Integration
- **Add a simple HTML page** (or embed in your existing portal) that calls the FastAPI `GET /reports/{incident_id}` endpoint to fetch the generated JSON report.
- Use **CORS**: set `CORS_ORIGIN` in `.env` to the portal’s domain (or `*` for testing). The FastAPI app already respects this variable.
- Host the static page on any web server (Firebase Hosting, Cloud Storage static site, etc.) and point it to the FastAPI URL.

---

## 📋 Summary of Tasks
| Phase | Action | Command / UI | Done? |
|------|--------|--------------|------|
| **Code** | Commit, generate `requirements.txt`, add `.env.example` | `git add . && git commit` | ☐ |
| **Container** | Write Dockerfile, build & push image | `gcloud builds submit …` | ☐ |
| **Deploy** | Deploy to Cloud Run, set env vars / secrets | Cloud Console / `gcloud run deploy` | ☐ |
| **MQTT** | Switch to private broker, enable TLS & auth | Broker config | ☐ |
| **SMS** | Set MSG91 secrets, enable flag, test | Secret Manager + env var | ☐ |
| **Observability** | Verify logs, health check, optional metrics | Cloud Logging / Monitoring | ☐ |
| **Portal** | Add front‑end page, configure CORS | HTML/JS + env var | ☐ |

Once all rows are checked, the Sentinel‑Outputs service is fully live, handling inbound incidents, publishing sign/status MQTT messages, and (optionally) sending real SMS notifications.
