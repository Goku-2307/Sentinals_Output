import os
import json
from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"

def publish_output(topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Publish a JSON payload to an MQTT topic.

    * In **DEMO_MODE** the payload is printed and a simulated result is returned.
    * Otherwise we use ``paho.mqtt.publish.single`` with QoS = 1, no retain.
      Authentication and TLS are applied only if the corresponding environment
      variables are set.
    """
    if DEMO_MODE:
        print(f"[DEMO MQTT] topic={topic} payload={json.dumps(payload)}")
        return {"status": "simulated", "topic": topic}
    try:
        from paho.mqtt import publish as mqtt_publish
        auth = None
        if MQTT_USERNAME:
            auth = {"username": MQTT_USERNAME, "password": MQTT_PASSWORD}
        # ``tls`` expects a dict; an empty dict uses default TLS settings.
        tls = {} if MQTT_TLS else None
        mqtt_publish.single(
            topic=topic,
            payload=json.dumps(payload),
            qos=1,
            retain=False,
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            auth=auth,
            tls=tls,
        )
        return {"status": "published", "topic": topic}
    except Exception as exc:
        # Truncate error to 300 chars as required
        err = str(exc)[:300]
        return {"status": "failed", "error": err}
