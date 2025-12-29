import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """Stream JSON objects from a JSONL file."""
    if not path.exists():
        return []
    def _iter():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Skip malformed lines (best-effort log parsing).
                    continue
    return _iter()


def compute_max_ts(logs: Path) -> int:
    """Return the maximum integer `ts` across all JSONL files under `logs`."""
    max_ts: Optional[int] = None
    for p in logs.rglob("*.jsonl"):
        for e in read_jsonl(p):
            ts = e.get("ts")
            if isinstance(ts, int):
                max_ts = ts if max_ts is None else max(max_ts, ts)
    return max_ts or 0


def is_telemetry_topic(topic: str, telemetry_suffix: str) -> bool:
    """Return True if a topic represents telemetry payloads."""
    # In this prototype, telemetry topics end with '/telemetry' for both UNS and P2P modes.
    return topic.endswith(telemetry_suffix)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Evaluate Exp2 traffic-amplification metrics from prototype logs."
    )
    ap.add_argument("--logs", required=True, help="Path to the logs directory")
    ap.add_argument("--out", required=True, help="Output JSON file path")
    ap.add_argument(
        "--window-sec",
        type=float,
        default=None,
        help=(
            "If set, only count events within the last N seconds of the log timeline "
            "(helps when logs contain multiple runs)."
        ),
    )
    ap.add_argument(
        "--telemetry-suffix",
        type=str,
        default="/telemetry",
        help="Telemetry topic suffix used for telemetry-only breakdown (default: /telemetry).",
    )
    ap.add_argument(
        "--frame-key",
        type=str,
        default="ts_core_in",
        help=(
            "Event field used as a stable per-frame identifier to estimate the number of ingested frames "
            "(default: ts_core_in)."
        ),
    )
    args = ap.parse_args()

    logs = Path(args.logs)
    t0: Optional[int] = None
    if args.window_sec is not None:
        max_ts = compute_max_ts(logs)
        t0 = max_ts - int(args.window_sec * 1000)

    # Publisher-side metrics (semantic-core publishes to MQTT).
    pub_msgs_all = 0
    pub_bytes_all = 0
    pub_msgs_tel = 0
    pub_bytes_tel = 0

    topics_all = defaultdict(int)
    topics_tel = defaultdict(int)

    frames_all: Set[int] = set()
    frames_tel: Set[int] = set()

    for p in logs.rglob("semantic-core/events.jsonl"):
        for e in read_jsonl(p):
            if t0 is not None and isinstance(e.get("ts"), int) and e["ts"] < t0:
                continue
            if e.get("event") != "publish":
                continue

            topic = str(e.get("topic", ""))
            msg_size = int(e.get("msg_size", 0))

            pub_msgs_all += 1
            pub_bytes_all += msg_size
            topics_all[topic] += 1

            frame_id = e.get(args.frame_key)
            if isinstance(frame_id, int):
                frames_all.add(frame_id)

            if is_telemetry_topic(topic, args.telemetry_suffix):
                pub_msgs_tel += 1
                pub_bytes_tel += msg_size
                topics_tel[topic] += 1
                if isinstance(frame_id, int):
                    frames_tel.add(frame_id)

    # Subscriber-side metrics (applications consuming broker topics).
    recv_msgs_all = 0
    recv_msgs_tel = 0
    recv_frames_all: Set[int] = set()
    recv_frames_tel: Set[int] = set()

    for p in logs.rglob("app-subscriber/events.jsonl"):
        for e in read_jsonl(p):
            if t0 is not None and isinstance(e.get("ts"), int) and e["ts"] < t0:
                continue
            if e.get("event") != "recv":
                continue

            recv_msgs_all += 1
            topic = str(e.get("topic", ""))
            frame_id = e.get(args.frame_key)
            if isinstance(frame_id, int):
                recv_frames_all.add(frame_id)

            if is_telemetry_topic(topic, args.telemetry_suffix):
                recv_msgs_tel += 1
                if isinstance(frame_id, int):
                    recv_frames_tel.add(frame_id)

    frames_all_n = len(frames_all)
    frames_tel_n = len(frames_tel)
    recv_frames_all_n = len(recv_frames_all)
    recv_frames_tel_n = len(recv_frames_tel)

    out = {
        # Backward-compatible summary (all publishes, all receives)
        "publisher": {"messages": pub_msgs_all, "bytes": pub_bytes_all},
        "subscriber": {"messages": recv_msgs_all},
        "topic_histogram_top10": sorted(topics_all.items(), key=lambda kv: kv[1], reverse=True)[:10],
        # Extended breakdown (telemetry-only)
        "telemetry": {
            "publisher": {"messages": pub_msgs_tel, "bytes": pub_bytes_tel},
            "subscriber": {"messages": recv_msgs_tel},
            "topic_histogram_top10": sorted(topics_tel.items(), key=lambda kv: kv[1], reverse=True)[:10],
        },
        # Frame-level normalization (helps explain ratios when offered load differs between runs)
        "frames": {
            "ingested_estimate": frames_all_n if frames_all_n else None,
            "ingested_estimate_telemetry": frames_tel_n if frames_tel_n else None,
            "delivered_estimate": recv_frames_all_n if recv_frames_all_n else None,
            "delivered_estimate_telemetry": recv_frames_tel_n if recv_frames_tel_n else None,
            "frame_key": args.frame_key,
        },
        "derived": {
            "subscriber_msgs_per_published_msg": (recv_msgs_all / pub_msgs_all) if pub_msgs_all else None,
            "publisher_msgs_per_frame": (pub_msgs_all / frames_all_n) if frames_all_n else None,
            "publisher_bytes_per_frame": (pub_bytes_all / frames_all_n) if frames_all_n else None,
            "telemetry_publisher_msgs_per_frame": (pub_msgs_tel / frames_tel_n) if frames_tel_n else None,
            "telemetry_publisher_bytes_per_frame": (pub_bytes_tel / frames_tel_n) if frames_tel_n else None,
            "window_sec": args.window_sec,
        },
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
