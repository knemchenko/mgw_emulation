import os, json, socket, re, time
import paho.mqtt.client as mqtt
from common.logging_utils import now_ms, log_event

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
RUN_DURATION_SEC = int(os.getenv("RUN_DURATION_SEC", "60"))

TOPIC = os.getenv("TOPIC", "auto")
P2P_MODE = os.getenv("P2P_MODE", "0") == "1"

APP_ID = os.getenv("APP_ID", "auto")
if APP_ID == "auto":
    # docker compose --scale gives each container a distinct hostname
    APP_ID = socket.gethostname()

def derive_appn(app_id: str) -> str:
    # Try to map hostname suffix digits -> appN. If not found, fall back to app1.
    m = re.search(r"(\d+)$", app_id)
    if m:
        return f"app{m.group(1)}"
    return "app1"

if TOPIC == "auto":
    if P2P_MODE:
        TOPIC = f"mgw_p2p/{derive_appn(APP_ID)}/#"
    else:
        TOPIC = "mgw/#"

LOG_DIR = os.getenv("LOG_DIR", "/logs/app-subscriber")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe(TOPIC)
    log_event(LOG_DIR, "events.jsonl", {"ts": now_ms(), "event": "connect", "topic": TOPIC, "app_id": APP_ID})

def on_message(client, userdata, msg):
    ts = now_ms()
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception:
        payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}
    payload["ts_app_recv"] = ts
    payload["app_id"] = APP_ID
    log_event(LOG_DIR, "events.jsonl", {"ts": ts, "event": "recv", "topic": msg.topic, **payload})

client.on_connect = on_connect
client.on_message = on_message

if __name__ == "__main__":
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    t_end = time.time() + RUN_DURATION_SEC
    while time.time() < t_end:
        time.sleep(0.5)
    log_event(LOG_DIR, "events.jsonl", {"ts": now_ms(), "event": "run_complete", "duration_sec": RUN_DURATION_SEC})
    client.disconnect()
    client.loop_stop()
