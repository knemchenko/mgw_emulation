#!/usr/bin/env python3
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def plot_metric(df_combo: pd.DataFrame, metric: str, ylabel: str, title: str, out_png: str, out_svg: str):
    plt.figure()
    for mode in ["replication", "uns"]:
        d = df_combo[df_combo["mode"] == mode].copy()
        if d.empty:
            continue
        d = d.groupby("n_app", as_index=False)[metric].mean().sort_values("n_app")
        plt.plot(d["n_app"], d[metric], marker="o", label=mode)

    plt.xlabel("N_app")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.savefig(out_svg)
    plt.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results/uplink_suite/merged.csv")
    ap.add_argument("--outdir", default="figures/uplink_suite")
    ap.add_argument("--only", default="", help="Optional: 'lam=10,qos=1,payload=256'")
    ap.add_argument("--drop_outliers", action="store_true", help="Drop obvious S_wire outliers")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    df["cpu_total_s"] = df["cpu_user_s"] + df["cpu_system_s"]
    df["cpu_load"] = df["cpu_total_s"] / df["wall_s"].clip(lower=1e-9)

    # Optional: drop obvious outliers (interface noise)
    if args.drop_outliers:
        df = df[df["s_wire_per_publish_B"] < 10_000].copy()

    # Optional filter parsing
    if args.only.strip():
        filt = {}
        for p in [x.strip() for x in args.only.split(",") if x.strip()]:
            k, v = p.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "lam":
                filt["lam"] = float(v)
            elif k == "qos":
                filt["qos"] = int(v)
            elif k == "payload":
                filt["payload_bytes"] = int(v)
        for k, v in filt.items():
            df = df[df[k] == v]

    ensure_dir(args.outdir)

    combos = df[["lam", "qos", "payload_bytes"]].drop_duplicates().sort_values(["lam", "qos", "payload_bytes"])
    for _, r in combos.iterrows():
        lam = float(r["lam"])
        qos = int(r["qos"])
        payload = int(r["payload_bytes"])
        d = df[(df["lam"] == lam) & (df["qos"] == qos) & (df["payload_bytes"] == payload)].copy()
        if d.empty:
            continue

        tag = f"lam{int(lam) if lam.is_integer() else lam}_qos{qos}_payload{payload}"
        base = os.path.join(args.outdir, tag)

        plot_metric(d, "tx_kbps", "TX (kbps)", f"Uplink TX vs N_app ({tag})",
                    base + "_tx_kbps.png", base + "_tx_kbps.svg")
        plot_metric(d, "p95_ms", "p95 one-way latency (ms)", f"p95 latency vs N_app ({tag})",
                    base + "_p95_ms.png", base + "_p95_ms.svg")
        plot_metric(d, "cpu_load", "CPU load (CPU-seconds / wall-second)", f"CPU load vs N_app ({tag})",
                    base + "_cpu_load.png", base + "_cpu_load.svg")

        print("Wrote:", tag)

    print("Done:", args.outdir)

if __name__ == "__main__":
    main()
