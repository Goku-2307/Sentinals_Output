import os
import re
import json
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv
# Helper to mask a phone number, showing only the last 4 digits
def _mask_number(num: str) -> str:
    # Preserve length, mask all but last 4 characters
    return "*" * (len(num) - 4) + num[-4:]

# Regular expression for Indian mobile numbers (e.g., 919876543210)
RECIPIENT_REGEX = re.compile(r"^91\d{10}$")


def send_sms(incident_id: str, location: str) -> Dict[str, Any]:
    """Send an SMS via MSG91 Flow API.

    The function follows the strict order of checks required by the
    specification:
    1. If SMS is disabled (`ENABLE_SMS=false`) → return ``{"status": "disabled"}``.
    2. If demo mode is active (`DEMO_MODE=true`) → return ``{"status": "simulated"}``.
    3. Validate that all required MSG91 environment variables are present.
    4. Validate each recipient number against the Indian format.
    5. Send a POST request per recipient and collect per‑recipient results.
    6. Return a unified result payload.

    Environment variables are read inside the function so tests can monkey‑patch
    them without needing to reload the module.
    """
    # Load .env at call time – enables tests to change env values dynamically
    load_dotenv()

    # Read configuration flags
    demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
    enable_sms = os.getenv("ENABLE_SMS", "false").lower() == "true"

    # 1. SMS disabled
    if not enable_sms:
        return {"status": "disabled"}

    # 2. Demo mode – no real request is sent
    if demo_mode:
        return {"status": "simulated"}

    # 3. Required MSG91 configuration
    authkey = os.getenv("MSG91_AUTHKEY", "")
    template_id = os.getenv("MSG91_TEMPLATE_ID", "")
    recipients_raw = os.getenv("SMS_RECIPIENTS", "")
    if not (authkey and template_id and recipients_raw):
        return {
            "status": "failed",
            "error": "Configure MSG91_AUTHKEY, MSG91_TEMPLATE_ID and SMS_RECIPIENTS",
        }

    # Prepare results list
    results: List[Dict[str, Any]] = []
    url = "https://control.msg91.com/api/v5/flow"
    base_headers = {
        "accept": "application/json",
        "authkey": authkey,
        "content-type": "application/json",
    }

    # 4. Process each recipient entry
    for raw in recipients_raw.split(","):
        num = raw.strip()
        if not RECIPIENT_REGEX.fullmatch(num):
            results.append(
                {
                    "recipient_last4": _mask_number(num),
                    "status": "failed",
                    "error": "Expected Indian number format 91XXXXXXXXXX",
                }
            )
            continue

        payload = {
            "template_id": template_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": num,
                    "VAR1": incident_id[:40],
                    "VAR2": location[:40],
                }
            ],
        }
        try:
            resp = requests.post(url, headers=base_headers, json=payload, timeout=15)
            provider_response = resp.text[:300]
            status = "accepted_by_provider" if resp.ok else "failed"
            results.append(
                {
                    "recipient_last4": _mask_number(num),
                    "status": status,
                    "http_status": resp.status_code,
                    "provider_response": provider_response,
                }
            )
        except requests.RequestException as e:
            results.append(
                {
                    "recipient_last4": _mask_number(num),
                    "status": "failed",
                    "error": str(e)[:300],
                }
            )

    return {"status": "completed", "results": results}

# NOTE: Provider acceptance (HTTP 200) does NOT guarantee delivery to the handset.
