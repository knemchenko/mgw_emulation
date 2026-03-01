# src/bench_subscriber.py
import argparse
import json
import os
import time
import struct
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import numpy as np
import paho.mqtt.client as mqtt


CONTROL_START = "control/start"
CONTROL_STOP  = "control/stop"

DATA_UNS_TOPIC = "uns/updates"
DATA_TENANT_WILDCARD = "tenant/+/updates"


def now_ns() -> int:
    return time.time_ns()


@dataclass
class RunConfig:
    run_id: str
    mode: str              # "uns" or "replication"
    n_app: int
    lam: float             # msg/s
    qos: int
    payload_bytes: int
    duration_s: float
    note: str = ""


@dataclass
class RunStats:
    run_id: str
    started_ns: int
    ended_ns: int
    rx_msgs: int
    rx_bytes_payload: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    mean_ms: float


class SubscriberCollector:
    def __init__(self, outdir: str, qos: int):
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)

        self.qos = qos
        self.active: bool = False
        self.cfg: Optional[RunConfig] = None

        self.lat_ms: List[float] = []
        self.rx_msgs: int = 0
        self.rx_bytes_payload: int = 0
        self.started_ns: int = 0

        # map seq -> first latency (optional: you can de-dup by semantic updates)
        self._seen_seq: Dict[int, float] = {}

    def start_run(self, cfg: RunConfig):
        self.active = True
        self.cfg = cfg
        self.lat_ms.clear()
        self.rx_msgs = 0
        self.rx_bytes_payload = 0
        self._seen_seq.clear()
        self.started_ns = now_ns()

    def stop_run(self) -> Optional[RunStats]:
        if not self.active or self.cfg is None:
            return None

        ended_ns = now_ns()
        lat = np.array(self.lat_ms, dtype=np.float64) if self.lat_ms else np.array([], dtype=np.float64)

        def pct(p: float) -> float:
            return float(np.percentile(lat, p)) if lat.size else float("nan")

        stats = RunStats(
            run_id=self.cfg.run_id,
            started_ns=self.started_ns,
            ended_ns=ended_ns,
            rx_msgs=self.rx_msgs,
            rx_bytes_payload=self.rx_bytes_payload,
            p50_ms=pct(50),
            p95_ms=pct(95),
            p99_ms=pct(99),
            max_ms=float(np.max(lat)) if lat.size else float("nan"),
            mean_ms=float(np.mean(lat)) if lat.size else float("nan"),
        )

        # persist
        cfg_path = os.path.join(self.outdir, f"run_{self.cfg.run_id}_cfg.json")
        st_path  = os.path.join(self.outdir, f"run_{self.cfg.run_id}_subscriber_stats.json")
        lat_path = os.path.join(self.outdir, f"run_{self.cfg.run_id}_lat_ms.csv")

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.cfg), f, indent=2)

        with open(st_path, "w", encoding="utf-8") as f:
            json.dump(asdict(stats), f, indent=2)

        # store raw latencies (optional but полезно для “robustness” графіків)
        with open(lat_path, "w", encoding="utf-8") as f:
            f.write("lat_ms\n")
            for v in self.lat_ms:
                f.write(f"{v:.6f}\n")

        self.active = False
        self.cfg = None
        return stats

    def on_data(self, payload: bytes):
        # payload format (binary):
        # [0:8]  uint64 seq
        # [8:16] uint64 t_send_ns
        if len(payload) < 16:
            return

        seq, t_send = struct.unpack("!QQ", payload[:16])
        t_recv = now_ns()
        lat_ms = (t_recv - t_send) / 1e6

        self.rx_msgs += 1
        self.rx_bytes_payload += len(payload)

        # варіант: рахуємо всі повідомлення
        self.lat_ms.append(lat_ms)

        # варіант (якщо захочеш latency “на semantic update”, а не на publish):
        # if seq not in self._seen_seq:
        #     self._seen_seq[seq] = lat_ms
        #     self.lat_ms.append(lat_ms)


def parse_run_cfg(msg_bytes: bytes) -> RunConfig:
    obj = json.loads(msg_bytes.decode("utf-8"))
    return RunConfig(
        run_id=str(obj["run_id"]),
        mode=str(obj["mode"]),
        n_app=int(obj["n_app"]),
        lam=float(obj["lam"]),
        qos=int(obj["qos"]),
        payload_bytes=int(obj["payload_bytes"]),
        duration_s=float(obj["duration_s"]),
        note=str(obj.get("note", "")),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", required=True)
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--outdir", default="results/uplink_suite")
    ap.add_argument("--qos", type=int, default=0)
    args = ap.parse_args()

    collector = SubscriberCollector(outdir=args.outdir, qos=args.qos)

    client = mqtt.Client(client_id=f"collector-{int(time.time())}", clean_session=True)

    def on_connect(c, u, f, rc):
        c.subscribe([(CONTROL_START, 0), (CONTROL_STOP, 0)])
        # data topics subscribed on start (mode-specific)

    def on_message(c, u, msg):
        topic = msg.topic
        if topic == CONTROL_START:
            cfg = parse_run_cfg(msg.payload)
            collector.start_run(cfg)

            # subscribe to relevant data topics
            if cfg.mode == "uns":
                c.subscribe([(DATA_UNS_TOPIC, cfg.qos)])
            else:
                c.subscribe([(DATA_TENANT_WILDCARD, cfg.qos)])

        elif topic == CONTROL_STOP:
            collector.stop_run()

            # unsubscribe from data topics to avoid mixing runs
            c.unsubscribe(DATA_UNS_TOPIC)
            c.unsubscribe(DATA_TENANT_WILDCARD)

        else:
            if collector.active:
                collector.on_data(msg.payload)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(args.broker, args.port, keepalive=30)
    client.loop_forever()


if __name__ == "__main__":
    main()
