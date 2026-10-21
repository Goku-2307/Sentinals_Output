import os
from dotenv import load_dotenv
load_dotenv()
import secrets
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Optional, List, Dict, Any

from models import IncidentEvent
from publish_output import publish_output
import sms as sms_mod
from report_utils import (
    update_report,
    load_report,
    list_reports,
    check_duplicate,
    mark_processed,
    unmark_processed,
)

app = FastAPI(title="Sentinel Outputs Service")

# Environment configuration
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

# Startup guard: abort if demo mode is off and a public broker is used
def _startup_guard():
    public_brokers = {"test.mosquitto.org", "broker.hivemq.com", "broker.emqx.io"}
    if not DEMO_MODE and MQTT_HOST in public_brokers:
        print(f"[ERROR] PUBLIC BROKER DETECTED ({MQTT_HOST}) while DEMO_MODE=false. Exiting.")
        import sys; sys.exit(1)
_startup_guard()
ENABLE_SMS = os.getenv("ENABLE_SMS", "false").lower() == "true"
MQTT_SIGN_TOPIC = os.getenv("MQTT_SIGN_TOPIC", "sentinel/outputs/sign")
MQTT_STATUS_TOPIC = os.getenv("MQTT_STATUS_TOPIC", "sentinel/outputs/status")
# INTERNAL_API_KEY is read per-request to avoid stale env values

def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    # INTERNAL_API_KEY is read at request time so tests can modify the env between runs
    internal_key = os.getenv("INTERNAL_API_KEY")
    if internal_key:
        if not x_api_key or not secrets.compare_digest(x_api_key, internal_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@app.get("/health")
def health():
    return {
        "service": "sentinel_outputs",
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "sms_enabled": ENABLE_SMS,
    }

@app.post("/internal/events")
async def internal_event(event: IncidentEvent, request: Request, _: bool = Depends(verify_api_key)):
    # Normalise fields (already done by validator)
    incident_id = event.incident_id
    event_type = event.event
    status = event.status

    # Validate allowed combinations
    if not ((event_type == "INCIDENT_CONFIRMED" and status == "CONFIRMED") or
            (event_type == "INCIDENT_CLEARED" and status == "CLEARED")):
        raise HTTPException(status_code=400, detail="Invalid event/status combination")

    # Idempotency check
    is_dup, prev = check_duplicate(incident_id, event_type)
    if is_dup:
        return JSONResponse(content={
            "status": "duplicate_ignored",
            "previous_result": prev,
        })

    # Process event – keep a placeholder dict for eventual result
    result: Dict[str, Any] = {
        "incident_id": incident_id,
        "event": event_type,
        "outputs": {},
    }

    # Mark as processing to prevent race conditions
    try:
        mark_processed(incident_id, event_type, result)

        # Prepare common fields for report
        base_report = event.model_dump()
        base_report["received_at"] = datetime.now(timezone.utc).isoformat()

        if event_type == "INCIDENT_CONFIRMED":
            # Build sign payload
            sign_payload = {
                "incident_id": incident_id,
                "command": "DISPLAY_ACCIDENT_WARNING",
                "message": f"ACCIDENT AHEAD - {event.location}"[:120],
                "severity": event.severity,
                "latitude": event.latitude,
                "longitude": event.longitude,
            }
            sign_res = publish_output(MQTT_SIGN_TOPIC, sign_payload)
            sms_res = sms_mod.send_sms(incident_id, event.location)
            result["outputs"]["sign"] = sign_res
            result["outputs"]["sms"] = sms_res
        else:  # INCIDENT_CLEARED
            sign_payload = {
                "incident_id": incident_id,
                "command": "CLEAR_WARNING",
            }
            sign_res = publish_output(MQTT_SIGN_TOPIC, sign_payload)
            result["outputs"]["sign"] = sign_res
            result["outputs"]["sms"] = {"status": "not_sent_for_clear"}

        # Publish status message and capture its result
        status_res = publish_output(MQTT_STATUS_TOPIC, {
            "incident_id": incident_id,
            "event": event_type,
            "outputs": result["outputs"],
        })
        # Add status_publish to outputs dict
        result["outputs"]["status_publish"] = status_res

        # Write the final report *once* with all outputs (including status_publish)
        report_path = update_report(base_report, result["outputs"])
        result["report_file"] = report_path

        # Store processed result
        mark_processed(incident_id, event_type, result)
        return result


    except Exception as exc:
        # Cleanup for retryability
        unmark_processed(incident_id, event_type)
        print(f"[ERROR] {exc}")
    raise HTTPException(status_code=500, detail="Internal processing error")

@app.get("/reports")
def get_reports():
    reports = list_reports()
    return {"count": len(reports), "reports": reports}


@app.get("/reports/{incident_id}")
def get_report(incident_id: str):
    data = load_report(incident_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")
    return data
