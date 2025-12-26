import os, socket, json, time
import httpx, yaml
from common.logging_utils import now_ms, log_event

PROTOCOL = os.getenv("PROTOCOL", "lora")
ACP_URL = os.getenv("ACP_URL", "http://acp-router:8002/ingest")
UDP_LISTEN = os.getenv("UDP_LISTEN", "0.0.0.0:9001")
LOG_DIR = os.getenv("LOG_DIR", f"/logs/protocol-agent-{PROTOCOL}")
WORKLOAD_PATH = "/app/configs/workload.yml"

host, port = UDP_LISTEN.split(":")
port = int(port)

def load_cfg():
    try:
        with open(WORKLOAD_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}
CFG = load_cfg()
RET = CFG.get("retries", {"enabled": True, "max_retries": 2, "backoff_ms": 20})

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((host, port))

def post_with_retry(payload: dict) -> bool:
    enabled = bool(RET.get("enabled", True))
    maxr = int(RET.get("max_retries", 0))
    backoff = int(RET.get("backoff_ms", 10))
    tries = 0
    while True:
        tries += 1
        payload["retries"] = tries - 1
        try:
            with httpx.Client(timeout=5) as client:
                r = client.post(ACP_URL, json=payload)
                r.raise_for_status()
                return True
        except Exception:
            if (not enabled) or tries > maxr + 1:
                return False
            time.sleep(backoff/1000.0)

def main():
    while True:
        data, _ = sock.recvfrom(65535)
        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        ts = now_ms()
        log_event(LOG_DIR, "events.jsonl", {"ts": ts, "event": "agent_recv", **msg})
        ok = post_with_retry({
            "protocol": msg["protocol"],
            "phy_id": msg["phy_id"],
            "trace_id": msg["trace_id"],
            "seq": msg["seq"],
            "ts_gen": msg["ts_gen"],
            "payload_b64": msg["payload_b64"],
            "retries": 0,
        })
        log_event(LOG_DIR, "events.jsonl", {"ts": now_ms(), "event": "agent_forward", "ok": ok, "trace_id": msg["trace_id"]})

if __name__ == "__main__":
    main()
