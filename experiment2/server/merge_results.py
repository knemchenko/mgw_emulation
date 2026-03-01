# merge_results.py
import json, glob
import pandas as pd

PUB_GLOB = "results/uplink_suite/run_*_publisher_stats.json"
SUB_GLOB = "results/uplink_suite/run_*_subscriber_stats.json"

def load_many(pat):
    rows = []
    for p in glob.glob(pat):
        with open(p, "r", encoding="utf-8") as f:
            rows.append(json.load(f))
    return pd.DataFrame(rows)

pub = load_many(PUB_GLOB)
sub = load_many(SUB_GLOB)

if pub.empty:
    raise SystemExit("No publisher stats found")
if sub.empty:
    raise SystemExit("No subscriber stats found")

df = pub.merge(sub, on="run_id", how="left", suffixes=("_pub", "_sub"))

# derived
df["cpu_total_s"] = df["cpu_user_s"] + df["cpu_system_s"]
df["s_wire_per_publish_B"] = df["tx_bytes"] / df["publish_count"]
df["s_wire_per_update_B"]  = df["tx_bytes"] / df["semantic_updates"]

# subscriber expects 1 RX per publish
df["expected_rx_msgs"] = df["publish_count"]
df["rx_loss_ratio"] = 1.0 - (df["rx_msgs"].fillna(0) / df["expected_rx_msgs"])

out = "results/uplink_suite/merged.csv"
df.to_csv(out, index=False)
print("Wrote:", out)
print(df[["run_id","mode","n_app","lam","qos","payload_bytes","tx_kbps","cpu_total_s","p95_ms","rx_loss_ratio","s_wire_per_publish_B"]].head(12))
