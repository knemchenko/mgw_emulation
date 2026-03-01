#!/usr/bin/env python3
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def plot_metric(df_combo: pd.DataFrame, metric: str, ylabel: str, title: str, out_png: str, out_svg: str):
    plt.figure()
    # aggregate by n_app for each mode (mean)
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
    ap.add_argument("--only", default="", help="Optional filter: e.g. 'lam=10,qos=1,payload=256'")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)

    # Derived CPU load (fraction of one CPU core over wall time)
    if "cpu_total_s" not in df.columns:
        df["cpu_total_s"] = df["cpu_user_s"] + df["cpu_system_s"]
    df["cpu_load"] = df["cpu_total_s"] / df["wall_s"].clip(lower=1e-9)

    # Quick sanity warning for negative p95
    neg = (df["p95_ms"] < 0).sum()
    if neg > 0:
        print(f"WARNING: {neg} runs have negative p95_ms. One-way latency is unreliable (clock offset). "
              f"Enable NTP/chrony on both hosts or switch to RTT measurement.")

    ensure_dir(args.outdir)

    # Optional filter parsing
    filt = {}
    if args.only.strip():
        parts = [x.strip() for x in args.only.split(",") if x.strip()]
        for p in parts:
            k, v = p.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k in ("lam",):
                filt[k] = float(v)
            elif k in ("qos", "payload"):
                filt["payload_bytes" if k == "payload" else k] = int(v)
            else:
                filt[k] = v

    if filt:
        for k, v in filt.items():
            df = df[df[k] == v]

    combos = df[["lam", "qos", "payload_bytes"]].drop_duplicates().sort_values(["lam", "qos", "payload_bytes"])

    for _, row in combos.iterrows():
        lam = float(row["lam"])
        qos = int(row["qos"])
        payload = int(row["payload_bytes"])

        d = df[(df["lam"] == lam) & (df["qos"] == qos) & (df["payload_bytes"] == payload)].copy()
        if d.empty:
            continue

        tag = f"lam{int(lam) if lam.is_integer() else lam}_qos{qos}_payload{payload}"
        base = os.path.join(args.outdir, tag)

        plot_metric(
            d,
            metric="tx_kbps",
            ylabel="TX (kbps)",
            title=f"Uplink TX vs N_app ({tag})",
            out_png=base + "_tx_kbps.png",
            out_svg=base + "_tx_kbps.svg",
        )

        plot_metric(
            d,
            metric="p95_ms",
            ylabel="p95 one-way latency (ms)",
            title=f"p95 latency vs N_app ({tag})",
            out_png=base + "_p95_ms.png",
            out_svg=base + "_p95_ms.svg",
        )

        plot_metric(
            d,
            metric="cpu_load",
            ylabel="CPU load (CPU-seconds / wall-second)",
            title=f"CPU load vs N_app ({tag})",
            out_png=base + "_cpu_load.png",
            out_svg=base + "_cpu_load.svg",
        )

        print(f"Wrote figures for {tag}")

    print("Done. Output:", args.outdir)

if __name__ == "__main__":
    main()
