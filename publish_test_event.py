import os
import json
import argparse
import datetime
from pathlib import Path
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Load env for broker config
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"
MQTT_INCIDENT_TOPIC = os.getenv("MQTT_INCIDENT_TOPIC", "sentinel/incidents/confirmed")

# Load env for broker config
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"
MQTT_INCIDENT_TOPIC = os.getenv("MQTT_INCIDENT_TOPIC", "sentinel/incidents/confirmed")

def build_event(event_type: str, incident_id: str, status: str, location: str) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "event": event_type,
        "incident_id": incident_id,
        "status": status,
        "location": location,
        "latitude": 13.0827,
        "longitude": 80.2707,
        "severity": "HIGH",
        "timestamp": now,
    }

def publish(event: dict):
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    payload = json.dumps(event)
    client.publish(MQTT_INCIDENT_TOPIC, payload, qos=1)
    client.disconnect()
    print(f"[PUBLISH TEST] Sent event to {MQTT_INCIDENT_TOPIC}: {event['event']}")

def main():
    parser = argparse.ArgumentParser(description="Publish a demo incident event to Sentinel MQTT.")
    parser.add_argument("--clear", action="store_true", help="After publishing CONFIRMED, also publish a CLEARED event for the same incident ID.")
    parser.add_argument("--incident-id", default="SENTINEL-DEMO-001", help="Incident ID to use (default SENTINEL-DEMO-001)")
    args = parser.parse_args()

    incident_id = args.incident_id
    location = "Demo Junction"
    confirmed = build_event(
        event_type="INCIDENT_CONFIRMED",
        incident_id=incident_id,
        status="CONFIRMED",
        location=location,
    )
    publish(confirmed)
    if args.clear:
        cleared = build_event(
            event_type="INCIDENT_CLEARED",
            incident_id=incident_id,
            status="CLEARED",
            location=location,
        )
        publish(cleared)

    parser = argparse.ArgumentParser(description="Publish a demo incident event to Sentinel MQTT.")
    parser.add_argument("--clear", action="store_true", help="After publishing CONFIRMED, also publish a CLEARED event for the same incident ID.")
    args = parser.parse_args()

    incident_id = "SENTINEL-DEMO-001"
    location = "Demo Junction"
    confirmed = build_event(
        event_type="INCIDENT_CONFIRMED",
        incident_id=incident_id,
        status="CONFIRMED",
        location=location,
    )
    publish(confirmed)
    if args.clear:
        cleared = build_event(
            event_type="INCIDENT_CLEARED",
            incident_id=incident_id,
            status="CLEARED",
            location=location,
        )
        publish(cleared)

if __name__ == "__main__":
    main()
