# Expirement 2 — Uplink-suite (Raspberry Pi ↔ Server)

This experiment evaluates the scalability of MQTT-based semantic update delivery under uplink constraints, comparing:

- **replication**: gateway publishes `N_app` copies (per-tenant topics)
- **uns**: gateway publishes once to an UNS topic; broker performs fan-out

The goal is to obtain **real measurements** (not illustrative numbers) for:
- uplink TX rate on Raspberry Pi (interface-level)
- one-way latency distribution observed by the subscriber
- CPU time on Raspberry Pi
- a replication feasibility bound under a given uplink budget using measured on-wire size

---

## Testbed

**Raspberry Pi 5**
- Runs publisher workload (`uplink_suite_pi.py`)
- Measures uplink bytes on a chosen interface (`--iface wlan0` or `--iface eth0`)

**Server**
- Runs MQTT broker (Mosquitto)
- Runs subscriber/collector (`bench_subscriber.py`)
- Merges results and plots figures (`merge_results.py`, `plot_results.py`)

Transport can be **Wi‑Fi** or **Ethernet**.

---

## What is measured

**On Raspberry Pi (publisher):**
- `tx_kbps`: uplink TX rate derived from interface byte counters
- CPU time (user + system)
- `publish_count`, `semantic_updates`

**On server (subscriber):**
- `p50_ms`, `p95_ms`, `p99_ms`, `max_ms`, `mean_ms`
- `rx_msgs` and a loss proxy vs expected publishes

**Outputs**
- Pi: `results/uplink_suite/run_*_publisher_stats.json`
- Server: `results/uplink_suite/run_*_subscriber_stats.json`, `run_*_lat_ms.csv`, `run_*_cfg.json`
- Server post-processing: `results/uplink_suite/merged.csv`
- Figures: `figures/uplink_suite/*.png` and `*.svg`

---

## Reproducibility requirements (important)

### 1) Time synchronization (required for one-way latency)
One-way latency is computed as `t_recv - t_send` using timestamps from different hosts.
You must ensure **stable NTP/chrony synchronization** on both nodes.

Quick check (run on **both** Pi and Server):
```bash
chronyc tracking | egrep 'Leap status|System time|Last offset|RMS offset|Reference ID'
```
Recommended: offsets in the **1–5 ms** range (or better).

**Note (containers):** If the server runs inside LXC, stepping the system clock may be disabled (`chronyd -x`).
In that case, the container time follows the host clock; ensure the **host** is synchronized.

### 2) Avoid uplink measurement contamination
`tx_bytes` is measured at the **interface level**, so **any background traffic** (scp/rsync/apt updates/streams)
will corrupt `tx_kbps` and derived `S_wire` estimates. During the run:
- avoid file transfers on the measured interface
- stop unattended upgrades (optional)

---

## Setup

### A) Server

#### 1) Mosquitto should listen on 0.0.0.0:1883
Verify:
```bash
sudo ss -lntp | grep 1883
```
If Mosquitto listens only on `127.0.0.1:1883`, configure a listener:
```conf
listener 1883 0.0.0.0
allow_anonymous true
```
(For production, use authentication/TLS instead of `allow_anonymous true`.)

#### 2) Python environment
```bash
cd expirement2/server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3) Run subscriber/collector
```bash
python3 bench_subscriber.py --broker 0.0.0.0 --port 1883 --outdir results/uplink_suite
```

---

### B) Raspberry Pi

#### 1) Python environment
```bash
cd expirement2/raspberry
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2) Quick “negtest” (recommended before a full sweep)
Run a short single-case test (60s) to confirm p95 is non-negative:
```bash
python3 uplink_suite_pi.py --broker <SERVER_IP> --port 1883 --iface wlan0 --outdir results/uplink_suite --runs-prefix negtest
```
Check on server:
```bash
cat results/uplink_suite/run_negtest-*_subscriber_stats.json
```
Expect: `p95_ms > 0`.

#### 3) Full sweep
```bash
python3 uplink_suite_pi.py --broker <SERVER_IP> --port 1883 --iface wlan0 --outdir results/uplink_suite --runs-prefix wifi_full
```

---

## Post-processing (Server)

### 1) Copy publisher stats from Pi to Server
```bash
rsync -av raspberry@<PI_IP>:~/6g-gateway/results/uplink_suite/run_*_publisher_stats.json \
  ~/mgw/results/uplink_suite/
```

### 2) Merge into a single CSV
```bash
python3 merge_results.py
```
Output: `results/uplink_suite/merged.csv`

### 3) Plot figures
```bash
python3 plot_results.py --drop_outliers
```
`--drop_outliers` removes obvious interface-noise runs (e.g., extremely large `S_wire`).

Output: `figures/uplink_suite/`

