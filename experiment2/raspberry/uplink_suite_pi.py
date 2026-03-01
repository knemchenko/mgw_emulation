# src/uplink_suite_pi.py
import argparse
import json
import os
import time
import struct
import itertools
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

import psutil
import paho.mqtt.client as mqtt


def now_ns() -> int:
    return time.time_ns()


def read_net_tx_bytes(iface: str) -> int:
    path = f"/sys/class/net/{iface}/statistics/tx_bytes"
    with open(path, "r", encoding="utf-8") as f:
        return int(f.read().strip())


@dataclass
class Case:
    mode: str            # "uns" | "replication"
    n_app: int
    lam: float
    qos: int
    payload_bytes: int
    duration_s: float
    note: str = ""


@dataclass
class PublisherStats:
    run_id: str
    iface: str
    broker: str
    port: int
    mode: str
    n_app: int
    lam: float
    qos: int
    payload_bytes: int
    duration_s: float
    publish_count: int
    semantic_updates: int
    tx_bytes: int
    tx_kbps: float
    cpu_user_s: float
    cpu_system_s: float
    wall_s: float


CONTROL_START = "control/start"
CONTROL_STOP  = "control/stop"

TOPIC_UNS = "uns/updates"
TOPIC_TENANT_FMT = "tenant/{i}/updates"


def build_payload(seq: int, payload_bytes: int) -> bytes:
    # 16 bytes header + filler
    header = struct.pack("!QQ", seq, now_ns())
    if payload_bytes < 16:
        return header[:payload_bytes]
    filler = b"\x00" * (payload_bytes - 16)
    return header + filler


def publish_loop(client: mqtt.Client, case: Case) -> Dict[str, Any]:
    # timing: periodic publish at lam msg/s (semantic updates)
    period_s = 1.0 / case.lam
    semantic_updates = int(case.lam * case.duration_s)
    publish_count = 0

    t0 = time.perf_counter()
    next_t = t0

    for seq in range(1, semantic_updates + 1):
        payload = build_payload(seq, case.payload_bytes)

        if case.mode == "uns":
            client.publish(TOPIC_UNS, payload=payload, qos=case.qos)
            publish_count += 1
        else:
            # replication: publish to each tenant topic
            for i in range(1, case.n_app + 1):
                client.publish(TOPIC_TENANT_FMT.format(i=i), payload=payload, qos=case.qos)
                publish_count += 1

        next_t += period_s
        now_t = time.perf_counter()
        sleep_s = next_t - now_t
        if sleep_s > 0:
            time.sleep(sleep_s)

    wall_s = time.perf_counter() - t0
    return {
        "semantic_updates": semantic_updates,
        "publish_count": publish_count,
        "wall_s": wall_s,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", required=True)
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--iface", required=True, help="eth0 or wlan0")
    ap.add_argument("--outdir", default="results/uplink_suite")
    ap.add_argument("--runs-prefix", default="pi")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

   # матриця кейсів (міняй під себе)
    modes = ["replication", "uns"]
    n_apps = [1, 5, 10, 20, 50]
    lams  = [2.0, 10.0, 50.0]
    qoss  = [0, 1]
    payloads = [256, 1024]      # bytes
    duration_s = 60.0          # кожен кейс


    cases: List[Case] = []
    for mode, n_app, lam, qos, payload in itertools.product(modes, n_apps, lams, qoss, payloads):
        # UNS не залежить від n_app для publisher, але залишаємо для симетрії (і для таблиць)
        cases.append(Case(mode=mode, n_app=n_app, lam=lam, qos=qos, payload_bytes=payload, duration_s=duration_s))

    client = mqtt.Client(client_id=f"pub-{args.runs_prefix}-{int(time.time())}", clean_session=True)
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()

    proc = psutil.Process(os.getpid())

    all_stats: List[PublisherStats] = []

    for idx, case in enumerate(cases, 1):
        run_id = f"{args.runs_prefix}-{idx:03d}-{int(time.time())}"

        # control/start
        start_msg = {
            "run_id": run_id,
            "mode": case.mode,
            "n_app": case.n_app,
            "lam": case.lam,
            "qos": case.qos,
            "payload_bytes": case.payload_bytes,
            "duration_s": case.duration_s,
            "note": case.note,
        }
        client.publish(CONTROL_START, json.dumps(start_msg), qos=0)
        time.sleep(0.5)  # дай subscriber підписатись

        tx0 = read_net_tx_bytes(args.iface)
        cpu0 = proc.cpu_times()

        loop_res = publish_loop(client, case)

        cpu1 = proc.cpu_times()
        tx1 = read_net_tx_bytes(args.iface)

        # control/stop
        client.publish(CONTROL_STOP, json.dumps({"run_id": run_id}), qos=0)
        time.sleep(0.5)

        tx_bytes = max(0, tx1 - tx0)
        wall_s = float(loop_res["wall_s"])
        tx_kbps = (tx_bytes * 8.0) / max(wall_s, 1e-9) / 1000.0

        st = PublisherStats(
            run_id=run_id,
            iface=args.iface,
            broker=args.broker,
            port=args.port,
            mode=case.mode,
            n_app=case.n_app,
            lam=case.lam,
            qos=case.qos,
            payload_bytes=case.payload_bytes,
            duration_s=case.duration_s,
            publish_count=int(loop_res["publish_count"]),
            semantic_updates=int(loop_res["semantic_updates"]),
            tx_bytes=int(tx_bytes),
            tx_kbps=float(tx_kbps),
            cpu_user_s=float(cpu1.user - cpu0.user),
            cpu_system_s=float(cpu1.system - cpu0.system),
            wall_s=float(wall_s),
        )
        all_stats.append(st)

        # persist per-run
        with open(os.path.join(args.outdir, f"run_{run_id}_publisher_stats.json"), "w", encoding="utf-8") as f:
            json.dump(asdict(st), f, indent=2)

        print(f"[{idx}/{len(cases)}] {run_id} done: tx_kbps={tx_kbps:.1f}, pub={st.publish_count}, cpu={st.cpu_user_s+st.cpu_system_s:.3f}s")

        time.sleep(1.0)  # “cooldown” між кейсами

    # persist summary
    with open(os.path.join(args.outdir, "publisher_all_runs.json"), "w", encoding="utf-8") as f:
        json.dump([asdict(x) for x in all_stats], f, indent=2)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()

