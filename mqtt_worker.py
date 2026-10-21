import os
from dotenv import load_dotenv
load_dotenv()
import json
import time
import signal
import sys
from pathlib import Path
from typing import Any, Dict
import requests
# Attempt to import paho.mqtt, provide fallback if missing for test environment
try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    class _DummyCallbackAPIVersion:
        VERSION2 = None
    class _DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        def username_pw_set(self, *args, **kwargs):
            pass
        def tls_set(self, *args, **kwargs):
            pass
        def on_connect(self, *args, **kwargs):
            pass
        def on_message(self, *args, **kwargs):
            pass
        def reconnect_delay_set(self, *args, **kwargs):
            pass
        def connect(self, *args, **kwargs):
            pass
        def loop_forever(self, *args, **kwargs):
            pass
        def disconnect(self, *args, **kwargs):
            pass
    class _DummyMQTT:
        CONNACK_ACCEPTED = 0
        CallbackAPIVersion = _DummyCallbackAPIVersion
        Client = _DummyClient
    mqtt = _DummyMQTT

load_dotenv()

# Environment configuration
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"
MQTT_INCIDENT_TOPIC = os.getenv("MQTT_INCIDENT_TOPIC", "sentinel/incidents/confirmed")
OUTPUTS_API_URL = os.getenv("OUTPUTS_API_URL", "http://127.0.0.1:8000")

FAILED_EVENTS_PATH = Path(__file__).parent / "failed_events.jsonl"
FAILED_EVENTS_PATH.touch(exist_ok=True)

client: mqtt.Client | None = None

def publish_failed(event: Dict[str, Any]):
    """Append a failed event JSON line for later manual replay."""
    with FAILED_EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"[MQTT WORKER] Event persisted to {FAILED_EVENTS_PATH}")

def post_event(event: Dict[str, Any]) -> bool:
    """POST the incident to the FastAPI internal endpoint.
    Returns True on success (2xx), False otherwise.
    """
    url = f"{OUTPUTS_API_URL.rstrip('/')}/internal/events"
    try:
        headers = {}
        api_key = os.getenv("INTERNAL_API_KEY")
        if api_key:
            headers["X-API-Key"] = api_key
        resp = requests.post(url, json=event, headers=headers, timeout=10)
        if resp.status_code == 200:
            print(f"[MQTT WORKER] Event posted successfully – status 200")
            return True
        else:
            # Log first 300 chars of response text
            snippet = resp.text[:300].replace("\n", " ")
            print(f"[MQTT WORKER] API rejected ({resp.status_code}): {snippet}")
            return False
    except requests.RequestException as e:
        print(f"[MQTT WORKER] API unavailable: {str(e)[:300]}")
        return False

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != mqtt.CONNACK_ACCEPTED:
        print(f"[MQTT WORKER] Connection failed, reason_code={reason_code}")
        return
    print(f"[MQTT WORKER] Connected to {MQTT_HOST}:{MQTT_PORT}, subscribing to {MQTT_INCIDENT_TOPIC}")
    client.subscribe(MQTT_INCIDENT_TOPIC, qos=1)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        event = json.loads(payload)
    except Exception as e:
        print(f"[MQTT WORKER] Malformed payload, dropped: {e}")
        return

    # Simple retry logic: up to 3 attempts with exponential backoff
    for attempt in range(1, 4):
        success = post_event(event)
        if success:
            break
        wait = 2 ** (attempt - 1)
        print(f"[MQTT WORKER] Retry {attempt}/3 after {wait}s")
        time.sleep(wait)
    else:
        # All retries failed – persist for manual replay
        publish_failed(event)

def run():
    global client
    client_id = "sentinel-outputs-worker"
    client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    except Exception as e:
        print(f"[MQTT WORKER] Unable to connect to broker: {e}")
        sys.exit(1)
    # Graceful shutdown on SIGINT/SIGTERM
    def handle_stop(signum, frame):
        print("[MQTT WORKER] Shutting down…")
        client.disconnect()
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    client.loop_forever()

if __name__ == "__main__":
    run()
