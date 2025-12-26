import os, time, socket, base64, json, random
import yaml, httpx
from common.logging_utils import now_ms, log_event, new_trace_id
from .generators import make_payload

PROTOCOL = os.getenv("PROTOCOL", "lora")
TARGET_UDP = os.getenv("TARGET_UDP", "protocol-agent-lora:9001")
IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity-manager:8001")
LOG_DIR = os.getenv("LOG_DIR", f"/logs/proto-gen-{PROTOCOL}")
WORKLOAD_PATH = "/app/configs/workload.yml"
RUN_DURATION_SEC = int(os.getenv("RUN_DURATION_SEC", "60"))
START_DELAY_SEC = float(os.getenv("START_DELAY_SEC", "2"))
REGISTER_TIMEOUT_SEC = float(os.getenv("REGISTER_TIMEOUT_SEC", "30"))

h, p = TARGET_UDP.split(":"); p = int(p)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def load_cfg():
    with open(WORKLOAD_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def register(protocol: str, phy_id: str, logical_id: str):
    """Register (protocol, phy_id) -> logical_id mapping in Identity Manager.

    Startup ordering is not deterministic in containerized deployments, therefore we retry
    until the Identity Manager becomes reachable.
    """
    deadline = time.time() + REGISTER_TIMEOUT_SEC
    last_err: str | None = None
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.post(
                    f"{IDENTITY_URL}/register",
                    json={"protocol": protocol, "phy_id": phy_id, "logical_id": logical_id},
                )
                r.raise_for_status()
                return r.json()
        except Exception as e:
            last_err = str(e)
            log_event(
                LOG_DIR,
                "events.jsonl",
                {
                    "ts": now_ms(),
                    "event": "register_retry",
                    "protocol": protocol,
                    "phy_id": phy_id,
                    "logical_id": logical_id,
                    "err": last_err,
                },
            )
            time.sleep(1.0)
    raise RuntimeError(f"Identity Manager register timeout after {REGISTER_TIMEOUT_SEC}s: {last_err}")

def phy_id_for(i: int) -> str:
    return f"{PROTOCOL.upper()}-{i:04d}-{random.randint(100000,999999)}"

def main():
    cfg = load_cfg()
    p_cfg = cfg["protocols"][PROTOCOL]
    N = int(p_cfg["devices"])
    hz = float(p_cfg["hz"])
    payload_bytes = int(p_cfg["payload_bytes"])
    prefix = cfg.get("logical_id_prefix", {}).get(PROTOCOL, f"siteA/{PROTOCOL}")
    repl = cfg.get("replacement", {"enabled": False, "at_seconds": 60, "percent_devices": 0})
    repl_enabled = bool(repl.get("enabled", False))
    repl_at = int(repl.get("at_seconds", 60))
    repl_pct = float(repl.get("percent_devices", 0))

    devices = []
    for i in range(N):
        logical_id = f"{prefix}/sensor{i:04d}"
        phy = phy_id_for(i)
        rec = register(PROTOCOL, phy, logical_id)
        devices.append({"i": i, "logical_id": logical_id, "phy_id": phy, "seq": 0})
        log_event(LOG_DIR, "events.jsonl", {"ts": now_ms(), "event": "device_init", **rec})
    if START_DELAY_SEC > 0:
        time.sleep(START_DELAY_SEC)

    start = time.time()
    end_time = start + RUN_DURATION_SEC
    next_tick = time.time()
    replaced = set()

    while True:
        now = time.time()
        if now >= end_time:
            break
        elapsed = int(now - start)

        if repl_enabled and elapsed >= repl_at:
            k = max(1, int(round(N * repl_pct / 100.0)))
            cand = [d for d in devices if d["i"] not in replaced]
            random.shuffle(cand)
            for d in cand[:k]:
                old_phy = d["phy_id"]
                new_phy = phy_id_for(d["i"])
                rec = register(PROTOCOL, new_phy, d["logical_id"])
                d["phy_id"] = new_phy
                replaced.add(d["i"])
                log_event(LOG_DIR, "events.jsonl", {"ts": now_ms(), "event": "device_replace", "logical_id": d["logical_id"], "old_phy": old_phy, "new_phy": new_phy, "vip": rec["vip"]})
            repl_enabled = False

        if now < next_tick:
            time.sleep(min(0.01, next_tick-now))
            continue

        batch = max(1, int((N * hz) / 10.0))
        for _ in range(batch):
            d = random.choice(devices)
            d["seq"] += 1
            trace_id = new_trace_id()
            ts_gen = now_ms()
            payload = make_payload(PROTOCOL, payload_bytes)
            msg = {
                "protocol": PROTOCOL,
                "phy_id": d["phy_id"],
                "logical_id": d["logical_id"],
                "seq": d["seq"],
                "trace_id": trace_id,
                "ts_gen": ts_gen,
                "payload_b64": base64.b64encode(payload).decode("ascii"),
            }
            sock.sendto(json.dumps(msg).encode("utf-8"), (h, p))
            log_event(LOG_DIR, "events.jsonl", {"ts": ts_gen, "event": "frame_sent", **msg})
        next_tick += 0.1

    log_event(LOG_DIR, "events.jsonl", {"ts": now_ms(), "event": "run_complete", "duration_sec": RUN_DURATION_SEC})

if __name__ == "__main__":
    main()
