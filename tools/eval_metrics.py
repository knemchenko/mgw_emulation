import argparse, json, math
from pathlib import Path
from collections import defaultdict

def read_jsonl(path: Path):
    if not path.exists(): return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: yield json.loads(line)
            except Exception: pass

def percentile(xs, p):
    if not xs: return None
    xs=sorted(xs)
    k=(len(xs)-1)*p
    f=math.floor(k); c=math.ceil(k)
    if f==c: return xs[int(k)]
    return xs[f]*(c-k)+xs[c]*(k-f)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--logs", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    logs=Path(args.logs)
    gen_ts={}
    recv_ts=defaultdict(list)

    for p in logs.rglob("proto-gen-*/events.jsonl"):
        for e in read_jsonl(p):
            if e.get("event")=="frame_sent":
                gen_ts[e["trace_id"]] = e["ts_gen"]

    for p in logs.rglob("app-subscriber/events.jsonl"):
        for e in read_jsonl(p):
            if e.get("event")=="recv":
                recv_ts[e.get("trace_id")].append(e.get("ts_app_recv"))

    e2e=[]
    for tid, t0 in gen_ts.items():
        rs = recv_ts.get(tid)
        if not rs: continue
        e2e.append(min(rs)-t0)

    metrics={
        "samples": len(e2e),
        "e2e_ms": {
            "p50": percentile(e2e,0.5),
            "p95": percentile(e2e,0.95),
            "p99": percentile(e2e,0.99),
            "mean": (sum(e2e)/len(e2e)) if e2e else None
        }
    }
    out=Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))

if __name__=="__main__":
    main()
