import os
import json
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# Load environment variables (broker config)
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"
MQTT_INCIDENT_TOPIC = os.getenv("MQTT_INCIDENT_TOPIC", "sentinel/incidents/confirmed")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[LISTENER] Connected to MQTT broker, subscribing…")
        client.subscribe("sentinel/outputs/#", qos=1)
    else:
        print(f"[LISTENER] Connection failed with code {rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print(f"[LISTENER] Topic: {msg.topic}\nPayload: {json.dumps(payload, indent=2)}")
    except Exception:
        print(f"[LISTENER] Topic: {msg.topic}\nRaw payload: {msg.payload.decode()}")


def main():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_forever()

if __name__ == "__main__":
    main()
