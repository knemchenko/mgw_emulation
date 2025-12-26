import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
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
                except Exception:
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate Exp2 traffic amplification metrics from logs.")
    ap.add_argument("--logs", required=True, help="Path to the logs directory")
    ap.add_argument("--out", required=True, help="Output JSON file path")
    ap.add_argument(
        "--window-sec",
        type=float,
        default=None,
        help="If set, only count events within the last N seconds of the log timeline (helps when logs contain multiple runs).",
    )
    args = ap.parse_args()

    logs = Path(args.logs)
    t0: Optional[int] = None
    if args.window_sec is not None:
        max_ts = compute_max_ts(logs)
        t0 = max_ts - int(args.window_sec * 1000)

    pub_msgs = 0
    pub_bytes = 0
    topics = defaultdict(int)

    for p in logs.rglob("semantic-core/events.jsonl"):
        for e in read_jsonl(p):
            if t0 is not None and isinstance(e.get("ts"), int) and e["ts"] < t0:
                continue
            if e.get("event") == "publish":
                pub_msgs += 1
                pub_bytes += int(e.get("msg_size", 0))
                topics[e.get("topic", "")] += 1

    recv_msgs = 0
    for p in logs.rglob("app-subscriber/events.jsonl"):
        for e in read_jsonl(p):
            if t0 is not None and isinstance(e.get("ts"), int) and e["ts"] < t0:
                continue
            if e.get("event") == "recv":
                recv_msgs += 1

    out = {
        "publisher": {"messages": pub_msgs, "bytes": pub_bytes},
        "subscriber": {"messages": recv_msgs},
        "topic_histogram_top10": sorted(topics.items(), key=lambda kv: kv[1], reverse=True)[:10],
        "derived": {
            "subscriber_msgs_per_published_msg": (recv_msgs / pub_msgs) if pub_msgs else None,
            "window_sec": args.window_sec,
        },
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
