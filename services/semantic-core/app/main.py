import os, base64, json, struct
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn, httpx
import paho.mqtt.client as mqtt
from common.logging_utils import now_ms, log_event
from .kg import SemanticDriverStore
from .codecs import CODECS

LOG_DIR = os.getenv("LOG_DIR", "/logs/semantic-core")
PORT = int(os.getenv("PORT", "8003"))
IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity-manager:8001")
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
KG_PATH = os.getenv("KG_PATH", "/app/kg/semantic_drivers.ttl")
DECODER_MODE = os.getenv("DECODER_MODE", "ontology")  # ontology | hardcoded

# Exp2 knobs:
# - UNS mode (P + A): publish once to mgw/<logical_id>/telemetry and rely on broker fan-out
# - P2P mode (P×A): publish APP_COUNT times to mgw_p2p/app<i>/<logical_id>/telemetry
P2P_MODE = os.getenv("P2P_MODE", "0") == "1"
APP_COUNT = int(os.getenv("APP_COUNT", "1"))

store = SemanticDriverStore(KG_PATH)

app = FastAPI(title="Semantic Core", version="0.2")

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()

class IngestReq(BaseModel):
    protocol: str
    phy_id: str
    trace_id: str
    seq: int
    ts_gen: int
    payload_b64: str
    retries: int = 0
    ts_acp_in: int | None = None

def hardcoded_decode(protocol: str, payload: bytes) -> Dict[str, Any]:
    # Produces final normalized output directly, without KG lookups.
    if protocol in ("lora", "zigbee"):
        temp_x100, hum_x10 = struct.unpack(">hH", payload[:4])
        return {
            "temperature": {"value": temp_x100 / 100.0, "unit": "°C"},
            "humidity": {"value": hum_x10 / 10.0, "unit": "%"},
        }
    if protocol == "ble":
        temp, hum = struct.unpack(">ff", payload[:8])
        return {
            "temperature": {"value": float(temp), "unit": "°C"},
            "humidity": {"value": float(hum), "unit": "%"},
        }
    raise ValueError("Unknown protocol")

def apply_mappings(raw: Dict[str, Any], mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for m in mappings:
        rk = m["rawKey"]
        if rk not in raw:
            continue
        scaled = float(raw[rk]) * float(m["scale"])
        ok = (m["min"] <= scaled <= m["max"])
        out[m["unifiedKey"]] = {"value": scaled, "unit": m["unit"], "range_ok": ok}
    return out

@app.post("/ingest")
async def ingest(req: IngestReq):
    ts_core_in = now_ms()

    # Resolve identity
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{IDENTITY_URL}/resolve/by-phy/{req.phy_id}")
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="Unknown phy_id")
        ident = r.json()

    payload = base64.b64decode(req.payload_b64)

    # Decode + normalize
    if DECODER_MODE == "hardcoded":
        normalized = hardcoded_decode(req.protocol, payload)
        codec_name = "hardcoded"
    else:
        model_uri = ident["model_uri"]
        codec_name = store.get_codec_name(model_uri)
        mappings = store.get_mappings(model_uri)
        fn = CODECS.get(codec_name)
        if not fn:
            raise HTTPException(status_code=500, detail=f"Unknown codec {codec_name}")
        raw = fn(payload)
        normalized = apply_mappings(raw, mappings)

    ts_decode_done = now_ms()

    logical_id = ident["logical_id"]
    base_topic = f"mgw/{logical_id}/telemetry"

    # Topic set for Exp2
    topics: List[str] = []
    if P2P_MODE:
        for i in range(1, APP_COUNT + 1):
            topics.append(f"mgw_p2p/app{i}/{logical_id}/telemetry")
    else:
        topics.append(base_topic)

    msg = {
        "source_id": logical_id,
        "phy_id": req.phy_id,
        "protocol": req.protocol,
        "(V)IP": ident["vip"],
        "seq": req.seq,
        "trace_id": req.trace_id,
        "retries": req.retries,
        "ts_gen": req.ts_gen,
        "ts_acp_in": req.ts_acp_in,
        "ts_core_in": ts_core_in,
        "ts_decode_done": ts_decode_done,
        "decoder_mode": DECODER_MODE,
        "codec": codec_name,
        "p2p_mode": P2P_MODE,
        "app_count": APP_COUNT,
        "data": normalized,
    }

    payload_str = json.dumps(msg, ensure_ascii=False)
    msg_size = len(payload_str.encode("utf-8"))

    published_topics: List[str] = []
    for topic in topics:
        mqtt_client.publish(topic, payload_str)
        ts_pub = now_ms()
        published_topics.append(topic)
        log_event(LOG_DIR, "events.jsonl", {
            "ts": ts_pub,
            "event": "publish",
            "topic": topic,
            "msg_size": msg_size,
            **msg
        })

    return {"ok": True, "topics": published_topics, "msg_size": msg_size}

@app.get("/health")
def health():
    return {"ok": True, "decoder_mode": DECODER_MODE, "p2p_mode": P2P_MODE, "app_count": APP_COUNT}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="info")
